"""
Rappels de rendez-vous par SMS, ~24h avant l'heure du RDV.

Sources couvertes (les deux contiennent le numéro patient) :
- `public_bookings` (réservations page publique)
- `appointments` JOIN `slots` (réservations vocales Clara + saisies manuelles dashboard)

Anti-doublon : table `appointment_reminders` (UNIQUE tenant/source/ref/kind).
Job APScheduler horaire : à chaque exécution, on traite la fenêtre [now+24h, now+25h).
Multi-tenant + RLS : on boucle sur les tenants actifs et on pose le contexte
`app.current_tenant_id` sur chaque connexion.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REMINDER_KIND = "sms_24h"

_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def reminders_enabled() -> bool:
    return os.getenv("APPOINTMENT_REMINDERS_ENABLED", "true").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _pg_url() -> Optional[str]:
    return os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL") or os.environ.get("PG_EVENTS_URL")


def _active_tenant_ids() -> List[int]:
    url = _pg_url()
    if not url:
        return []
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id FROM tenants WHERE COALESCE(status, 'active') = 'active' ORDER BY tenant_id"
                )
                return [int(r[0]) for r in cur.fetchall()]
    except Exception as e:
        if "does not exist" not in str(e).lower():
            logger.warning("appointment_reminders _active_tenant_ids failed: %s", e)
        return []


def ensure_reminders_schema() -> None:
    url = _pg_url()
    if not url:
        return
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS appointment_reminders (
                        id BIGSERIAL PRIMARY KEY,
                        tenant_id BIGINT,
                        source VARCHAR(20) NOT NULL,
                        ref_id VARCHAR(64) NOT NULL,
                        kind VARCHAR(20) NOT NULL DEFAULT 'sms_24h',
                        sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        UNIQUE (tenant_id, source, ref_id, kind)
                    )
                    """
                )
            conn.commit()
    except Exception as e:
        logger.warning("ensure_reminders_schema failed: %s", e)


def _set_tenant_ctx(conn, tenant_id: int) -> None:
    """Pose le contexte RLS au niveau session (survit aux commits)."""
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (str(int(tenant_id)),))


def _due_for_tenant(conn, tenant_id: int, ws: datetime, we: datetime) -> List[Dict[str, Any]]:
    """RDV du tenant dont le début est dans [ws, we), des deux sources."""
    out: List[Dict[str, Any]] = []

    # Source 1 : réservations page publique
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, patient_name, patient_phone, motif, start_iso
                FROM public_bookings
                WHERE tenant_id = %s
                  AND status IN ('confirmed', 'pending')
                  AND start_iso >= %s AND start_iso < %s
                """,
                (tenant_id, ws, we),
            )
            for r in cur.fetchall():
                out.append({
                    "source": "public",
                    "ref_id": str(r[0]),
                    "name": r[1] or "",
                    "phone": r[2] or "",
                    "motif": r[3] or "",
                    "start_ts": r[4],
                })
    except Exception as e:
        if "does not exist" not in str(e).lower():
            logger.warning("appointment_reminders public query failed tenant=%s: %s", tenant_id, e)

    # Source 2 : RDV vocaux / manuels (appointments JOIN slots)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.name, a.contact, a.contact_type, a.motif, s.start_ts
                FROM appointments a
                JOIN slots s ON s.id = a.slot_id
                WHERE a.tenant_id = %s
                  AND s.start_ts >= %s AND s.start_ts < %s
                """,
                (tenant_id, ws, we),
            )
            for r in cur.fetchall():
                contact_type = (r[3] or "").strip().lower()
                if contact_type == "email":
                    continue
                out.append({
                    "source": "local",
                    "ref_id": str(r[0]),
                    "name": r[1] or "",
                    "phone": r[2] or "",
                    "motif": r[4] or "",
                    "start_ts": r[5],
                })
    except Exception as e:
        if "does not exist" not in str(e).lower():
            logger.warning("appointment_reminders local query failed tenant=%s: %s", tenant_id, e)

    return out


def _already_reminded(conn, tenant_id: int, source: str, ref_id: str) -> bool:
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM appointment_reminders
                WHERE tenant_id = %s AND source = %s AND ref_id = %s AND kind = %s
                """,
                (tenant_id, source, ref_id, REMINDER_KIND),
            )
            return cur.fetchone() is not None
    except Exception as e:
        logger.warning("appointment_reminders _already_reminded failed: %s", e)
        return True  # en cas de doute, ne pas renvoyer


def _claim_reminder(conn, tenant_id: int, source: str, ref_id: str) -> bool:
    """Réserve atomiquement l'envoi : True si on l'a réservé (à envoyer maintenant).

    Sûr avec plusieurs workers/replicas : la contrainte UNIQUE garantit qu'un seul
    process réussit l'INSERT. Si l'envoi échoue ensuite, on libère via _release_reminder.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO appointment_reminders (tenant_id, source, ref_id, kind)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (tenant_id, source, ref_id, kind) DO NOTHING
                RETURNING id
                """,
                (tenant_id, source, ref_id, REMINDER_KIND),
            )
            claimed = cur.fetchone() is not None
        conn.commit()
        return claimed
    except Exception as e:
        logger.warning("appointment_reminders _claim_reminder failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def _release_reminder(conn, tenant_id: int, source: str, ref_id: str) -> None:
    """Libère une réservation (envoi échoué) pour réessai au prochain run."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM appointment_reminders
                WHERE tenant_id = %s AND source = %s AND ref_id = %s AND kind = %s
                """,
                (tenant_id, source, ref_id, REMINDER_KIND),
            )
        conn.commit()
    except Exception as e:
        logger.warning("appointment_reminders _release_reminder failed: %s", e)


def _tenant_display_name(tenant_id: int) -> str:
    try:
        from backend.tenant_config import get_params
        params = get_params(tenant_id) or {}
        name = (params.get("business_name") or "").strip()
        if name:
            return name
    except Exception:
        pass
    try:
        from backend.auth_pg import pg_get_tenant_name
        name = (pg_get_tenant_name(tenant_id) or "").strip()
        if name:
            return name
    except Exception:
        pass
    return "votre cabinet"


def _tenant_tz(tenant_id: int):
    try:
        from backend.tools_booking import _tenant_timezone_name
        tz_name = _tenant_timezone_name(tenant_id)
    except Exception:
        tz_name = "Europe/Paris"
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_name)
    except Exception:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Europe/Paris")


def _format_when(start_ts, tz) -> str:
    """Ex: 'mardi 24 juin à 14h30'."""
    dt = start_ts
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return str(start_ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(tz)
    jour = _JOURS[local.weekday()]
    mois = _MOIS[local.month - 1]
    heure = f"{local.hour}h{local.minute:02d}" if local.minute else f"{local.hour}h"
    return f"{jour} {local.day} {mois} à {heure}"


def _compose_message(name: str, when_str: str, cabinet: str, motif: str) -> str:
    prenom = (name or "").strip().split(" ")[0] if name else ""
    hello = f"Bonjour {prenom}, " if prenom else "Bonjour, "
    motif_part = f" ({motif.strip()})" if motif and motif.strip() else ""
    return (
        f"{hello}rappel de votre rendez-vous {when_str} avec {cabinet}{motif_part}. "
        f"En cas d'empêchement, merci de prévenir le cabinet. UWI"
    )


def run_appointment_reminders_job(dry_run: bool = False, only_tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Job horaire : envoie les rappels SMS pour les RDV ~24h à l'avance.

    dry_run=True : n'envoie rien, ne marque rien — retourne la liste de ce qui
    SERAIT envoyé (numéro masqué). only_tenant_id : restreint à un tenant (test).
    """
    if not reminders_enabled():
        return {"disabled": True}

    from backend.services.sms_service import sms_is_configured, send_sms_message
    from backend.db import normalize_phone_number

    def _extract_phone(raw: str) -> str:
        # Le champ contact local peut être combiné ('Tél. +33… · Email …') :
        # on extrait le 1er motif téléphone pour éviter de coller les chiffres d'un email.
        m = re.search(r"\+?\d[\d ().\-]{7,}", str(raw or ""))
        return normalize_phone_number(m.group(0)) if m else ""

    sms_ok = sms_is_configured()
    if not dry_run and not sms_ok:
        logger.info("appointment_reminders: SMS non configuré, job ignoré")
        return {"skipped": "sms_not_configured"}

    url = _pg_url()
    if not url:
        return {"skipped": "no_db"}

    ensure_reminders_schema()

    now = datetime.now(timezone.utc)
    ws = now + timedelta(hours=24)
    we = now + timedelta(hours=25)

    sent = 0
    failed = 0
    skipped = 0
    preview: List[Dict[str, Any]] = []
    tenants = [only_tenant_id] if only_tenant_id else _active_tenant_ids()

    import psycopg
    for tenant_id in tenants:
        try:
            with psycopg.connect(url) as conn:
                _set_tenant_ctx(conn, tenant_id)
                due = _due_for_tenant(conn, tenant_id, ws, we)
                if not due:
                    continue
                cabinet = _tenant_display_name(tenant_id)
                tz = _tenant_tz(tenant_id)
                seen: set = set()
                for item in due:
                    phone = _extract_phone(item.get("phone") or "")
                    if not phone:
                        skipped += 1
                        continue
                    # Anti-doublon intra-run (un même RDV mirroré sur 2 sources)
                    dedup_key = (phone, str(item.get("start_ts")))
                    if dedup_key in seen:
                        continue
                    when_str = _format_when(item.get("start_ts"), tz)
                    body = _compose_message(item.get("name") or "", when_str, cabinet, item.get("motif") or "")
                    if dry_run:
                        already = _already_reminded(conn, tenant_id, item["source"], item["ref_id"])
                        masked = f"***{phone[-4:]}" if len(phone) > 4 else "***"
                        preview.append({
                            "tenant_id": tenant_id, "source": item["source"], "ref_id": item["ref_id"],
                            "phone": masked, "when": when_str, "body": body,
                            "already_reminded": already,
                        })
                        seen.add(dedup_key)
                        continue
                    # Réservation atomique : un seul worker/replica enverra ce rappel.
                    if not _claim_reminder(conn, tenant_id, item["source"], item["ref_id"]):
                        skipped += 1
                        seen.add(dedup_key)
                        continue
                    ok, err = send_sms_message(phone, body)
                    if ok:
                        seen.add(dedup_key)
                        sent += 1
                    else:
                        # Envoi échoué : on libère pour réessayer au prochain run
                        _release_reminder(conn, tenant_id, item["source"], item["ref_id"])
                        failed += 1
                        logger.warning(
                            "appointment_reminders send failed tenant=%s source=%s ref=%s: %s",
                            tenant_id, item["source"], item["ref_id"], err,
                        )
        except Exception as e:
            logger.warning("appointment_reminders tenant=%s failed: %s", tenant_id, e)

    summary: Dict[str, Any] = {
        "sent": sent, "failed": failed, "skipped": skipped, "tenants": len(tenants),
        "sms_configured": sms_ok,
        "window": [ws.isoformat(), we.isoformat()],
    }
    if dry_run:
        summary["dry_run"] = True
        summary["would_send"] = preview
        return summary
    logger.info("appointment_reminders %s", summary)
    return summary
