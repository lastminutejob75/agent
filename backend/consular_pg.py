"""Accès PostgreSQL du domaine consulaire."""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from backend.pg_pool import pg_connection
from backend.pg_tenant_context import (
    set_post_id_on_connection,
    set_tenant_id_on_connection,
)
from backend.services.counter_schedule import load_post_counter_slots


def _resolve_post(conn: Any, legacy_tenant_id: int) -> Optional[dict[str, Any]]:
    """Résout le poste lié au compte existant puis active son contexte RLS."""
    set_tenant_id_on_connection(conn, legacy_tenant_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT post_id, name, country_code, host_country_code,
                   reference_prefix, timezone, status
            FROM posts
            WHERE legacy_tenant_id = %s
            """,
            (legacy_tenant_id,),
        )
        post = cur.fetchone()
    if not post:
        return None
    set_post_id_on_connection(conn, post["post_id"])
    return dict(post)


def get_post_for_account(legacy_tenant_id: int) -> Optional[dict[str, Any]]:
    with pg_connection() as conn:
        return _resolve_post(conn, legacy_tenant_id)


def list_applications(
    legacy_tenant_id: int,
    *,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    with pg_connection() as conn:
        post = _resolve_post(conn, legacy_tenant_id)
        if not post:
            return []
        query = """
            SELECT id, reference, channel, lang, purpose, visa_category,
                   reclassified_from, applicant_name, applicant_phone,
                   residence, travel_window, duration_days, passport_ok,
                   host_nationality, fee_exempt, is_minor,
                   is_first_application, schengen_history, previous_refusal,
                   status, created_at, qualified_at
            FROM applications
        """
        params: list[Any] = []
        if status:
            query += " WHERE status = %s"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            return [dict(row) for row in cur.fetchall()]


def get_application(
    legacy_tenant_id: int,
    application_id: UUID,
) -> Optional[dict[str, Any]]:
    with pg_connection() as conn:
        post = _resolve_post(conn, legacy_tenant_id)
        if not post:
            return None
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, reference, channel, lang, purpose, visa_category,
                       reclassified_from, applicant_name, applicant_phone,
                       residence, travel_window, duration_days, passport_ok,
                       host_nationality, fee_exempt, is_minor,
                       is_first_application, schengen_history, previous_refusal,
                       status, original_transcript, translated_transcript_fr,
                       translated_transcript_bg, created_at, qualified_at
                FROM applications
                WHERE id = %s
                """,
                (application_id,),
            )
            application = cur.fetchone()
            if not application:
                return None
            cur.execute(
                """
                SELECT doc_key, state, is_blocking, updated_at
                FROM application_documents
                WHERE application_id = %s
                ORDER BY doc_key
                """,
                (application_id,),
            )
            documents = [dict(row) for row in cur.fetchall()]
        result = dict(application)
        result["documents"] = documents
        return result


def list_counter_slots(
    legacy_tenant_id: int,
    *,
    visa_category: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Créneaux internes réservés au dashboard authentifié du poste."""
    with pg_connection() as conn:
        post = _resolve_post(conn, legacy_tenant_id)
        if not post:
            return []
        slots = load_post_counter_slots(
            conn,
            UUID(str(post["post_id"])),
            visa_category=visa_category,
            limit=limit,
        )
        return [
            {
                "post_id": str(slot.post_id),
                "slot_start": slot.slot_start,
                "slot_end": slot.slot_end,
                "visa_category_filter": slot.visa_category_filter,
            }
            for slot in slots
        ]
