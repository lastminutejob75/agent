"""Métriques patient V2 — calcul déterministe (SQL), jamais par l'IA."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.db import get_conn, list_patient_notes, normalize_phone_number
from backend.patient_v2_db import (
    ensure_patient_v2_schema,
    exec_pg,
    fetch_one_pg,
    normalize_patient_phone,
    pg_available,
)

logger = logging.getLogger(__name__)

ABSENCE_RE = re.compile(
    r"(no[\s-]?show|absence au rendez|absent au rendez|manqu[ée].{0,12}rdv|"
    r"pas venu|n['']est pas venu|n'a pas honor)",
    re.IGNORECASE,
)

RECOMPUTE_SQL = """
WITH rdv AS (
    SELECT occurred_at, statut,
           (payload_json->>'annulation_delai_h')::numeric AS delai_annul_h
    FROM patient_events
    WHERE tenant_id = %s AND patient_phone = %s AND type = 'rdv'
),
contacts AS (
    SELECT MAX(occurred_at) AS dernier_contact
    FROM patient_events
    WHERE tenant_id = %s AND patient_phone = %s
),
motifs AS (
    SELECT motif, COUNT(*) AS n
    FROM patient_events
    WHERE tenant_id = %s AND patient_phone = %s AND motif IS NOT NULL
    GROUP BY motif ORDER BY n DESC LIMIT 3
)
SELECT
    COUNT(*) FILTER (WHERE statut IN ('honore','no_show','annule')) AS nb_rdv,
    COUNT(*) FILTER (WHERE statut = 'no_show') AS nb_no_shows,
    COUNT(*) FILTER (WHERE statut = 'annule' AND delai_annul_h < 24) AS nb_annul_tardive,
    ROUND(COALESCE(
        COUNT(*) FILTER (WHERE statut = 'honore')::numeric
        / NULLIF(COUNT(*) FILTER (
            WHERE statut = 'honore' OR statut = 'no_show'
               OR (statut = 'annule' AND delai_annul_h < 24)), 0),
    1) * 100, 0) AS taux_assiduite,
    MAX(occurred_at) FILTER (WHERE statut = 'honore' AND occurred_at <= now()) AS dernier_rdv,
    MIN(occurred_at) FILTER (WHERE occurred_at > now() AND statut NOT IN ('annule','no_show')) AS prochain_rdv,
    (SELECT dernier_contact FROM contacts) AS dernier_contact,
    (SELECT json_agg(json_build_object('motif', motif, 'n', n)) FROM motifs) AS motifs_top
FROM rdv
"""


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _absence_dates_from_notes(notes: List[Dict[str, Any]]) -> set[str]:
    dates: set[str] = set()
    for note in notes:
        text_val = str(note.get("note_text") or "")
        if ABSENCE_RE.search(text_val):
            created = _parse_dt(note.get("created_at"))
            if created:
                dates.add(created.date().isoformat())
    return dates


def _list_appointments_for_sync(tenant_id: int, phone_norm: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    import os

    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_SLOTS_URL")
    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row

            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT a.id, a.motif, s.start_ts
                        FROM appointments a
                        JOIN slots s ON s.id = a.slot_id AND s.tenant_id = a.tenant_id
                        WHERE a.tenant_id = %s
                        ORDER BY s.start_ts DESC
                        LIMIT 200
                        """,
                        (tenant_id,),
                    )
                    for row in cur.fetchall() or []:
                        contact_norm = normalize_phone_number(row.get("contact") if "contact" in row else "")
                        if contact_norm and contact_norm != phone_norm:
                            continue
                        start = _parse_dt(row.get("start_ts"))
                        if not start:
                            continue
                        rows.append({"start": start, "motif": row.get("motif") or "Consultation", "id": row.get("id")})
            return rows
        except Exception:
            logger.debug("sync appointments pg failed", exc_info=True)

    conn = get_conn()
    try:
        raw = conn.execute(
            """
            SELECT a.id, a.contact, a.motif, s.date, s.time
            FROM appointments a
            JOIN slots s ON s.id = a.slot_id AND s.tenant_id = a.tenant_id
            WHERE a.tenant_id = ?
            ORDER BY s.date DESC, s.time DESC
            LIMIT 200
            """,
            (tenant_id,),
        ).fetchall()
        for row in raw:
            if normalize_phone_number(row["contact"] or "") != phone_norm:
                continue
            try:
                start = datetime.fromisoformat(f"{row['date']}T{row['time']}:00").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            rows.append({"start": start, "motif": row["motif"] or "Consultation", "id": row["id"]})
    finally:
        conn.close()
    return rows


def sync_patient_events_from_sources(tenant_id: int, patient_phone: str) -> None:
    """Reconstruit patient_events depuis RDV + notes (best-effort, idempotent)."""
    ensure_patient_v2_schema()
    phone = normalize_patient_phone(patient_phone)
    notes = list_patient_notes(tenant_id, phone, limit=200)
    absence_dates = _absence_dates_from_notes(notes)
    appts = _list_appointments_for_sync(tenant_id, phone)
    now = datetime.now(timezone.utc)

    conn = get_conn()
    try:
        conn.execute(
            "DELETE FROM patient_events WHERE tenant_id = ? AND patient_phone = ? AND type = 'rdv'",
            (tenant_id, phone),
        )
        for appt in appts:
            start: datetime = appt["start"]
            day = start.date().isoformat()
            if start > now:
                statut = "planifie"
            elif day in absence_dates:
                statut = "no_show"
            else:
                statut = "honore"
            event_id = f"rdv-{appt.get('id')}-{int(start.timestamp())}"
            conn.execute(
                """
                INSERT OR REPLACE INTO patient_events
                (id, tenant_id, patient_phone, type, occurred_at, statut, motif, payload_json)
                VALUES (?, ?, ?, 'rdv', ?, ?, ?, ?)
                """,
                (
                    event_id,
                    tenant_id,
                    phone,
                    start.isoformat(),
                    statut,
                    appt.get("motif"),
                    json.dumps({"source": "appointments"}, ensure_ascii=False),
                ),
            )
        conn.commit()
    finally:
        conn.close()

    if pg_available():
        exec_pg(
            "DELETE FROM patient_events WHERE tenant_id = %s AND patient_phone = %s AND type = 'rdv'",
            (tenant_id, phone),
        )
        for appt in appts:
            start = appt["start"]
            day = start.date().isoformat()
            statut = "planifie" if start > now else ("no_show" if day in absence_dates else "honore")
            exec_pg(
                """
                INSERT INTO patient_events
                (tenant_id, patient_phone, type, occurred_at, statut, motif, payload_json)
                VALUES (%s, %s, 'rdv', %s, %s, %s, %s::jsonb)
                ON CONFLICT DO NOTHING
                """,
                (
                    tenant_id,
                    phone,
                    start.isoformat(),
                    statut,
                    appt.get("motif"),
                    json.dumps({"source": "appointments", "appointment_id": appt.get("id")}),
                ),
            )


def _apply_metric_guardrails(row: Dict[str, Any]) -> Dict[str, Any]:
    nb_rdv = int(row.get("nb_rdv") or 0)
    taux = row.get("taux_assiduite")
    if nb_rdv < 2:
        taux = None
        score = None
    else:
        score = int(taux) if taux is not None else None
        if score is not None:
            nb_no_shows = int(row.get("nb_no_shows") or 0)
            score = max(0, min(100, score - min(nb_no_shows * 10, 30)))
    dernier_contact = _parse_dt(row.get("dernier_contact"))
    recence = None
    if dernier_contact:
        recence = max(0, (datetime.now(timezone.utc) - dernier_contact).days)
    motifs_top = row.get("motifs_top")
    if isinstance(motifs_top, str):
        try:
            motifs_top = json.loads(motifs_top)
        except json.JSONDecodeError:
            motifs_top = []
    return {
        "nb_rdv": nb_rdv,
        "nb_no_shows": int(row.get("nb_no_shows") or 0),
        "nb_annul_tardive": int(row.get("nb_annul_tardive") or 0),
        "taux_assiduite": int(taux) if taux is not None else None,
        "score_fiabilite": score,
        "dernier_rdv": row.get("dernier_rdv"),
        "prochain_rdv": row.get("prochain_rdv"),
        "recence_jours": recence,
        "motifs_top_json": motifs_top or [],
    }


def recompute_patient_metrics(tenant_id: int, patient_phone: str) -> Dict[str, Any]:
    """Recalcule et persiste les métriques depuis patient_events."""
    ensure_patient_v2_schema()
    sync_patient_events_from_sources(tenant_id, patient_phone)
    phone = normalize_patient_phone(patient_phone)

    metrics: Dict[str, Any]
    if pg_available():
        row = fetch_one_pg(
            RECOMPUTE_SQL,
            (tenant_id, phone, tenant_id, phone, tenant_id, phone),
        )
        metrics = _apply_metric_guardrails(row or {})
    else:
        conn = get_conn()
        try:
            cur = conn.execute(
                """
                WITH rdv AS (
                    SELECT occurred_at, statut, json_extract(payload_json, '$.annulation_delai_h') AS delai_annul_h
                    FROM patient_events
                    WHERE tenant_id = ? AND patient_phone = ? AND type = 'rdv'
                )
                SELECT
                    SUM(CASE WHEN statut IN ('honore','no_show','annule') THEN 1 ELSE 0 END) AS nb_rdv,
                    SUM(CASE WHEN statut = 'no_show' THEN 1 ELSE 0 END) AS nb_no_shows,
                    SUM(CASE WHEN statut = 'annule' AND CAST(delai_annul_h AS REAL) < 24 THEN 1 ELSE 0 END) AS nb_annul_tardive,
                    MAX(CASE WHEN statut = 'honore' AND occurred_at <= datetime('now') THEN occurred_at END) AS dernier_rdv,
                    MIN(CASE WHEN occurred_at > datetime('now') AND statut NOT IN ('annule','no_show') THEN occurred_at END) AS prochain_rdv,
                    MAX(occurred_at) AS dernier_contact
                FROM rdv
                """,
                (tenant_id, phone),
            ).fetchone()
            base = dict(cur) if cur else {}
            nb_honore = conn.execute(
                "SELECT COUNT(*) AS n FROM patient_events WHERE tenant_id = ? AND patient_phone = ? AND type = 'rdv' AND statut = 'honore'",
                (tenant_id, phone),
            ).fetchone()["n"]
            denom = conn.execute(
                """
                SELECT COUNT(*) AS n FROM patient_events
                WHERE tenant_id = ? AND patient_phone = ? AND type = 'rdv'
                  AND (statut = 'honore' OR statut = 'no_show'
                       OR (statut = 'annule' AND CAST(json_extract(payload_json,'$.annulation_delai_h') AS REAL) < 24))
                """,
                (tenant_id, phone),
            ).fetchone()["n"]
            taux = round(nb_honore / denom * 100) if denom else None
            base["taux_assiduite"] = taux
            base["motifs_top"] = []
            metrics = _apply_metric_guardrails(base)
        finally:
            conn.close()

    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO patient_metrics (
                tenant_id, patient_phone, nb_rdv, nb_no_shows, nb_annul_tardive,
                taux_assiduite, score_fiabilite, dernier_rdv, prochain_rdv,
                recence_jours, motifs_top_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(tenant_id, patient_phone) DO UPDATE SET
                nb_rdv=excluded.nb_rdv, nb_no_shows=excluded.nb_no_shows,
                nb_annul_tardive=excluded.nb_annul_tardive, taux_assiduite=excluded.taux_assiduite,
                score_fiabilite=excluded.score_fiabilite, dernier_rdv=excluded.dernier_rdv,
                prochain_rdv=excluded.prochain_rdv, recence_jours=excluded.recence_jours,
                motifs_top_json=excluded.motifs_top_json, updated_at=datetime('now')
            """,
            (
                tenant_id,
                phone,
                metrics["nb_rdv"],
                metrics["nb_no_shows"],
                metrics["nb_annul_tardive"],
                metrics["taux_assiduite"],
                metrics["score_fiabilite"],
                str(metrics["dernier_rdv"] or "") or None,
                str(metrics["prochain_rdv"] or "") or None,
                metrics["recence_jours"],
                json.dumps(metrics["motifs_top_json"], ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    if pg_available():
        exec_pg(
            """
            INSERT INTO patient_metrics (
                tenant_id, patient_phone, nb_rdv, nb_no_shows, nb_annul_tardive,
                taux_assiduite, score_fiabilite, dernier_rdv, prochain_rdv,
                recence_jours, motifs_top_json, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, now())
            ON CONFLICT (tenant_id, patient_phone) DO UPDATE SET
                nb_rdv=EXCLUDED.nb_rdv, nb_no_shows=EXCLUDED.nb_no_shows,
                nb_annul_tardive=EXCLUDED.nb_annul_tardive, taux_assiduite=EXCLUDED.taux_assiduite,
                score_fiabilite=EXCLUDED.score_fiabilite, dernier_rdv=EXCLUDED.dernier_rdv,
                prochain_rdv=EXCLUDED.prochain_rdv, recence_jours=EXCLUDED.recence_jours,
                motifs_top_json=EXCLUDED.motifs_top_json, updated_at=now()
            """,
            (
                tenant_id,
                phone,
                metrics["nb_rdv"],
                metrics["nb_no_shows"],
                metrics["nb_annul_tardive"],
                metrics["taux_assiduite"],
                metrics["score_fiabilite"],
                metrics["dernier_rdv"],
                metrics["prochain_rdv"],
                metrics["recence_jours"],
                json.dumps(metrics["motifs_top_json"], ensure_ascii=False),
            ),
        )
    return metrics


def get_patient_metrics(tenant_id: int, patient_phone: str, *, refresh: bool = False) -> Dict[str, Any]:
    phone = normalize_patient_phone(patient_phone)
    if refresh:
        return recompute_patient_metrics(tenant_id, phone)
    ensure_patient_v2_schema()
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM patient_metrics WHERE tenant_id = ? AND patient_phone = ?",
            (tenant_id, phone),
        ).fetchone()
    finally:
        conn.close()
    if row:
        return {
            "nb_rdv": row["nb_rdv"],
            "nb_no_shows": row["nb_no_shows"],
            "nb_annul_tardive": row["nb_annul_tardive"],
            "taux_assiduite": row["taux_assiduite"],
            "score_fiabilite": row["score_fiabilite"],
            "dernier_rdv": row["dernier_rdv"],
            "prochain_rdv": row["prochain_rdv"],
            "recence_jours": row["recence_jours"],
            "motifs_top_json": _json_load(row["motifs_top_json"], []),
        }
    return recompute_patient_metrics(tenant_id, phone)


def _json_load(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except json.JSONDecodeError:
        return default
