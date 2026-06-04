from __future__ import annotations

import json
import logging
import re
import sqlite3
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from backend.pg_tenant_context import set_tenant_id_on_connection
from backend.tenants_pg import _pg_url, pg_get_tenant_params, pg_tenants_connection

logger = logging.getLogger(__name__)

DAY_KEYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _jsonable(value: Any):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def _slugify(value: str) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return ""
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = re.sub(r"[^\w\s-]", "", raw, flags=re.ASCII)
    return re.sub(r"[-\s]+", "-", raw).strip("-")


def _slug_candidates(params: Dict[str, Any], tenant_name: str = "") -> Set[str]:
    out: Set[str] = set()
    if not isinstance(params, dict):
        params = {}
    for key in ("public_slug", "business_name", "practitioner_name", "name"):
        s = _slugify(str(params.get(key) or ""))
        if s:
            out.add(s)
    s = _slugify(tenant_name or "")
    if s:
        out.add(s)
    return out


def _sqlite_agent_db_path() -> Optional[Path]:
    root = Path(__file__).resolve().parent.parent
    for candidate in (root / "agent.db", root / "data" / "agent.db"):
        if candidate.exists():
            return candidate
    return None


def _get_tenant_id_by_public_slug_sqlite(slug: str) -> Optional[int]:
    db_path = _sqlite_agent_db_path()
    if not db_path:
        return None
    slug = (slug or "").strip().lower()
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT t.tenant_id, t.name, tc.params_json
            FROM tenants t
            LEFT JOIN tenant_config tc ON tc.tenant_id = t.tenant_id
            """
        )
        for row in cur.fetchall():
            tid = int(row["tenant_id"])
            name = row["name"] or ""
            params: Dict[str, Any] = {}
            if row["params_json"]:
                try:
                    params = json.loads(row["params_json"])
                except Exception:
                    params = {}
            if slug in _slug_candidates(params, name):
                conn.close()
                return tid
        conn.close()
    except Exception as e:
        logger.debug("get_tenant_id_by_public_slug sqlite slug=%s err=%s", slug[:80], e)
    return None


def _get_tenant_id_by_public_slug_uncached(slug: str) -> Optional[int]:
    """Résolution slug → tenant_id (PG indexé puis SQLite local). Pas de scan complet en prod."""
    slug = (slug or "").strip().lower()
    if not slug:
        return None

    if _pg_url():
        try:
            from backend.pg_tenant_context import set_bypass_tenant_rls_on_connection

            with pg_tenants_connection() as conn:
                set_bypass_tenant_rls_on_connection(conn, enabled=True)
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT tenant_id FROM tenant_profiles WHERE LOWER(public_slug) = %s LIMIT 1",
                        (slug,),
                    )
                    row = cur.fetchone()
                    if row:
                        return int(row.get("tenant_id") if hasattr(row, "get") else row[0])
                    cur.execute(
                        """
                        SELECT tenant_id
                        FROM tenant_config
                        WHERE LOWER(params_json->>'public_slug') = %s
                        LIMIT 1
                        """,
                        (slug,),
                    )
                    row = cur.fetchone()
                    if row:
                        return int(row.get("tenant_id") if hasattr(row, "get") else row[0])
        except Exception as e:
            logger.debug("get_tenant_id_by_public_slug pg slug=%s err=%s", slug[:80], e)

    return _get_tenant_id_by_public_slug_sqlite(slug)


@lru_cache(maxsize=512)
def _get_tenant_id_by_public_slug_cached(slug: str) -> Optional[int]:
    return _get_tenant_id_by_public_slug_uncached(slug)


def get_tenant_id_by_public_slug(slug: str) -> Optional[int]:
    """Retourne le tenant_id correspondant au public_slug (cache mémoire, invalidé rarement)."""
    return _get_tenant_id_by_public_slug_cached((slug or "").strip().lower())


def get_public_profile_bundle(tenant_id: int) -> Dict[str, Any]:
    """Profil + params pour la fiche publique (PG puis fallback SQLite local)."""
    profile = get_profile(tenant_id) or {}
    params: Dict[str, Any] = {}
    params_tuple = pg_get_tenant_params(tenant_id)
    if params_tuple:
        params = params_tuple[0] if isinstance(params_tuple, tuple) else (params_tuple or {})
    if not isinstance(params, dict):
        params = {}

    if profile or params.get("business_name") or params.get("practitioner_name"):
        return {"profile": profile, "params": params}

    db_path = _sqlite_agent_db_path()
    if not db_path:
        return {"profile": profile, "params": params}
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT params_json FROM tenant_config WHERE tenant_id = ?",
            (int(tenant_id),),
        ).fetchone()
        conn.close()
        if row and row["params_json"]:
            loaded = json.loads(row["params_json"])
            if isinstance(loaded, dict):
                params = loaded
    except Exception as e:
        logger.debug("get_public_profile_bundle sqlite tenant_id=%s err=%s", tenant_id, e)

    if not profile and params:
        profile = {
            "practitioner_name": params.get("practitioner_name") or params.get("primary_practitioner_name") or "",
            "cabinet_name": params.get("business_name") or "",
            "specialty": params.get("specialty_label") or params.get("profession") or "",
            "phone": params.get("phone_number") or "",
            "email": params.get("contact_email") or "",
            "address_line": params.get("address_line1") or params.get("address") or "",
            "postal_code": params.get("postal_code") or "",
            "city": params.get("city") or "",
            "website_url": params.get("website_url") or "",
            "languages": params.get("languages") or [],
            "accepts_new_patients": params.get("accepts_new_patients", True),
            "practitioner_photo_url": params.get("practitioner_photo_url") or "",
        }
    return {"profile": profile, "params": params}


def _parse_profile_row(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not row:
        return {}
    langs = row.get("languages_json")
    if isinstance(langs, str):
        try:
            langs = json.loads(langs)
        except Exception:
            langs = []
    if not isinstance(langs, list):
        langs = []
    return {
        "practitioner_name": row.get("practitioner_name") or "",
        "cabinet_name": row.get("cabinet_name") or "",
        "specialty": row.get("specialty") or "",
        "phone": row.get("phone") or "",
        "email": row.get("email") or "",
        "address_line": row.get("address_line") or "",
        "postal_code": row.get("postal_code") or "",
        "city": row.get("city") or "",
        "website_url": row.get("website_url") or "",
        "languages": [str(v).strip() for v in langs if str(v).strip()],
        "accepts_new_patients": bool(row.get("accepts_new_patients", True)),
        "practitioner_photo_url": row.get("practitioner_photo_url") or "",
        "public_slug": row.get("public_slug") or "",
    }


def _parse_params_json(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            loaded = json.loads(raw)
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}
    return {}


def _parse_assistant_row(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not row:
        return {}
    faq_items = row.get("faq_items_json")
    if isinstance(faq_items, str):
        try:
            faq_items = json.loads(faq_items)
        except Exception:
            faq_items = []
    if not isinstance(faq_items, list):
        faq_items = []
    return {
        "assistant_name": row.get("assistant_name") or "Clara",
        "welcome_message": row.get("welcome_message") or "",
        "documents_to_bring": row.get("documents_to_bring") or "",
        "documents_hint": row.get("documents_to_bring") or "",
        "access_instructions": row.get("access_instructions") or "",
        "payment_methods": row.get("payment_methods") or "",
        "parking_info": row.get("parking_info") or "",
        "pmr_access": row.get("pmr_access") or "",
        "sensitive_medical_instruction": row.get("sensitive_medical_instruction") or "",
        "escalation_instruction": row.get("escalation_instruction") or "",
        "human_handoff_instruction": row.get("human_handoff_instruction") or "",
        "faq_items": faq_items,
        "vapi_assistant_id": row.get("vapi_assistant_id") or "",
    }


def fetch_public_practitioner_bundle_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """
    Charge en une seule connexion pool PG toutes les données page publique pour un slug.
    Évite 6+ sessions PG séquentielles (SET LOCAL + SELECT répétés).
    """
    slug_key = (slug or "").strip().lower()
    if not slug_key:
        return None

    if not _pg_url():
        tid = _get_tenant_id_by_public_slug_sqlite(slug_key)
        if not tid:
            return None
        bundle = get_public_profile_bundle(int(tid))
        return {
            "tenant_id": int(tid),
            "profile": bundle.get("profile") or {},
            "params": bundle.get("params") if isinstance(bundle.get("params"), dict) else {},
            "assistant": get_assistant_settings(int(tid)) or {},
            "reasons": list_appointment_reasons(int(tid)) or [],
            "opening_hours": get_opening_hours(int(tid)) or [],
        }

    try:
        from backend.pg_tenant_context import set_bypass_tenant_rls_on_connection, set_tenant_id_on_connection

        with pg_tenants_connection() as conn:
            set_bypass_tenant_rls_on_connection(conn, enabled=True)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id FROM tenant_profiles WHERE LOWER(public_slug) = %s LIMIT 1",
                    (slug_key,),
                )
                row = cur.fetchone()
                if not row:
                    cur.execute(
                        """
                        SELECT tenant_id
                        FROM tenant_config
                        WHERE LOWER(params_json->>'public_slug') = %s
                        LIMIT 1
                        """,
                        (slug_key,),
                    )
                    row = cur.fetchone()
                if not row:
                    return None
                tenant_id = int(row.get("tenant_id") if hasattr(row, "get") else row[0])

            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT practitioner_name, cabinet_name, specialty, phone, email, address_line, postal_code, city,
                           website_url, languages_json, accepts_new_patients, practitioner_photo_url, public_slug
                    FROM tenant_profiles
                    WHERE tenant_id = %s
                    """,
                    (tenant_id,),
                )
                profile = _parse_profile_row(cur.fetchone())

                cur.execute(
                    "SELECT params_json FROM tenant_config WHERE tenant_id = %s",
                    (tenant_id,),
                )
                params_row = cur.fetchone()
                params = _parse_params_json(params_row.get("params_json") if params_row else None)

                cur.execute(
                    """
                    SELECT assistant_name, welcome_message, documents_to_bring, access_instructions,
                           payment_methods, parking_info, pmr_access, sensitive_medical_instruction,
                           escalation_instruction, human_handoff_instruction, faq_items_json
                    FROM tenant_assistant_settings
                    WHERE tenant_id = %s
                    """,
                    (tenant_id,),
                )
                assistant = _parse_assistant_row(cur.fetchone())

                cur.execute(
                    """
                    SELECT id::text, label, duration_minutes, description, enabled, allowed_for_new_patients
                    FROM tenant_appointment_reasons
                    WHERE tenant_id = %s
                    ORDER BY created_at ASC
                    """,
                    (tenant_id,),
                )
                reasons = [
                    {
                        "id": r.get("id"),
                        "label": r.get("label") or "",
                        "duration_minutes": int(r.get("duration_minutes") or 30),
                        "description": r.get("description") or "",
                        "enabled": bool(r.get("enabled", True)),
                        "allowed_for_new_patients": bool(r.get("allowed_for_new_patients", True)),
                    }
                    for r in (cur.fetchall() or [])
                    if str(r.get("label") or "").strip()
                ]

                cur.execute(
                    """
                    SELECT day_of_week, is_open, morning_start, morning_end, afternoon_start, afternoon_end
                    FROM tenant_opening_hours
                    WHERE tenant_id = %s
                    ORDER BY CASE day_of_week
                        WHEN 'monday' THEN 1
                        WHEN 'tuesday' THEN 2
                        WHEN 'wednesday' THEN 3
                        WHEN 'thursday' THEN 4
                        WHEN 'friday' THEN 5
                        WHEN 'saturday' THEN 6
                        WHEN 'sunday' THEN 7
                        ELSE 99 END
                    """,
                    (tenant_id,),
                )
                opening_hours = [
                    {
                        "day": r.get("day_of_week"),
                        "is_open": bool(r.get("is_open")),
                        "morning_start": r.get("morning_start") or "",
                        "morning_end": r.get("morning_end") or "",
                        "afternoon_start": r.get("afternoon_start") or "",
                        "afternoon_end": r.get("afternoon_end") or "",
                    }
                    for r in (cur.fetchall() or [])
                ]

        if not profile and params:
            profile = {
                "practitioner_name": params.get("practitioner_name") or params.get("primary_practitioner_name") or "",
                "cabinet_name": params.get("business_name") or "",
                "specialty": params.get("specialty_label") or params.get("profession") or "",
                "phone": params.get("phone_number") or "",
                "email": params.get("contact_email") or "",
                "address_line": params.get("address_line1") or params.get("address") or "",
                "postal_code": params.get("postal_code") or "",
                "city": params.get("city") or "",
                "website_url": params.get("website_url") or "",
                "languages": params.get("languages") or [],
                "accepts_new_patients": params.get("accepts_new_patients", True),
                "practitioner_photo_url": params.get("practitioner_photo_url") or "",
            }

        return {
            "tenant_id": tenant_id,
            "profile": profile,
            "params": params,
            "assistant": assistant,
            "reasons": reasons,
            "opening_hours": opening_hours,
        }
    except Exception as e:
        logger.debug("fetch_public_practitioner_bundle_by_slug slug=%s err=%s", slug_key[:80], e)
        return None


def get_profile(tenant_id: int) -> Optional[Dict[str, Any]]:
    if not _pg_url():
        return None
    try:
        with pg_tenants_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT practitioner_name, cabinet_name, specialty, phone, email, address_line, postal_code, city,
                           website_url, languages_json, accepts_new_patients, practitioner_photo_url, public_slug
                    FROM tenant_profiles
                    WHERE tenant_id = %s
                    """,
                    (tenant_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                langs = row.get("languages_json")
                if isinstance(langs, str):
                    try:
                        langs = json.loads(langs)
                    except Exception:
                        langs = []
                if not isinstance(langs, list):
                    langs = []
                return {
                    "practitioner_name": row.get("practitioner_name") or "",
                    "cabinet_name": row.get("cabinet_name") or "",
                    "specialty": row.get("specialty") or "",
                    "phone": row.get("phone") or "",
                    "email": row.get("email") or "",
                    "address_line": row.get("address_line") or "",
                    "postal_code": row.get("postal_code") or "",
                    "city": row.get("city") or "",
                    "website_url": row.get("website_url") or "",
                    "languages": [str(v).strip() for v in langs if str(v).strip()],
                    "accepts_new_patients": bool(row.get("accepts_new_patients", True)),
                    "practitioner_photo_url": row.get("practitioner_photo_url") or "",
                    "public_slug": row.get("public_slug") or "",
                }
    except Exception as e:
        logger.debug("get_profile failed tenant_id=%s err=%s", tenant_id, e)
        return None


def upsert_profile(tenant_id: int, payload: Dict[str, Any]) -> bool:
    if not _pg_url():
        return False
    try:
        with pg_tenants_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tenant_profiles (
                        tenant_id, practitioner_name, cabinet_name, specialty, phone, email, address_line, postal_code, city,
                        website_url, languages_json, accepts_new_patients, practitioner_photo_url, public_slug, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, now())
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        practitioner_name = COALESCE(EXCLUDED.practitioner_name, tenant_profiles.practitioner_name),
                        cabinet_name = COALESCE(EXCLUDED.cabinet_name, tenant_profiles.cabinet_name),
                        specialty = COALESCE(EXCLUDED.specialty, tenant_profiles.specialty),
                        phone = COALESCE(EXCLUDED.phone, tenant_profiles.phone),
                        email = COALESCE(EXCLUDED.email, tenant_profiles.email),
                        address_line = COALESCE(EXCLUDED.address_line, tenant_profiles.address_line),
                        postal_code = COALESCE(EXCLUDED.postal_code, tenant_profiles.postal_code),
                        city = COALESCE(EXCLUDED.city, tenant_profiles.city),
                        website_url = COALESCE(EXCLUDED.website_url, tenant_profiles.website_url),
                        languages_json = COALESCE(EXCLUDED.languages_json, tenant_profiles.languages_json),
                        accepts_new_patients = COALESCE(EXCLUDED.accepts_new_patients, tenant_profiles.accepts_new_patients),
                        practitioner_photo_url = COALESCE(EXCLUDED.practitioner_photo_url, tenant_profiles.practitioner_photo_url),
                        public_slug = COALESCE(EXCLUDED.public_slug, tenant_profiles.public_slug),
                        updated_at = now()
                    """,
                    (
                        tenant_id,
                        payload.get("practitioner_name"),
                        payload.get("cabinet_name"),
                        payload.get("specialty"),
                        payload.get("phone"),
                        payload.get("email"),
                        payload.get("address_line"),
                        payload.get("postal_code"),
                        payload.get("city"),
                        payload.get("website_url"),
                        _jsonable(payload.get("languages")),
                        payload.get("accepts_new_patients"),
                        payload.get("practitioner_photo_url"),
                        payload.get("public_slug"),
                    ),
                )
            conn.commit()
            return True
    except Exception as e:
        logger.debug("upsert_profile failed tenant_id=%s err=%s", tenant_id, e)
        return False


def get_opening_hours(tenant_id: int) -> Optional[List[Dict[str, Any]]]:
    if not _pg_url():
        return None
    try:
        with pg_tenants_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT day_of_week, is_open, morning_start, morning_end, afternoon_start, afternoon_end
                    FROM tenant_opening_hours
                    WHERE tenant_id = %s
                    ORDER BY CASE day_of_week
                        WHEN 'monday' THEN 1
                        WHEN 'tuesday' THEN 2
                        WHEN 'wednesday' THEN 3
                        WHEN 'thursday' THEN 4
                        WHEN 'friday' THEN 5
                        WHEN 'saturday' THEN 6
                        WHEN 'sunday' THEN 7
                        ELSE 99 END
                    """,
                    (tenant_id,),
                )
                rows = cur.fetchall() or []
                if not rows:
                    return None
                return [
                    {
                        "day": row.get("day_of_week"),
                        "is_open": bool(row.get("is_open")),
                        "morning_start": row.get("morning_start") or "",
                        "morning_end": row.get("morning_end") or "",
                        "afternoon_start": row.get("afternoon_start") or "",
                        "afternoon_end": row.get("afternoon_end") or "",
                    }
                    for row in rows
                ]
    except Exception as e:
        logger.debug("get_opening_hours failed tenant_id=%s err=%s", tenant_id, e)
        return None


def replace_opening_hours(tenant_id: int, opening_hours: List[Dict[str, Any]]) -> bool:
    if not _pg_url():
        return False
    try:
        with pg_tenants_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant_opening_hours WHERE tenant_id = %s", (tenant_id,))
                for row in opening_hours:
                    cur.execute(
                        """
                        INSERT INTO tenant_opening_hours (
                            tenant_id, day_of_week, is_open, morning_start, morning_end, afternoon_start, afternoon_end, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                        """,
                        (
                            tenant_id,
                            row.get("day"),
                            bool(row.get("is_open")),
                            row.get("morning_start") or "",
                            row.get("morning_end") or "",
                            row.get("afternoon_start") or "",
                            row.get("afternoon_end") or "",
                        ),
                    )
            conn.commit()
            return True
    except Exception as e:
        logger.debug("replace_opening_hours failed tenant_id=%s err=%s", tenant_id, e)
        return False


def get_availability_settings(tenant_id: int) -> Optional[Dict[str, Any]]:
    if not _pg_url():
        return None
    try:
        with pg_tenants_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT temporary_closure_enabled, temporary_closure_start, temporary_closure_end, temporary_closure_message
                    FROM tenant_availability_settings
                    WHERE tenant_id = %s
                    """,
                    (tenant_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "temporary_closure_enabled": bool(row.get("temporary_closure_enabled")),
                    "temporary_closure_start": row.get("temporary_closure_start") or "",
                    "temporary_closure_end": row.get("temporary_closure_end") or "",
                    "temporary_closure_message": row.get("temporary_closure_message") or "",
                }
    except Exception as e:
        logger.debug("get_availability_settings failed tenant_id=%s err=%s", tenant_id, e)
        return None


def upsert_availability_settings(tenant_id: int, payload: Dict[str, Any]) -> bool:
    if not _pg_url():
        return False
    try:
        with pg_tenants_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tenant_availability_settings (
                        tenant_id, temporary_closure_enabled, temporary_closure_start, temporary_closure_end, temporary_closure_message, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, now())
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        temporary_closure_enabled = COALESCE(EXCLUDED.temporary_closure_enabled, tenant_availability_settings.temporary_closure_enabled),
                        temporary_closure_start = COALESCE(EXCLUDED.temporary_closure_start, tenant_availability_settings.temporary_closure_start),
                        temporary_closure_end = COALESCE(EXCLUDED.temporary_closure_end, tenant_availability_settings.temporary_closure_end),
                        temporary_closure_message = COALESCE(EXCLUDED.temporary_closure_message, tenant_availability_settings.temporary_closure_message),
                        updated_at = now()
                    """,
                    (
                        tenant_id,
                        payload.get("temporary_closure_enabled"),
                        payload.get("temporary_closure_start"),
                        payload.get("temporary_closure_end"),
                        payload.get("temporary_closure_message"),
                    ),
                )
            conn.commit()
            return True
    except Exception as e:
        logger.debug("upsert_availability_settings failed tenant_id=%s err=%s", tenant_id, e)
        return False


def get_booking_rules(tenant_id: int) -> Optional[Dict[str, Any]]:
    if not _pg_url():
        return None
    try:
        with pg_tenants_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT default_appointment_duration_minutes, minimum_booking_notice_hours, accepts_new_patients,
                           appointment_reschedule_allowed, appointment_reschedule_notice_hours,
                           appointment_cancel_allowed, appointment_cancel_notice_hours, emergency_instruction,
                           new_patient_instruction, booking_notes
                    FROM tenant_booking_rules
                    WHERE tenant_id = %s
                    """,
                    (tenant_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "default_appointment_duration_minutes": int(row.get("default_appointment_duration_minutes") or 30),
                    "minimum_booking_notice_hours": int(row.get("minimum_booking_notice_hours") or 24),
                    "accepts_new_patients": bool(row.get("accepts_new_patients", True)),
                    "appointment_reschedule_allowed": bool(row.get("appointment_reschedule_allowed", True)),
                    "appointment_reschedule_notice_hours": int(row.get("appointment_reschedule_notice_hours") or 24),
                    "appointment_cancel_allowed": bool(row.get("appointment_cancel_allowed", True)),
                    "appointment_cancel_notice_hours": int(row.get("appointment_cancel_notice_hours") or 24),
                    "emergency_instruction": row.get("emergency_instruction") or "",
                    "new_patient_instruction": row.get("new_patient_instruction") or "",
                    "booking_notes": row.get("booking_notes") or "",
                }
    except Exception as e:
        logger.debug("get_booking_rules failed tenant_id=%s err=%s", tenant_id, e)
        return None


def upsert_booking_rules(tenant_id: int, payload: Dict[str, Any]) -> bool:
    if not _pg_url():
        return False
    try:
        with pg_tenants_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tenant_booking_rules (
                        tenant_id, default_appointment_duration_minutes, minimum_booking_notice_hours, accepts_new_patients,
                        appointment_reschedule_allowed, appointment_reschedule_notice_hours,
                        appointment_cancel_allowed, appointment_cancel_notice_hours,
                        emergency_instruction, new_patient_instruction, booking_notes, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        default_appointment_duration_minutes = COALESCE(EXCLUDED.default_appointment_duration_minutes, tenant_booking_rules.default_appointment_duration_minutes),
                        minimum_booking_notice_hours = COALESCE(EXCLUDED.minimum_booking_notice_hours, tenant_booking_rules.minimum_booking_notice_hours),
                        accepts_new_patients = COALESCE(EXCLUDED.accepts_new_patients, tenant_booking_rules.accepts_new_patients),
                        appointment_reschedule_allowed = COALESCE(EXCLUDED.appointment_reschedule_allowed, tenant_booking_rules.appointment_reschedule_allowed),
                        appointment_reschedule_notice_hours = COALESCE(EXCLUDED.appointment_reschedule_notice_hours, tenant_booking_rules.appointment_reschedule_notice_hours),
                        appointment_cancel_allowed = COALESCE(EXCLUDED.appointment_cancel_allowed, tenant_booking_rules.appointment_cancel_allowed),
                        appointment_cancel_notice_hours = COALESCE(EXCLUDED.appointment_cancel_notice_hours, tenant_booking_rules.appointment_cancel_notice_hours),
                        emergency_instruction = COALESCE(EXCLUDED.emergency_instruction, tenant_booking_rules.emergency_instruction),
                        new_patient_instruction = COALESCE(EXCLUDED.new_patient_instruction, tenant_booking_rules.new_patient_instruction),
                        booking_notes = COALESCE(EXCLUDED.booking_notes, tenant_booking_rules.booking_notes),
                        updated_at = now()
                    """,
                    (
                        tenant_id,
                        payload.get("default_appointment_duration_minutes"),
                        payload.get("minimum_booking_notice_hours"),
                        payload.get("accepts_new_patients"),
                        payload.get("appointment_reschedule_allowed"),
                        payload.get("appointment_reschedule_notice_hours"),
                        payload.get("appointment_cancel_allowed"),
                        payload.get("appointment_cancel_notice_hours"),
                        payload.get("emergency_instruction"),
                        payload.get("new_patient_instruction"),
                        payload.get("booking_notes"),
                    ),
                )
            conn.commit()
            return True
    except Exception as e:
        logger.debug("upsert_booking_rules failed tenant_id=%s err=%s", tenant_id, e)
        return False


def list_appointment_reasons(tenant_id: int) -> Optional[List[Dict[str, Any]]]:
    if not _pg_url():
        return None
    try:
        with pg_tenants_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, label, duration_minutes, description, enabled, allowed_for_new_patients
                    FROM tenant_appointment_reasons
                    WHERE tenant_id = %s
                    ORDER BY created_at ASC
                    """,
                    (tenant_id,),
                )
                rows = cur.fetchall() or []
                return [
                    {
                        "id": row.get("id"),
                        "label": row.get("label") or "",
                        "duration_minutes": int(row.get("duration_minutes") or 30),
                        "description": row.get("description") or "",
                        "enabled": bool(row.get("enabled", True)),
                        "allowed_for_new_patients": bool(row.get("allowed_for_new_patients", True)),
                    }
                    for row in rows
                    if str(row.get("label") or "").strip()
                ]
    except Exception as e:
        logger.debug("list_appointment_reasons failed tenant_id=%s err=%s", tenant_id, e)
        return None


def create_appointment_reason(tenant_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _pg_url():
        return None
    reason_id = str(payload.get("id") or uuid4())
    try:
        with pg_tenants_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tenant_appointment_reasons (
                        id, tenant_id, label, duration_minutes, description, enabled, allowed_for_new_patients, created_at, updated_at
                    )
                    VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, now(), now())
                    RETURNING id::text, label, duration_minutes, description, enabled, allowed_for_new_patients
                    """,
                    (
                        reason_id,
                        tenant_id,
                        payload.get("label"),
                        int(payload.get("duration_minutes") or 30),
                        payload.get("description") or "",
                        bool(payload.get("enabled", True)),
                        bool(payload.get("allowed_for_new_patients", True)),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            if not row:
                return None
            return {
                "id": row.get("id"),
                "label": row.get("label") or "",
                "duration_minutes": int(row.get("duration_minutes") or 30),
                "description": row.get("description") or "",
                "enabled": bool(row.get("enabled", True)),
                "allowed_for_new_patients": bool(row.get("allowed_for_new_patients", True)),
            }
    except Exception as e:
        logger.debug("create_appointment_reason failed tenant_id=%s err=%s", tenant_id, e)
        return None


def update_appointment_reason(tenant_id: int, reason_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _pg_url():
        return None
    fields = []
    values = []
    for key in ("label", "duration_minutes", "description", "enabled", "allowed_for_new_patients"):
        if key in payload:
            fields.append(f"{key} = %s")
            if key == "duration_minutes":
                values.append(int(payload[key]))
            elif key in ("enabled", "allowed_for_new_patients"):
                values.append(bool(payload[key]))
            else:
                values.append(payload[key])
    if not fields:
        return None
    try:
        with pg_tenants_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE tenant_appointment_reasons
                    SET {", ".join(fields)}, updated_at = now()
                    WHERE tenant_id = %s AND id = %s::uuid
                    RETURNING id::text, label, duration_minutes, description, enabled, allowed_for_new_patients
                    """,
                    (*values, tenant_id, reason_id),
                )
                row = cur.fetchone()
            conn.commit()
            if not row:
                return None
            return {
                "id": row.get("id"),
                "label": row.get("label") or "",
                "duration_minutes": int(row.get("duration_minutes") or 30),
                "description": row.get("description") or "",
                "enabled": bool(row.get("enabled", True)),
                "allowed_for_new_patients": bool(row.get("allowed_for_new_patients", True)),
            }
    except Exception as e:
        logger.debug("update_appointment_reason failed tenant_id=%s err=%s", tenant_id, e)
        return None


def disable_appointment_reason(tenant_id: int, reason_id: str) -> bool:
    updated = update_appointment_reason(tenant_id, reason_id, {"enabled": False})
    return bool(updated)


def get_assistant_settings(tenant_id: int) -> Optional[Dict[str, Any]]:
    if not _pg_url():
        return None
    try:
        with pg_tenants_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT assistant_name, welcome_message, documents_to_bring, access_instructions,
                           payment_methods, parking_info, pmr_access, sensitive_medical_instruction,
                           escalation_instruction, human_handoff_instruction, faq_items_json
                    FROM tenant_assistant_settings
                    WHERE tenant_id = %s
                    """,
                    (tenant_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                faq_items = row.get("faq_items_json")
                if isinstance(faq_items, str):
                    try:
                        faq_items = json.loads(faq_items)
                    except Exception:
                        faq_items = []
                if not isinstance(faq_items, list):
                    faq_items = []
                return {
                    "assistant_name": row.get("assistant_name") or "Clara",
                    "welcome_message": row.get("welcome_message") or "",
                    "documents_to_bring": row.get("documents_to_bring") or "",
                    "access_instructions": row.get("access_instructions") or "",
                    "payment_methods": row.get("payment_methods") or "",
                    "parking_info": row.get("parking_info") or "",
                    "pmr_access": row.get("pmr_access") or "",
                    "sensitive_medical_instruction": row.get("sensitive_medical_instruction") or "",
                    "escalation_instruction": row.get("escalation_instruction") or "",
                    "human_handoff_instruction": row.get("human_handoff_instruction") or "",
                    "faq_items": faq_items,
                }
    except Exception as e:
        logger.debug("get_assistant_settings failed tenant_id=%s err=%s", tenant_id, e)
        return None


def upsert_assistant_settings(tenant_id: int, payload: Dict[str, Any]) -> bool:
    if not _pg_url():
        return False
    try:
        with pg_tenants_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tenant_assistant_settings (
                        tenant_id, assistant_name, welcome_message, documents_to_bring, access_instructions,
                        payment_methods, parking_info, pmr_access, sensitive_medical_instruction,
                        escalation_instruction, human_handoff_instruction, faq_items_json, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, now())
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        assistant_name = COALESCE(EXCLUDED.assistant_name, tenant_assistant_settings.assistant_name),
                        welcome_message = COALESCE(EXCLUDED.welcome_message, tenant_assistant_settings.welcome_message),
                        documents_to_bring = COALESCE(EXCLUDED.documents_to_bring, tenant_assistant_settings.documents_to_bring),
                        access_instructions = COALESCE(EXCLUDED.access_instructions, tenant_assistant_settings.access_instructions),
                        payment_methods = COALESCE(EXCLUDED.payment_methods, tenant_assistant_settings.payment_methods),
                        parking_info = COALESCE(EXCLUDED.parking_info, tenant_assistant_settings.parking_info),
                        pmr_access = COALESCE(EXCLUDED.pmr_access, tenant_assistant_settings.pmr_access),
                        sensitive_medical_instruction = COALESCE(EXCLUDED.sensitive_medical_instruction, tenant_assistant_settings.sensitive_medical_instruction),
                        escalation_instruction = COALESCE(EXCLUDED.escalation_instruction, tenant_assistant_settings.escalation_instruction),
                        human_handoff_instruction = COALESCE(EXCLUDED.human_handoff_instruction, tenant_assistant_settings.human_handoff_instruction),
                        faq_items_json = COALESCE(EXCLUDED.faq_items_json, tenant_assistant_settings.faq_items_json),
                        updated_at = now()
                    """,
                    (
                        tenant_id,
                        payload.get("assistant_name"),
                        payload.get("welcome_message"),
                        payload.get("documents_to_bring"),
                        payload.get("access_instructions"),
                        payload.get("payment_methods"),
                        payload.get("parking_info"),
                        payload.get("pmr_access"),
                        payload.get("sensitive_medical_instruction"),
                        payload.get("escalation_instruction"),
                        payload.get("human_handoff_instruction"),
                        _jsonable(payload.get("faq_items")),
                    ),
                )
            conn.commit()
            return True
    except Exception as e:
        logger.debug("upsert_assistant_settings failed tenant_id=%s err=%s", tenant_id, e)
        return False


def _non_empty_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def canonicalize_cabinet_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aligne les clés du wizard admin / anciennes créations avec params_json
    consommés par GET/PATCH /api/tenant/profile.
    """
    if not isinstance(params, dict):
        return {}
    out = dict(params)
    alias_map = (
        ("primary_practitioner_name", "practitioner_name"),
        ("current_phone_number", "phone_number"),
        ("address", "address_line1"),
        ("profession", "specialty_label"),
    )
    for src, dst in alias_map:
        src_val = _non_empty_str(out.get(src))
        dst_val = _non_empty_str(out.get(dst))
        if src_val and not dst_val:
            out[dst] = src_val
    line1 = _non_empty_str(out.get("address_line1"))
    line_alt = _non_empty_str(out.get("address_line"))
    if line1 and not line_alt:
        out["address_line"] = line1
    elif line_alt and not line1:
        out["address_line1"] = line_alt
    return out


def sync_normalized_from_params(tenant_id: int, params: Dict[str, Any]) -> None:
    if not isinstance(params, dict) or not params:
        return
    params = canonicalize_cabinet_params(params)
    profile_payload = {
        "practitioner_name": params.get("practitioner_name"),
        "cabinet_name": params.get("business_name"),
        "specialty": params.get("specialty_label"),
        "phone": params.get("phone_number"),
        "email": params.get("contact_email"),
        "address_line": params.get("address_line1"),
        "postal_code": params.get("postal_code"),
        "city": params.get("city"),
        "website_url": params.get("website_url"),
        "languages": params.get("languages"),
        "accepts_new_patients": params.get("accepts_new_patients"),
        "practitioner_photo_url": params.get("practitioner_photo_url"),
        "public_slug": params.get("public_slug"),
    }
    if any(v is not None for v in profile_payload.values()):
        upsert_profile(tenant_id, profile_payload)

    availability_payload = {
        "temporary_closure_enabled": params.get("temporary_closure_enabled"),
        "temporary_closure_start": params.get("temporary_closure_start"),
        "temporary_closure_end": params.get("temporary_closure_end"),
        "temporary_closure_message": params.get("temporary_closure_message"),
    }
    if any(v is not None for v in availability_payload.values()):
        upsert_availability_settings(tenant_id, availability_payload)

    booking_payload = {
        "default_appointment_duration_minutes": params.get("default_appointment_duration_minutes"),
        "minimum_booking_notice_hours": params.get("minimum_booking_notice_hours"),
        "accepts_new_patients": params.get("accepts_new_patients"),
        "appointment_reschedule_allowed": params.get("appointment_reschedule_allowed"),
        "appointment_reschedule_notice_hours": params.get("appointment_reschedule_notice_hours"),
        "appointment_cancel_allowed": params.get("appointment_cancel_allowed"),
        "appointment_cancel_notice_hours": params.get("appointment_cancel_notice_hours"),
        "emergency_instruction": params.get("emergency_instruction"),
        "new_patient_instruction": params.get("new_patient_instruction"),
        "booking_notes": params.get("booking_notes"),
    }
    if any(v is not None for v in booking_payload.values()):
        upsert_booking_rules(tenant_id, booking_payload)

    assistant_payload = {
        "assistant_name": params.get("assistant_name"),
        "welcome_message": params.get("welcome_message"),
        "documents_to_bring": params.get("documents_to_bring"),
        "access_instructions": params.get("access_instructions"),
        "payment_methods": params.get("payment_methods"),
        "parking_info": params.get("parking_info"),
        "pmr_access": params.get("pmr_access"),
        "sensitive_medical_instruction": params.get("sensitive_medical_instruction"),
        "escalation_instruction": params.get("escalation_instruction"),
        "human_handoff_instruction": params.get("human_handoff_instruction"),
        "faq_items": params.get("faq_items_json"),
    }
    if any(v is not None for v in assistant_payload.values()):
        upsert_assistant_settings(tenant_id, assistant_payload)

    reasons = params.get("appointment_reasons_json")
    if isinstance(reasons, list):
        current = list_appointment_reasons(tenant_id) or []
        existing_ids = {item.get("id") for item in current}
        for item in reasons:
            if not isinstance(item, dict):
                continue
            rid = str(item.get("id") or uuid4())
            payload = {
                "id": rid,
                "label": item.get("label") or "",
                "duration_minutes": int(item.get("duration_minutes") or 30),
                "description": item.get("description") or "",
                "enabled": bool(item.get("enabled", True)),
                "allowed_for_new_patients": bool(item.get("allowed_for_new_patients", True)),
            }
            if rid in existing_ids:
                update_appointment_reason(tenant_id, rid, payload)
            else:
                create_appointment_reason(tenant_id, payload)


def sync_opening_hours_from_booking_rules(tenant_id: int, rules: Dict[str, Any]) -> None:
    if not isinstance(rules, dict):
        return
    booking_days = rules.get("booking_days")
    if isinstance(booking_days, str):
        try:
            booking_days = json.loads(booking_days)
        except Exception:
            booking_days = []
    if not isinstance(booking_days, list):
        booking_days = []
    open_idx = {int(v) for v in booking_days if str(v).strip().isdigit()}
    start = int(rules.get("booking_start_hour") or 9)
    end = int(rules.get("booking_end_hour") or 18)
    rows = []
    for idx, day in enumerate(DAY_KEYS):
        is_open = idx in open_idx
        rows.append(
            {
                "day": day,
                "is_open": is_open,
                "morning_start": f"{start:02d}:00" if is_open else "",
                "morning_end": "12:30" if is_open else "",
                "afternoon_start": "14:00" if is_open else "",
                "afternoon_end": f"{end:02d}:00" if is_open else "",
            }
        )
    replace_opening_hours(tenant_id, rows)
