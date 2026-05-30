"""Questionnaires patient V2 — templates typés, tokens usage unique, conformité HDS."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.db import get_cabinet_client_by_phone, get_conn, insert_patient_note
from backend.patient_v2_db import (
    _json_dump,
    _json_load,
    _new_id,
    ensure_patient_v2_schema,
    exec_pg,
    fetch_all_pg,
    fetch_one_pg,
    normalize_patient_phone,
)
from backend.services.patient_summary import invalidate_patient_summary
from backend.tenant_capabilities import is_hds_active

logger = logging.getLogger(__name__)

TOKEN_TTL_DAYS = 7

ADMIN_TYPE_DEMANDE_OPTIONS = [
    "premiere_consultation",
    "suivi",
    "renouvellement",
    "recuperation_document",
    "question_administrative",
    "deplacement_rdv",
    "autre_administratif",
]

DEFAULT_ADMIN_TEMPLATE_FIELDS: List[Dict[str, Any]] = [
    {
        "field_id": "type_demande",
        "label": "Type de demande",
        "type": "select",
        "sensitivity": "admin",
        "required": True,
        "options": ADMIN_TYPE_DEMANDE_OPTIONS,
    },
    {
        "field_id": "deja_patient",
        "label": "Déjà patient de ce cabinet",
        "type": "boolean",
        "sensitivity": "admin",
        "required": True,
    },
    {
        "field_id": "medecin_traitant",
        "label": "Médecin traitant",
        "type": "text",
        "sensitivity": "admin",
        "required": False,
        "constrained": True,
    },
    {
        "field_id": "besoin_rappel",
        "label": "Souhaite être rappelé",
        "type": "boolean",
        "sensitivity": "admin",
        "required": False,
    },
    {
        "field_id": "consentement",
        "label": "J'accepte que ces informations soient transmises au cabinet",
        "type": "boolean",
        "sensitivity": "admin",
        "required": True,
    },
]


def default_admin_template() -> Dict[str, Any]:
    return {
        "name": "Préparer ma demande",
        "type": "admin",
        "description": "Questionnaire administratif (sans donnée de santé).",
        "sections_json": DEFAULT_ADMIN_TEMPLATE_FIELDS,
        "is_default": True,
        "is_health": False,
    }


def validate_template_fields(sections_json: List[Dict[str, Any]], *, hds_active: bool) -> None:
    if not isinstance(sections_json, list) or not sections_json:
        raise ValueError("Le template doit contenir au moins un champ.")
    for field in sections_json:
        ftype = str(field.get("type") or "")
        sensitivity = str(field.get("sensitivity") or "admin")
        if not hds_active:
            if ftype == "file":
                raise ValueError("Upload interdit sans HDS.")
            if sensitivity == "health":
                raise ValueError("Champ santé interdit sans HDS.")
            if ftype == "text" and not field.get("constrained") and ftype not in ("select", "boolean", "date", "phone", "email"):
                raise ValueError(f"Champ texte libre interdit en mode non-HDS : {field.get('field_id')}")


def compute_response_is_health(template: Dict[str, Any], answers: dict, *, has_uploads: bool) -> bool:
    if has_uploads:
        return True
    for field in template.get("sections_json") or []:
        if field.get("sensitivity") == "health":
            return True
        if field.get("type") == "text" and not field.get("constrained"):
            fid = field.get("field_id")
            if fid and str(answers.get(fid) or "").strip():
                return True
    return False


def validate_answers_against_template(
    template: Dict[str, Any],
    answers: dict,
    *,
    hds_active: bool,
    has_uploads: bool = False,
) -> Dict[str, Any]:
    sections = template.get("sections_json") or []
    clean: Dict[str, Any] = {}
    allowed_ids = {f.get("field_id") for f in sections}
    for field in sections:
        fid = field.get("field_id")
        if not fid:
            continue
        raw = answers.get(fid)
        required = bool(field.get("required"))
        ftype = str(field.get("type") or "text")
        if raw is None or str(raw).strip() == "":
            if required:
                raise ValueError(f"Champ requis manquant : {field.get('label') or fid}")
            continue
        if ftype == "boolean":
            clean[fid] = str(raw).lower() in ("1", "true", "yes", "oui", "on")
        elif ftype == "select":
            val = str(raw).strip()
            options = field.get("options") or []
            if options and val not in options:
                raise ValueError(f"Valeur invalide pour {field.get('label') or fid}")
            clean[fid] = val
        else:
            clean[fid] = str(raw).strip()[:2000]
    for key in answers.keys():
        if key not in allowed_ids:
            continue
    is_health = compute_response_is_health(template, clean, has_uploads=has_uploads)
    if is_health and not hds_active:
        raise ValueError("Cette réponse contient des données de santé ; soumission refusée sans HDS.")
    return clean


def ensure_default_admin_template(tenant_id: int) -> Dict[str, Any]:
    ensure_patient_v2_schema()
    existing = fetch_one_pg(
        """
        SELECT * FROM questionnaire_templates
        WHERE tenant_id = %s AND type = 'admin' AND is_default = true
        ORDER BY created_at ASC LIMIT 1
        """,
        (tenant_id,),
    )
    if existing:
        return _template_row(existing)
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT * FROM questionnaire_templates
            WHERE tenant_id = ? AND type = 'admin' AND is_default = 1
            ORDER BY created_at ASC LIMIT 1
            """,
            (tenant_id,),
        ).fetchone()
        if row:
            return _template_row(dict(row))
    finally:
        conn.close()

    tpl = default_admin_template()
    return create_template(tenant_id, tpl)


def create_template(tenant_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    ensure_patient_v2_schema()
    sections = payload.get("sections_json") or []
    hds = is_hds_active(tenant_id)
    validate_template_fields(sections, hds_active=hds)
    tpl_id = _new_id()
    row = {
        "id": tpl_id,
        "tenant_id": tenant_id,
        "name": payload.get("name") or "Questionnaire",
        "type": payload.get("type") or "admin",
        "description": payload.get("description") or "",
        "sections_json": sections,
        "is_default": bool(payload.get("is_default")),
        "is_health": bool(payload.get("is_health")),
    }
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO questionnaire_templates
            (id, tenant_id, name, type, description, sections_json, is_default, is_health)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tpl_id,
                tenant_id,
                row["name"],
                row["type"],
                row["description"],
                _json_dump(sections),
                1 if row["is_default"] else 0,
                1 if row["is_health"] else 0,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    exec_pg(
        """
        INSERT INTO questionnaire_templates
        (id, tenant_id, name, type, description, sections_json, is_default, is_health)
        VALUES (%s::uuid, %s, %s, %s, %s, %s::jsonb, %s, %s)
        """,
        (
            tpl_id,
            tenant_id,
            row["name"],
            row["type"],
            row["description"],
            _json_dump(sections),
            row["is_default"],
            row["is_health"],
        ),
    )
    return row


def _template_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "tenant_id": int(row.get("tenant_id") or 0),
        "name": row.get("name") or "",
        "type": row.get("type") or "",
        "description": row.get("description") or "",
        "sections_json": _json_load(row.get("sections_json"), []),
        "is_default": bool(row.get("is_default")),
        "is_health": bool(row.get("is_health")),
    }


def get_template(tenant_id: int, template_id: str) -> Optional[Dict[str, Any]]:
    row = fetch_one_pg(
        "SELECT * FROM questionnaire_templates WHERE tenant_id = %s AND id = %s::uuid",
        (tenant_id, template_id),
    )
    if row:
        return _template_row(row)
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT * FROM questionnaire_templates WHERE tenant_id = ? AND id = ?",
            (tenant_id, template_id),
        ).fetchone()
        return _template_row(dict(cur)) if cur else None
    finally:
        conn.close()


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_questionnaire_request(
    tenant_id: int,
    patient_phone: str,
    *,
    template_id: Optional[str] = None,
    sent_by_user_id: str = "",
    sent_to_email: str = "",
    sent_to_phone: str = "",
    appointment_id: str = "",
) -> Tuple[Dict[str, Any], str]:
    """Crée une demande de questionnaire et renvoie (request, raw_token)."""
    ensure_patient_v2_schema()
    phone = normalize_patient_phone(patient_phone)
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise ValueError("Fiche patient introuvable.")

    template = get_template(tenant_id, template_id) if template_id else ensure_default_admin_template(tenant_id)
    if not template:
        template = ensure_default_admin_template(tenant_id)

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    req_id = _new_id()
    expires = datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS)
    email = (sent_to_email or profile.get("email") or "").strip()

    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO questionnaire_requests (
                id, tenant_id, patient_phone, appointment_id, template_id, status,
                sent_by_user_id, sent_to_email, sent_to_phone, secure_token_hash,
                token_used, expires_at
            ) VALUES (?, ?, ?, ?, ?, 'sent', ?, ?, ?, ?, 0, ?)
            """,
            (
                req_id,
                tenant_id,
                phone,
                appointment_id or None,
                template["id"],
                sent_by_user_id or None,
                email or None,
                sent_to_phone or phone,
                token_hash,
                expires.isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    exec_pg(
        """
        INSERT INTO questionnaire_requests (
            id, tenant_id, patient_phone, appointment_id, template_id, status,
            sent_by_user_id, sent_to_email, sent_to_phone, secure_token_hash,
            token_used, expires_at
        ) VALUES (%s::uuid, %s, %s, %s, %s::uuid, 'sent', %s, %s, %s, %s, false, %s)
        """,
        (
            req_id,
            tenant_id,
            phone,
            appointment_id or None,
            template["id"],
            sent_by_user_id or None,
            email or None,
            sent_to_phone or phone,
            token_hash,
            expires,
        ),
    )
    invalidate_patient_summary(tenant_id, phone)
    return {
        "id": req_id,
        "tenant_id": tenant_id,
        "patient_phone": phone,
        "template_id": template["id"],
        "status": "sent",
        "sent_to_email": email,
        "expires_at": expires.isoformat(),
    }, raw_token


def resolve_token(raw_token: str) -> Optional[Dict[str, Any]]:
    ensure_patient_v2_schema()
    token_hash = _hash_token(raw_token)
    row = fetch_one_pg(
        "SELECT * FROM questionnaire_requests WHERE secure_token_hash = %s LIMIT 1",
        (token_hash,),
    )
    if not row:
        conn = get_conn()
        try:
            cur = conn.execute(
                "SELECT * FROM questionnaire_requests WHERE secure_token_hash = ? LIMIT 1",
                (token_hash,),
            ).fetchone()
            row = dict(cur) if cur else None
        finally:
            conn.close()
    if not row:
        return None
    expires = _parse_dt(row.get("expires_at"))
    if expires and expires < datetime.now(timezone.utc):
        return None
    if bool(row.get("token_used")):
        return None
    return dict(row)


def mark_request_opened(request_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE questionnaire_requests
            SET opened_at = COALESCE(opened_at, ?), status = CASE WHEN status = 'sent' THEN 'opened' ELSE status END
            WHERE id = ?
            """,
            (now, request_id),
        )
        conn.commit()
    finally:
        conn.close()
    exec_pg(
        """
        UPDATE questionnaire_requests
        SET opened_at = COALESCE(opened_at, now()),
            status = CASE WHEN status = 'sent' THEN 'opened' ELSE status END
        WHERE id = %s::uuid
        """,
        (request_id,),
    )


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _structured_summary_from_answers(template: Dict[str, Any], answers: dict) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for field in template.get("sections_json") or []:
        fid = field.get("field_id")
        if not fid:
            continue
        val = answers.get(fid)
        if val is None or val == "":
            continue
        out[fid] = {"label": field.get("label") or fid, "value": val, "type": field.get("type")}
    return out


def _questionnaire_ai_summary(answers: dict, *, is_health: bool) -> str:
    lines = []
    for key, val in answers.items():
        if val is True or val is False:
            val = "Oui" if val else "Non"
        lines.append(f"- {key}: {val}")
    if not lines:
        return ""
    if is_health:
        return "Éléments transmis (questionnaire médical) :\n" + "\n".join(lines)
    return "Demande administrative :\n" + "\n".join(lines)


def submit_questionnaire_response(
    raw_token: str,
    answers: dict,
    *,
    consent_given: bool,
    has_uploads: bool = False,
) -> Dict[str, Any]:
    req = resolve_token(raw_token)
    if not req:
        raise ValueError("Lien invalide, expiré ou déjà utilisé.")
    if not consent_given:
        raise ValueError("Consentement requis.")

    tenant_id = int(req["tenant_id"])
    phone = normalize_patient_phone(req["patient_phone"])
    template = get_template(tenant_id, str(req.get("template_id") or ""))
    if not template:
        raise ValueError("Template introuvable.")

    hds = is_hds_active(tenant_id)
    clean = validate_answers_against_template(
        template, answers, hds_active=hds, has_uploads=has_uploads
    )
    is_health = compute_response_is_health(template, clean, has_uploads=has_uploads)
    if is_health and not hds:
        raise ValueError("Soumission refusée : données de santé sans HDS.")

    response_id = _new_id()
    structured = _structured_summary_from_answers(template, clean)
    ai_summary = _questionnaire_ai_summary(clean, is_health=is_health)
    now = datetime.now(timezone.utc).isoformat()

    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO questionnaire_responses (
                id, tenant_id, questionnaire_request_id, patient_phone,
                answers_json, ai_summary, structured_summary_json, consent_given, is_health, submitted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                response_id,
                tenant_id,
                req["id"],
                phone,
                _json_dump(clean),
                ai_summary,
                _json_dump(structured),
                1 if consent_given else 0,
                1 if is_health else 0,
                now,
            ),
        )
        conn.execute(
            """
            UPDATE questionnaire_requests
            SET token_used = 1, status = 'completed', completed_at = ?, started_at = COALESCE(started_at, ?)
            WHERE id = ?
            """,
            (now, now, req["id"]),
        )
        conn.execute(
            """
            INSERT INTO patient_events (id, tenant_id, patient_phone, type, occurred_at, statut, motif, payload_json)
            VALUES (?, ?, ?, 'message', ?, 'completed', ?, ?)
            """,
            (
                _new_id(),
                tenant_id,
                phone,
                now,
                "questionnaire",
                _json_dump({"request_id": req["id"], "response_id": response_id, "is_health": is_health}),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    exec_pg(
        """
        INSERT INTO questionnaire_responses (
            id, tenant_id, questionnaire_request_id, patient_phone,
            answers_json, ai_summary, structured_summary_json, consent_given, is_health, submitted_at
        ) VALUES (%s::uuid, %s, %s::uuid, %s, %s::jsonb, %s, %s::jsonb, %s, %s, now())
        """,
        (
            response_id,
            tenant_id,
            req["id"],
            phone,
            _json_dump(clean),
            ai_summary,
            _json_dump(structured),
            consent_given,
            is_health,
        ),
    )
    exec_pg(
        """
        UPDATE questionnaire_requests
        SET token_used = true, status = 'completed', completed_at = now(),
            started_at = COALESCE(started_at, now())
        WHERE id = %s::uuid
        """,
        (req["id"],),
    )
    exec_pg(
        """
        INSERT INTO patient_events (tenant_id, patient_phone, type, occurred_at, statut, motif, payload_json)
        VALUES (%s, %s, 'message', now(), 'completed', 'questionnaire', %s::jsonb)
        """,
        (
            tenant_id,
            phone,
            _json_dump({"request_id": str(req["id"]), "response_id": response_id, "is_health": is_health}),
        ),
    )

    if not is_health:
        note_lines = [f"{k}: {v}" for k, v in clean.items()]
        insert_patient_note(
            tenant_id,
            phone,
            note_text=f"Questionnaire administratif complété\n" + "\n".join(note_lines),
            author="Questionnaire patient",
        )

    invalidate_patient_summary(tenant_id, phone)
    return {
        "response_id": response_id,
        "is_health": is_health,
        "ai_summary": ai_summary,
        "structured_summary": structured,
    }


def integrate_response(tenant_id: int, response_id: str) -> Dict[str, Any]:
    row = fetch_one_pg(
        """
        SELECT qr.*, qreq.template_id
        FROM questionnaire_responses qr
        JOIN questionnaire_requests qreq ON qreq.id = qr.questionnaire_request_id
        WHERE qr.tenant_id = %s AND qr.id = %s::uuid
        """,
        (tenant_id, response_id),
    )
    if not row:
        conn = get_conn()
        try:
            cur = conn.execute(
                """
                SELECT qr.*, qreq.template_id
                FROM questionnaire_responses qr
                JOIN questionnaire_requests qreq ON qreq.id = qr.questionnaire_request_id
                WHERE qr.tenant_id = ? AND qr.id = ?
                """,
                (tenant_id, response_id),
            ).fetchone()
            row = dict(cur) if cur else None
        finally:
            conn.close()
    if not row:
        raise ValueError("Réponse introuvable.")

    req_id = row.get("questionnaire_request_id")
    phone = normalize_patient_phone(row.get("patient_phone") or "")
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE questionnaire_requests
            SET status = 'integrated', integrated_at = ?
            WHERE id = ? AND tenant_id = ?
            """,
            (now, req_id, tenant_id),
        )
        conn.commit()
    finally:
        conn.close()
    exec_pg(
        """
        UPDATE questionnaire_requests
        SET status = 'integrated', integrated_at = now()
        WHERE id = %s::uuid AND tenant_id = %s
        """,
        (req_id, tenant_id),
    )
    invalidate_patient_summary(tenant_id, phone)
    return {"ok": True, "response_id": response_id, "status": "integrated"}


def list_patient_questionnaire_requests(tenant_id: int, patient_phone: str) -> List[Dict[str, Any]]:
    phone = normalize_patient_phone(patient_phone)
    rows = fetch_all_pg(
        """
        SELECT qreq.id, qreq.status, qreq.sent_to_email, qreq.created_at, qreq.completed_at,
               qreq.integrated_at, qreq.expires_at,
               (
                 SELECT qr.id FROM questionnaire_responses qr
                 WHERE qr.questionnaire_request_id = qreq.id
                 ORDER BY qr.submitted_at DESC LIMIT 1
               ) AS response_id
        FROM questionnaire_requests qreq
        WHERE qreq.tenant_id = %s AND qreq.patient_phone = %s
        ORDER BY qreq.created_at DESC
        LIMIT 20
        """,
        (tenant_id, phone),
    )
    if rows:
        return [dict(r) for r in rows]
    conn = get_conn()
    try:
        raw = conn.execute(
            """
            SELECT qreq.id, qreq.status, qreq.sent_to_email, qreq.created_at, qreq.completed_at,
                   qreq.integrated_at, qreq.expires_at,
                   (
                     SELECT qr.id FROM questionnaire_responses qr
                     WHERE qr.questionnaire_request_id = qreq.id
                     ORDER BY qr.submitted_at DESC LIMIT 1
                   ) AS response_id
            FROM questionnaire_requests qreq
            WHERE qreq.tenant_id = ? AND qreq.patient_phone = ?
            ORDER BY qreq.created_at DESC LIMIT 20
            """,
            (tenant_id, phone),
        ).fetchall()
        return [dict(r) for r in raw]
    finally:
        conn.close()


def public_questionnaire_payload(raw_token: str) -> Dict[str, Any]:
    req = resolve_token(raw_token)
    if not req:
        raise ValueError("Lien invalide, expiré ou déjà utilisé.")
    mark_request_opened(str(req["id"]))
    tenant_id = int(req["tenant_id"])
    phone = normalize_patient_phone(req["patient_phone"])
    profile = get_cabinet_client_by_phone(tenant_id, phone) or {}
    template = get_template(tenant_id, str(req.get("template_id") or "")) or ensure_default_admin_template(tenant_id)
    hds = is_hds_active(tenant_id)
    return {
        "tenant_id": tenant_id,
        "patient_phone": phone,
        "patient_name": profile.get("display_name") or profile.get("validated_name") or "",
        "template": {
            "id": template["id"],
            "name": template["name"],
            "description": template["description"],
            "sections_json": template["sections_json"],
            "hds_active": hds,
            "medical_upload_allowed": hds,
        },
        "request_id": str(req["id"]),
        "expires_at": str(req.get("expires_at") or ""),
    }
