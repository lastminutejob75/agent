# backend/leads_pg.py — Pre-onboarding leads (table pre_onboarding_leads)
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _get_conn():
    import psycopg
    from psycopg.rows import dict_row
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")
    if not url:
        raise RuntimeError("DATABASE_URL or PG_TENANTS_URL required for leads")
    return psycopg.connect(url, row_factory=dict_row)


def get_lead_by_email_for_upsert(email: str) -> Optional[Dict[str, Any]]:
    """
    Retourne un lead existant avec status in ('new','contacted') pour déduplication, ou None.
    Les leads converted/lost ne sont jamais retournés → jamais modifiés par un nouveau commit
    (pas d'écrasement d'historique ou de config).
    Si email vide, retourne None (pas de déduplication par email).
    """
    if not email or not (email or "").strip():
        return None
    email = (email or "").strip()
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, created_at, email, daily_call_volume, medical_specialty, medical_specialty_label, specialty_other, primary_pain_point, assistant_name, voice_gender,
                           opening_hours, wants_callback, callback_phone, callback_booking_date, callback_booking_slot, is_enterprise, source, status, notes, contacted_at, converted_at,
                           updated_at, last_submitted_at, max_daily_amplitude
                    FROM pre_onboarding_leads
                    WHERE LOWER(TRIM(email)) = LOWER(TRIM(%s)) AND status IN ('new', 'contacted')
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (email.strip(),),
                )
                row = cur.fetchone()
        return _row_to_lead(row) if row else None
    except Exception as e:
        logger.exception("get_lead_by_email_for_upsert failed: %s", e)
        return None


def upsert_lead(
    email: Optional[str],
    daily_call_volume: str,
    medical_specialty: str,
    primary_pain_point: str,
    assistant_name: str,
    voice_gender: str,
    opening_hours: Dict[str, Any],
    wants_callback: bool = False,
    callback_phone: Optional[str] = None,
    specialty_other: Optional[str] = None,
    medical_specialty_label: Optional[str] = None,
    source: str = "landing_cta",
) -> Optional[str]:
    """
    Si un lead existe déjà avec cet email et status in ('new','contacted') → UPDATE et retourne son id.
    Sinon INSERT et retourne le nouvel id. Évite les doublons quand un médecin refait le wizard.
    Si email vide/None (lead téléphone seul), pas de déduplication → insert.
    """
    is_enterprise = (daily_call_volume == "100+")
    existing = get_lead_by_email_for_upsert(email or "") if (email and (email or "").strip()) else None
    if existing:
        lead_id = existing["id"]
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    max_amp = compute_max_daily_amplitude(opening_hours)
                    cur.execute(
                        """
                        UPDATE pre_onboarding_leads
                        SET daily_call_volume = %s, medical_specialty = %s, medical_specialty_label = %s, primary_pain_point = %s, assistant_name = %s, voice_gender = %s,
                            opening_hours = %s::jsonb, wants_callback = %s, callback_phone = %s, specialty_other = %s, is_enterprise = %s, source = %s,
                            max_daily_amplitude = %s, updated_at = NOW(), last_submitted_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            daily_call_volume,
                            (medical_specialty or "").strip() or None,
                            (medical_specialty_label or "").strip() or None,
                            (primary_pain_point or "").strip() or None,
                            assistant_name.strip(),
                            voice_gender,
                            _json_dumps(opening_hours),
                            bool(wants_callback),
                            (callback_phone or "").strip() or None,
                            (specialty_other or "").strip() or None,
                            is_enterprise,
                            source,
                            max_amp,
                            lead_id,
                        ),
                    )
                conn.commit()
            return lead_id
        except Exception as e:
            logger.exception("upsert_lead update failed: %s", e)
            return None
    return insert_lead(
        email=(email or "").strip() or "",
        daily_call_volume=daily_call_volume,
        medical_specialty=medical_specialty,
        primary_pain_point=primary_pain_point,
        assistant_name=assistant_name,
        voice_gender=voice_gender,
        opening_hours=opening_hours,
        wants_callback=wants_callback,
        callback_phone=callback_phone,
        specialty_other=specialty_other,
        medical_specialty_label=medical_specialty_label,
        source=source,
    )


def insert_lead(
    email: str,  # peut être "" pour lead téléphone seul (colonne NOT NULL accepte '')
    daily_call_volume: str,
    medical_specialty: str,
    primary_pain_point: str,
    assistant_name: str,
    voice_gender: str,
    opening_hours: Dict[str, Any],
    wants_callback: bool = False,
    callback_phone: Optional[str] = None,
    specialty_other: Optional[str] = None,
    medical_specialty_label: Optional[str] = None,
    source: str = "landing_cta",
) -> Optional[str]:
    """Insert a new lead. Returns lead_id (uuid) or None on error."""
    try:
        lead_id = str(uuid.uuid4())
        max_amp = compute_max_daily_amplitude(opening_hours)
        with _get_conn() as conn:
            with conn.cursor() as cur:
                is_enterprise = (daily_call_volume == "100+")
                cur.execute(
                    """
                    INSERT INTO pre_onboarding_leads
                    (id, email, daily_call_volume, medical_specialty, medical_specialty_label, primary_pain_point, assistant_name, voice_gender, opening_hours, wants_callback, callback_phone, specialty_other, is_enterprise, source, status, last_submitted_at, updated_at, max_daily_amplitude)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, 'new', NOW(), NOW(), %s)
                    """,
                    (
                        lead_id,
                        (email or "").strip(),
                        daily_call_volume,
                        (medical_specialty or "").strip() or None,
                        (medical_specialty_label or "").strip() or None,
                        (primary_pain_point or "").strip() or None,
                        assistant_name.strip(),
                        voice_gender,
                        _json_dumps(opening_hours),
                        bool(wants_callback),
                        (callback_phone or "").strip() or None,
                        (specialty_other or "").strip() or None,
                        is_enterprise,
                        source,
                        max_amp,
                    ),
                )
            conn.commit()
        return lead_id
    except Exception as e:
        logger.exception("insert_lead failed: %s", e)
        return None


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


def _time_to_hours(t: str) -> float:
    """Parse HH:MM to decimal hours (e.g. 08:30 -> 8.5, 21:00 -> 21.0)."""
    if not t or not isinstance(t, str):
        return 0.0
    parts = (t.strip().split(":") + ["0"])[:2]
    try:
        h = int(parts[0].strip() or "0")
        m = int(parts[1].strip() or "0")
        return h + m / 60.0
    except (ValueError, TypeError):
        return 0.0


def compute_max_daily_amplitude(opening_hours: Optional[Dict[str, Any]]) -> Optional[float]:
    """
    Pour chaque jour ouvert: amplitude = end - start (heures).
    Retourne max(amplitudes) sur la semaine, ou None si aucun jour ouvert.
    """
    if not opening_hours or not isinstance(opening_hours, dict):
        return None
    day_keys_alt = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    amplitudes = []
    for i in range(7):
        key = str(i)
        slot = opening_hours.get(key) or opening_hours.get(
            (["lun", "mar", "mer", "jeu", "ven", "sam", "dim"][i])
        )
        if not slot and i < len(day_keys_alt):
            slot = opening_hours.get(day_keys_alt[i]) or opening_hours.get(day_keys_alt[i][:3])
        if not slot or not isinstance(slot, dict) or slot.get("closed"):
            continue
        start = (slot.get("start") or "").strip()
        end = (slot.get("end") or "").strip()
        if not start and not end:
            continue
        sh, eh = _time_to_hours(start), _time_to_hours(end)
        if eh > sh:
            amplitudes.append(eh - sh)
    return max(amplitudes) if amplitudes else None


def compute_amplitude_score(opening_hours: Optional[Dict[str, Any]]) -> int:
    """+20 si max_daily_amplitude >= 12h, +10 si >= 10h, sinon 0."""
    max_h = compute_max_daily_amplitude(opening_hours)
    if max_h is None:
        return 0
    if max_h >= 12:
        return 20
    if max_h >= 10:
        return 10
    return 0


def list_leads(
    status: Optional[str] = None,
    enterprise_only: Optional[bool] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """List leads. Optional filter by status and/or is_enterprise. Order: chronological (created_at desc, most recent first)."""
    where_parts = []
    params = []
    if status:
        where_parts.append("status = %s")
        params.append(status)
    if enterprise_only:
        where_parts.append("is_enterprise = true")
    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    params.append(limit)

    def _normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for row in rows:
            d = _row_to_lead(row)
            d.setdefault("notes_log", "[]")
            d.setdefault("follow_up_at", None)
            out.append(d)
        return out

    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, created_at, email, daily_call_volume, medical_specialty, medical_specialty_label, specialty_other, primary_pain_point, assistant_name, voice_gender,
                           opening_hours, wants_callback, callback_phone, callback_booking_date, callback_booking_slot, is_enterprise, source, status, notes,
                           COALESCE(notes_log, '[]'::jsonb) AS notes_log, follow_up_at,
                           contacted_at, converted_at, updated_at, last_submitted_at, max_daily_amplitude
                    FROM pre_onboarding_leads
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()
        return _normalize_rows(rows)
    except Exception as e:
        logger.warning("list_leads full query failed (schema?): %s", e)
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, created_at, email, daily_call_volume, medical_specialty, medical_specialty_label, specialty_other, primary_pain_point, assistant_name, voice_gender,
                           opening_hours, wants_callback, callback_phone, callback_booking_date, callback_booking_slot, is_enterprise, source, status, notes,
                           contacted_at, converted_at, updated_at, last_submitted_at, max_daily_amplitude
                    FROM pre_onboarding_leads
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()
        logger.info("list_leads: used minimal query (notes_log/follow_up_at may be missing)")
        return _normalize_rows(rows)
    except Exception as e:
        logger.exception("list_leads minimal failed: %s", e)
        return []


def lead_exists(lead_id: str) -> bool:
    """Vérifie l'existence d'un lead (requête minimale, robuste au schema)."""
    if not lead_id or not str(lead_id).strip():
        return False
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pre_onboarding_leads WHERE id = %s LIMIT 1", (str(lead_id).strip(),))
                return cur.fetchone() is not None
    except Exception as e:
        logger.warning("lead_exists failed: %s", e)
        return False


def _get_lead_full(lead_id: str) -> Optional[Dict[str, Any]]:
    """Requête complète (avec notes_log, follow_up_at). Peut échouer si migration 031 non appliquée."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, created_at, email, daily_call_volume, medical_specialty, medical_specialty_label, specialty_other, primary_pain_point, assistant_name, voice_gender,
                       opening_hours, wants_callback, callback_phone, callback_booking_date, callback_booking_slot, is_enterprise, source, status, notes,
                       COALESCE(notes_log, '[]'::jsonb) AS notes_log, follow_up_at,
                       tenant_id, contacted_at, converted_at, updated_at, last_submitted_at, max_daily_amplitude
                FROM pre_onboarding_leads
                WHERE id = %s
                """,
                (lead_id,),
            )
            row = cur.fetchone()
    return _row_to_lead(row) if row else None


def _get_lead_minimal(lead_id: str) -> Optional[Dict[str, Any]]:
    """Requête sans notes_log/follow_up_at (schema avant migration 031). Pour fallback."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, created_at, email, daily_call_volume, medical_specialty, medical_specialty_label, specialty_other, primary_pain_point, assistant_name, voice_gender,
                       opening_hours, wants_callback, callback_phone, callback_booking_date, callback_booking_slot, is_enterprise, source, status, notes,
                       tenant_id, contacted_at, converted_at, updated_at, last_submitted_at, max_daily_amplitude
                FROM pre_onboarding_leads
                WHERE id = %s
                """,
                (lead_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    d = _row_to_lead(row)
    if d is not None:
        d.setdefault("notes_log", "[]")
        d.setdefault("follow_up_at", None)
    return d


def get_lead(lead_id: str) -> Optional[Dict[str, Any]]:
    """Get one lead by id. Fallback sur requête minimale si schema incomplet (migration 031)."""
    if not lead_id or not str(lead_id).strip():
        return None
    lead_id = str(lead_id).strip()
    try:
        lead = _get_lead_full(lead_id)
        if lead is not None:
            return lead
    except Exception as e:
        logger.warning("get_lead full query failed (schema?): %s", e)
    try:
        lead = _get_lead_minimal(lead_id)
        if lead is not None:
            logger.info("get_lead: used minimal query (notes_log/follow_up_at may be missing)")
            return lead
    except Exception as e:
        logger.exception("get_lead minimal failed: %s", e)
    return None


def update_lead_callback_booking(
    lead_id: str,
    callback_booking_date: Optional[str],
    callback_booking_slot: Optional[str],
    callback_phone: Optional[str],
) -> bool:
    """Enregistre le créneau de rappel choisi (écran finalisation). date au format YYYY-MM-DD."""
    if not callback_booking_date or not callback_booking_slot:
        return False
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE pre_onboarding_leads
                    SET callback_booking_date = %s::date, callback_booking_slot = %s, callback_phone = COALESCE(NULLIF(TRIM(%s), ''), callback_phone), updated_at = NOW()
                    WHERE id = %s
                    """,
                    (callback_booking_date, (callback_booking_slot or "").strip() or None, (callback_phone or "").strip() or None, lead_id),
                )
            conn.commit()
        return True
    except Exception as e:
        logger.exception("update_lead_callback_booking failed: %s", e)
        return False


def update_lead(
    lead_id: str,
    status: Optional[str] = None,
    notes: Optional[str] = None,
    notes_log: Optional[str] = None,
    follow_up_at: Optional[str] = None,
) -> bool:
    """Update lead status, notes, notes_log and/or follow_up_at. Set contacted_at/converted_at when status changes."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                updates = []
                params = []
                if status is not None:
                    updates.append("status = %s")
                    params.append(status)
                    if status == "contacted":
                        updates.append("contacted_at = COALESCE(contacted_at, NOW())")
                    elif status == "converted":
                        updates.append("converted_at = COALESCE(converted_at, NOW())")
                if notes is not None:
                    updates.append("notes = %s")
                    params.append(notes)
                if notes_log is not None:
                    updates.append("notes_log = %s::jsonb")
                    params.append(notes_log)
                if follow_up_at is not None:
                    if follow_up_at.strip():
                        updates.append("follow_up_at = %s::timestamptz")
                        params.append(follow_up_at.strip())
                    else:
                        updates.append("follow_up_at = NULL")
                if not updates:
                    return True
                params.append(lead_id)
                cur.execute(
                    f"UPDATE pre_onboarding_leads SET {', '.join(updates)} WHERE id = %s",
                    params,
                )
            conn.commit()
        return True
    except Exception as e:
        logger.exception("update_lead failed: %s", e)
        return False


def count_new_leads() -> int:
    """Count leads with status = 'new' (for sidebar badge)."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS c FROM pre_onboarding_leads WHERE status = 'new'"
                )
                row = cur.fetchone()
        return int(row["c"]) if row else 0
    except Exception as e:
        logger.exception("count_new_leads failed: %s", e)
        return 0


def count_leads_total() -> int:
    """Compte total des leads (diagnostic). Retourne -1 si erreur."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM pre_onboarding_leads")
                row = cur.fetchone()
        return int(row["c"]) if row else 0
    except Exception as e:
        logger.warning("count_leads_total failed: %s", e)
        return -1


def _row_to_lead(r: Dict) -> Dict[str, Any]:
    out = dict(r)
    for key in ("created_at", "contacted_at", "converted_at", "updated_at", "last_submitted_at", "callback_booking_date", "follow_up_at"):
        if out.get(key) and hasattr(out[key], "isoformat"):
            out[key] = out[key].isoformat()
    return out
