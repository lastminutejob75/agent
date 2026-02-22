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
    """
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, created_at, email, daily_call_volume, medical_specialty, primary_pain_point, assistant_name, voice_gender,
                           opening_hours, wants_callback, source, status, notes, contacted_at, converted_at,
                           updated_at, last_submitted_at
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
    email: str,
    daily_call_volume: str,
    medical_specialty: str,
    primary_pain_point: str,
    assistant_name: str,
    voice_gender: str,
    opening_hours: Dict[str, Any],
    wants_callback: bool = False,
    source: str = "landing_cta",
) -> Optional[str]:
    """
    Si un lead existe déjà avec cet email et status in ('new','contacted') → UPDATE et retourne son id.
    Sinon INSERT et retourne le nouvel id. Évite les doublons quand un médecin refait le wizard.
    """
    existing = get_lead_by_email_for_upsert(email)
    if existing:
        lead_id = existing["id"]
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE pre_onboarding_leads
                        SET daily_call_volume = %s, medical_specialty = %s, primary_pain_point = %s, assistant_name = %s, voice_gender = %s,
                            opening_hours = %s::jsonb, wants_callback = %s, source = %s,
                            updated_at = NOW(), last_submitted_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            daily_call_volume,
                            (medical_specialty or "").strip() or None,
                            (primary_pain_point or "").strip() or None,
                            assistant_name.strip(),
                            voice_gender,
                            _json_dumps(opening_hours),
                            bool(wants_callback),
                            source,
                            lead_id,
                        ),
                    )
                conn.commit()
            return lead_id
        except Exception as e:
            logger.exception("upsert_lead update failed: %s", e)
            return None
    return insert_lead(
        email=email,
        daily_call_volume=daily_call_volume,
        medical_specialty=medical_specialty,
        primary_pain_point=primary_pain_point,
        assistant_name=assistant_name,
        voice_gender=voice_gender,
        opening_hours=opening_hours,
        wants_callback=wants_callback,
        source=source,
    )


def insert_lead(
    email: str,
    daily_call_volume: str,
    medical_specialty: str,
    primary_pain_point: str,
    assistant_name: str,
    voice_gender: str,
    opening_hours: Dict[str, Any],
    wants_callback: bool = False,
    source: str = "landing_cta",
) -> Optional[str]:
    """Insert a new lead. Returns lead_id (uuid) or None on error."""
    try:
        lead_id = str(uuid.uuid4())
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pre_onboarding_leads
                    (id, email, daily_call_volume, medical_specialty, primary_pain_point, assistant_name, voice_gender, opening_hours, wants_callback, source, status, last_submitted_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, 'new', NOW(), NOW())
                    """,
                    (
                        lead_id,
                        email.strip(),
                        daily_call_volume,
                        (medical_specialty or "").strip() or None,
                        (primary_pain_point or "").strip() or None,
                        assistant_name.strip(),
                        voice_gender,
                        _json_dumps(opening_hours),
                        bool(wants_callback),
                        source,
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


def list_leads(status: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    """List leads, newest first. Optional filter by status."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                if status:
                    cur.execute(
                        """
                        SELECT id, created_at, email, daily_call_volume, medical_specialty, primary_pain_point, assistant_name, voice_gender,
                               opening_hours, wants_callback, source, status, notes, contacted_at, converted_at,
                               updated_at, last_submitted_at
                        FROM pre_onboarding_leads
                        WHERE status = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (status, limit),
                    )
                else:
                    # Tri par défaut : new d'abord (leads chauds), puis created_at DESC
                    cur.execute(
                        """
                        SELECT id, created_at, email, daily_call_volume, medical_specialty, primary_pain_point, assistant_name, voice_gender,
                               opening_hours, wants_callback, source, status, notes, contacted_at, converted_at,
                               updated_at, last_submitted_at
                        FROM pre_onboarding_leads
                        ORDER BY (status = 'new') DESC, created_at DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                rows = cur.fetchall()
        return [_row_to_lead(r) for r in rows]
    except Exception as e:
        logger.exception("list_leads failed: %s", e)
        return []


def get_lead(lead_id: str) -> Optional[Dict[str, Any]]:
    """Get one lead by id."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, created_at, email, daily_call_volume, medical_specialty, primary_pain_point, assistant_name, voice_gender,
                           opening_hours, wants_callback, source, status, notes, tenant_id, contacted_at, converted_at,
                           updated_at, last_submitted_at
                    FROM pre_onboarding_leads
                    WHERE id = %s
                    """,
                    (lead_id,),
                )
                row = cur.fetchone()
        return _row_to_lead(row) if row else None
    except Exception as e:
        logger.exception("get_lead failed: %s", e)
        return None


def update_lead(lead_id: str, status: Optional[str] = None, notes: Optional[str] = None) -> bool:
    """Update lead status and/or notes. Set contacted_at/converted_at when status changes."""
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


def _row_to_lead(r: Dict) -> Dict[str, Any]:
    out = dict(r)
    for key in ("created_at", "contacted_at", "converted_at", "updated_at", "last_submitted_at"):
        if out.get(key) and hasattr(out[key], "isoformat"):
            out[key] = out[key].isoformat()
    return out
