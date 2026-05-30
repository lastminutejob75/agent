"""Questionnaires patient V2 — templates typés, tokens usage unique, conformité HDS."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.db import get_cabinet_client_by_phone, get_conn, insert_patient_note, update_patient_fields
from backend.patient_v2_db import (
    _json_dump,
    _json_load,
    _new_id,
    count_documents_for_request,
    ensure_patient_v2_schema,
    exec_pg,
    fetch_all_pg,
    fetch_one_pg,
    insert_patient_document_v2,
    link_documents_to_response,
    list_documents_for_request,
    list_documents_for_response,
    normalize_patient_phone,
    pg_available,
)
from backend.services.patient_document_storage import save_questionnaire_upload
from backend.services.patient_summary import invalidate_patient_summary
from backend.tenant_capabilities import is_hds_active

logger = logging.getLogger(__name__)

TOKEN_TTL_DAYS = 7


def _tenant_detail(tenant_id: int) -> Dict[str, Any]:
    try:
        from backend.tenants_pg import pg_get_tenant_full

        return pg_get_tenant_full(tenant_id) or {}
    except Exception:
        return {}


def _hds_active(tenant_id: int) -> bool:
    return is_hds_active(tenant_id, _tenant_detail(tenant_id))

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
        "field_id": "confirm_email",
        "label": "Confirmer votre email",
        "type": "email",
        "sensitivity": "admin",
        "required": False,
        "constrained": True,
    },
    {
        "field_id": "confirm_phone",
        "label": "Confirmer votre téléphone",
        "type": "phone",
        "sensitivity": "admin",
        "required": False,
        "constrained": True,
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
        "field_id": "disponibilites",
        "label": "Disponibilités préférées",
        "type": "select",
        "sensitivity": "admin",
        "required": False,
        "options": ["matin", "apres_midi", "fin_de_semaine", "semaine_prochaine", "flexible"],
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

DISPONIBILITES_LABELS = {
    "matin": "Matin",
    "apres_midi": "Après-midi",
    "fin_de_semaine": "Fin de semaine",
    "semaine_prochaine": "Semaine prochaine",
    "flexible": "Flexible",
}

TYPE_DEMANDE_LABELS = {
    "premiere_consultation": "Première consultation",
    "suivi": "Suivi",
    "renouvellement": "Renouvellement",
    "recuperation_document": "Récupération de document",
    "question_administrative": "Question administrative",
    "deplacement_rdv": "Déplacement de RDV",
    "autre_administratif": "Autre (administratif)",
}

DEFAULT_MEDICAL_TEMPLATE_FIELDS: List[Dict[str, Any]] = [
    {
        "field_id": "birth_date",
        "label": "Date de naissance",
        "type": "date",
        "sensitivity": "health",
        "required": False,
        "constrained": True,
    },
    {
        "field_id": "treating_physician_name",
        "label": "Médecin traitant",
        "type": "text",
        "sensitivity": "health",
        "required": False,
        "constrained": True,
    },
    {
        "field_id": "allergies",
        "label": "Allergies connues",
        "type": "textarea",
        "sensitivity": "health",
        "required": False,
        "constrained": False,
    },
    {
        "field_id": "current_treatments",
        "label": "Traitements en cours",
        "type": "textarea",
        "sensitivity": "health",
        "required": False,
        "constrained": False,
    },
    {
        "field_id": "medical_history",
        "label": "Antécédents médicaux",
        "type": "textarea",
        "sensitivity": "health",
        "required": False,
        "constrained": False,
    },
    {
        "field_id": "main_reason",
        "label": "Motif principal de consultation",
        "type": "textarea",
        "sensitivity": "health",
        "required": False,
        "constrained": False,
    },
    {
        "field_id": "consentement",
        "label": "J'accepte que ces informations médicales soient transmises au cabinet",
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


def default_medical_template() -> Dict[str, Any]:
    return {
        "name": "Questionnaire médical",
        "type": "medical",
        "description": "Questionnaire médical (données de santé — HDS requis).",
        "sections_json": DEFAULT_MEDICAL_TEMPLATE_FIELDS,
        "is_default": True,
        "is_health": True,
    }


def _merge_template_fields(existing: List[Dict[str, Any]], target: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ajoute les nouveaux champs du template par défaut sans écraser l'existant."""
    by_id = {str(f.get("field_id") or ""): f for f in existing if f.get("field_id")}
    merged = list(existing)
    for field in target:
        fid = str(field.get("field_id") or "")
        if fid and fid not in by_id:
            merged.append(field)
    return merged


def _upgrade_default_template_row(tenant_id: int, row: Dict[str, Any]) -> Dict[str, Any]:
    sections = _json_load(row.get("sections_json"), [])
    merged = _merge_template_fields(sections, DEFAULT_ADMIN_TEMPLATE_FIELDS)
    if merged == sections:
        return _template_row(row)
    tpl_id = str(row.get("id") or "")
    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE questionnaire_templates
            SET sections_json = ?, updated_at = datetime('now')
            WHERE tenant_id = ? AND id = ?
            """,
            (_json_dump(merged), tenant_id, tpl_id),
        )
        conn.commit()
    finally:
        conn.close()
    exec_pg(
        """
        UPDATE questionnaire_templates
        SET sections_json = %s::jsonb, updated_at = now()
        WHERE tenant_id = %s AND id = %s::uuid
        """,
        (_json_dump(merged), tenant_id, tpl_id),
    )
    row = dict(row)
    row["sections_json"] = merged
    return _template_row(row)


def _format_answer_display(field: Dict[str, Any], value: Any) -> str:
    fid = str(field.get("field_id") or "")
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    raw = str(value or "").strip()
    if field.get("type") == "select" and fid == "type_demande":
        return TYPE_DEMANDE_LABELS.get(raw, raw.replace("_", " "))
    if field.get("type") == "select" and fid == "disponibilites":
        return DISPONIBILITES_LABELS.get(raw, raw.replace("_", " "))
    return raw


def prefill_public_answers(profile: Dict[str, Any], patient_phone: str, *, template_type: str = "admin") -> Dict[str, Any]:
    """Pré-remplit le formulaire public depuis la fiche."""
    out: Dict[str, Any] = {}
    email = str(profile.get("email") or "").strip()
    if email:
        out["confirm_email"] = email
    phone = str(patient_phone or profile.get("phone") or "").strip()
    if phone:
        out["confirm_phone"] = phone
    physician = str(profile.get("treating_physician_name") or "").strip()
    if physician:
        out["medecin_traitant"] = physician
        out["treating_physician_name"] = physician
    birth = profile.get("birth_date")
    if birth:
        out["birth_date"] = str(birth)[:10]
    if template_type == "medical":
        city = str(profile.get("treating_physician_city") or "").strip()
        if city:
            out["treating_physician_city"] = city
    return out


def expire_stale_questionnaire_requests() -> int:
    """Passe en `expired` les demandes non complétées dont le lien a expiré."""
    ensure_patient_v2_schema()
    count = 0
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            UPDATE questionnaire_requests
            SET status = 'expired'
            WHERE status IN ('sent', 'opened', 'started')
              AND token_used = 0
              AND expires_at IS NOT NULL
              AND expires_at < datetime('now')
            """
        )
        count = int(cur.rowcount or 0)
        conn.commit()
    finally:
        conn.close()
    if pg_available():
        try:
            from backend.patient_v2_db import _pg_events_url
            import psycopg

            url = _pg_events_url()
            if url:
                with psycopg.connect(url) as pg:
                    with pg.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE questionnaire_requests
                            SET status = 'expired'
                            WHERE status IN ('sent', 'opened', 'started')
                              AND token_used = false
                              AND expires_at IS NOT NULL
                              AND expires_at < now()
                            """
                        )
                        count = max(count, int(cur.rowcount or 0))
                    pg.commit()
        except Exception:
            logger.debug("expire_stale_questionnaire_requests pg failed", exc_info=True)
    return count


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
        return _upgrade_default_template_row(tenant_id, existing)
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
            return _upgrade_default_template_row(tenant_id, dict(row))
    finally:
        conn.close()

    tpl = default_admin_template()
    return create_template(tenant_id, tpl)


def ensure_default_medical_template(tenant_id: int) -> Dict[str, Any]:
    """Template médical par défaut (créé uniquement si HDS actif pour le tenant)."""
    if not _hds_active(tenant_id):
        raise ValueError("Questionnaire médical indisponible sans HDS.")
    ensure_patient_v2_schema()
    existing = fetch_one_pg(
        """
        SELECT * FROM questionnaire_templates
        WHERE tenant_id = %s AND type = 'medical' AND is_default = true
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
            WHERE tenant_id = ? AND type = 'medical' AND is_default = 1
            ORDER BY created_at ASC LIMIT 1
            """,
            (tenant_id,),
        ).fetchone()
        if row:
            return _template_row(dict(row))
    finally:
        conn.close()

    return create_template(tenant_id, default_medical_template())


def create_template(tenant_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    ensure_patient_v2_schema()
    sections = payload.get("sections_json") or []
    hds = _hds_active(tenant_id)
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
    if template.get("is_health") and not _hds_active(tenant_id):
        raise ValueError("Questionnaire médical indisponible sans HDS.")

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


def _questionnaire_ai_summary(
    template: Dict[str, Any],
    answers: dict,
    *,
    is_health: bool,
) -> str:
    """Résumé factuel de la réponse (LLM Haiku si dispo, sinon liste à puces)."""
    structured = _structured_summary_from_answers(template, answers)
    lines = []
    for item in structured.values():
        label = item.get("label") or item.get("field_id") or "Champ"
        value = item.get("value")
        if isinstance(value, bool):
            value = "Oui" if value else "Non"
        lines.append(f"- {label}: {value}")
    fallback = ("Demande administrative :\n" if not is_health else "Éléments transmis :\n") + "\n".join(lines)

    api_key = (__import__("os").environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not api_key or not lines:
        return fallback.strip()

    system = (
        "Tu reformules UNIQUEMENT les réponses fournies d'un formulaire administratif patient. "
        "Ne déduis rien, n'invente rien, pas de diagnostic ni conseil. "
        "3 phrases maximum, ton neutre, français."
    )
    user = "Réponses (source de vérité) :\n" + json.dumps(structured, ensure_ascii=False, default=str)
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        model = "claude-sonnet-4-20250514" if is_health else "claude-haiku-4-5-20251001"
        resp = client.messages.create(
            model=model,
            max_tokens=220,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = (resp.content[0].text or "").strip()
        return text or fallback.strip()
    except Exception:
        logger.debug("questionnaire ai_summary LLM failed", exc_info=True)
        return fallback.strip()


def _apply_medical_integrated_answers_to_profile(tenant_id: int, phone: str, answers: dict) -> None:
    """Enrichit le profil patient depuis une réponse médicale intégrée."""
    if not answers:
        return
    kwargs: Dict[str, Any] = {}
    birth = str(answers.get("birth_date") or "").strip()
    physician = str(answers.get("treating_physician_name") or "").strip()
    city = str(answers.get("treating_physician_city") or "").strip()
    if birth:
        kwargs["birth_date"] = birth
    if physician:
        kwargs["treating_physician_name"] = physician
    if city:
        kwargs["treating_physician_city"] = city
    if kwargs:
        update_patient_fields(tenant_id, phone, **kwargs)


def _apply_integrated_answers_to_profile(tenant_id: int, phone: str, answers: dict) -> None:
    """Enrichit la fiche patient depuis une réponse admin intégrée."""
    if not answers:
        return
    email = str(answers.get("confirm_email") or "").strip()
    physician = str(answers.get("medecin_traitant") or "").strip()
    kwargs: Dict[str, Any] = {}
    if email:
        kwargs["email"] = email
    if physician:
        kwargs["treating_physician_name"] = physician
    if kwargs:
        update_patient_fields(tenant_id, phone, **kwargs)


def _answers_with_labels(template: Dict[str, Any], answers: dict) -> List[Dict[str, Any]]:
    fields = {str(f.get("field_id") or ""): f for f in (template.get("sections_json") or [])}
    out: List[Dict[str, Any]] = []
    for key, value in (answers or {}).items():
        field = fields.get(str(key)) or {"field_id": key, "label": key, "type": "text"}
        out.append(
            {
                "field_id": str(key),
                "label": field.get("label") or key,
                "type": field.get("type") or "text",
                "value": value,
                "display_value": _format_answer_display(field, value),
            }
        )
    return out


def upload_questionnaire_file(
    raw_token: str,
    content: bytes,
    original_name: str,
    mime_type: str = "",
) -> Dict[str, Any]:
    """Upload patient (token public) — HDS requis."""
    req = resolve_token(raw_token)
    if not req:
        raise ValueError("Lien invalide, expiré ou déjà utilisé.")
    tenant_id = int(req["tenant_id"])
    if not _hds_active(tenant_id):
        raise ValueError("Transmission de documents médicaux indisponible sans HDS.")
    request_id = str(req["id"])
    phone = normalize_patient_phone(req["patient_phone"])
    if count_documents_for_request(request_id) >= 5:
        raise ValueError("Maximum 5 documents par formulaire.")
    storage_key, stored_name = save_questionnaire_upload(
        tenant_id,
        phone,
        request_id,
        content,
        original_name,
        mime_type,
    )
    doc = insert_patient_document_v2(
        tenant_id,
        phone,
        questionnaire_request_id=request_id,
        filename=original_name or stored_name,
        storage_key=storage_key,
        mime_type=mime_type,
        is_health=True,
        uploaded_by="patient",
    )
    try:
        from backend.patient_access_audit import log_patient_access

        log_patient_access(
            tenant_id=tenant_id,
            actor_user_id="patient",
            action="patient_upload_document",
            patient_phone=phone,
            resource="questionnaire_v2_public",
        )
    except Exception:
        logger.debug("upload audit failed", exc_info=True)
    return doc


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

    hds = _hds_active(tenant_id)
    upload_count = count_documents_for_request(str(req["id"]))
    effective_has_uploads = has_uploads or upload_count > 0
    clean = validate_answers_against_template(
        template, answers, hds_active=hds, has_uploads=effective_has_uploads
    )
    is_health = compute_response_is_health(template, clean, has_uploads=effective_has_uploads)
    if is_health and not hds:
        raise ValueError("Soumission refusée : données de santé sans HDS.")

    response_id = _new_id()
    structured = _structured_summary_from_answers(template, clean)
    ai_summary = _questionnaire_ai_summary(template, clean, is_health=is_health)
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

    link_documents_to_response(str(req["id"]), response_id)

    fields_by_id = {str(f.get("field_id") or ""): f for f in (template.get("sections_json") or [])}
    note_lines = []
    for key, val in clean.items():
        field = fields_by_id.get(key) or {"field_id": key, "label": key}
        note_lines.append(f"{field.get('label') or key}: {_format_answer_display(field, val)}")
    if upload_count > 0:
        note_lines.append(f"Documents joints: {upload_count}")
    if note_lines:
        prefix = "Questionnaire médical complété" if is_health else "Formulaire administratif complété"
        insert_patient_note(
            tenant_id,
            phone,
            note_text=f"{prefix}\n" + "\n".join(note_lines),
            author="Questionnaire patient",
        )

    invalidate_patient_summary(tenant_id, phone)

    try:
        from backend.patient_access_audit import log_patient_access

        log_patient_access(
            tenant_id=tenant_id,
            actor_user_id="patient",
            action="patient_submit_questionnaire",
            patient_phone=phone,
            resource="questionnaire_v2_public",
        )
    except Exception:
        logger.debug("patient_submit_questionnaire audit failed", exc_info=True)

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
    template = get_template(tenant_id, str(row.get("template_id") or "")) or ensure_default_admin_template(tenant_id)
    answers = _json_load(row.get("answers_json"), {})
    is_medical = str(template.get("type") or "") == "medical" or bool(template.get("is_health"))
    if is_medical:
        _apply_medical_integrated_answers_to_profile(tenant_id, phone, answers)
    else:
        _apply_integrated_answers_to_profile(tenant_id, phone, answers)

    summary = str(row.get("ai_summary") or "").strip()
    if summary:
        prefix = "Questionnaire médical intégré" if is_medical else "Formulaire administratif intégré"
        insert_patient_note(
            tenant_id,
            phone,
            note_text=f"{prefix}\n{summary}",
            author="Questionnaire patient",
        )

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


def get_questionnaire_response(tenant_id: int, response_id: str) -> Dict[str, Any]:
    row = fetch_one_pg(
        """
        SELECT qr.*, qreq.status AS request_status, qreq.template_id, qreq.sent_to_email, qreq.created_at AS request_created_at
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
                SELECT qr.*, qreq.status AS request_status, qreq.template_id, qreq.sent_to_email,
                       qreq.created_at AS request_created_at
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

    template = get_template(tenant_id, str(row.get("template_id") or "")) or ensure_default_admin_template(tenant_id)
    answers = _json_load(row.get("answers_json"), {})
    phone = normalize_patient_phone(row.get("patient_phone") or "")
    return {
        "id": str(row.get("id") or response_id),
        "patient_phone": phone,
        "request_id": str(row.get("questionnaire_request_id") or ""),
        "request_status": row.get("request_status") or "",
        "sent_to_email": row.get("sent_to_email") or "",
        "submitted_at": str(row.get("submitted_at") or ""),
        "is_health": bool(row.get("is_health")),
        "ai_summary": row.get("ai_summary") or "",
        "answers": answers,
        "answers_display": _answers_with_labels(template, answers),
        "structured_summary": _json_load(row.get("structured_summary_json"), {}),
        "documents": list_documents_for_response(str(row.get("id") or response_id)),
    }


def list_patient_questionnaire_requests(
    tenant_id: int,
    patient_phone: str,
    *,
    template_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    expire_stale_questionnaire_requests()
    phone = normalize_patient_phone(patient_phone)
    rows = fetch_all_pg(
        """
        SELECT qreq.id, qreq.status, qreq.sent_to_email, qreq.created_at, qreq.completed_at,
               qreq.integrated_at, qreq.expires_at, qreq.template_id,
               qt.type AS template_type, qt.name AS template_name, qt.is_health AS template_is_health,
               (
                 SELECT qr.id FROM questionnaire_responses qr
                 WHERE qr.questionnaire_request_id = qreq.id
                 ORDER BY qr.submitted_at DESC LIMIT 1
               ) AS response_id,
               (
                 SELECT qr.ai_summary FROM questionnaire_responses qr
                 WHERE qr.questionnaire_request_id = qreq.id
                 ORDER BY qr.submitted_at DESC LIMIT 1
               ) AS ai_summary
        FROM questionnaire_requests qreq
        LEFT JOIN questionnaire_templates qt ON qt.id = qreq.template_id
        WHERE qreq.tenant_id = %s AND qreq.patient_phone = %s
        """
        + (" AND qt.type = %s" if template_type else "")
        + """
        ORDER BY qreq.created_at DESC
        LIMIT 20
        """,
        (tenant_id, phone, template_type) if template_type else (tenant_id, phone),
    )
    if rows:
        return [dict(r) for r in rows]
    conn = get_conn()
    try:
        sql = """
            SELECT qreq.id, qreq.status, qreq.sent_to_email, qreq.created_at, qreq.completed_at,
                   qreq.integrated_at, qreq.expires_at, qreq.template_id,
                   qt.type AS template_type, qt.name AS template_name, qt.is_health AS template_is_health,
                   (
                     SELECT qr.id FROM questionnaire_responses qr
                     WHERE qr.questionnaire_request_id = qreq.id
                     ORDER BY qr.submitted_at DESC LIMIT 1
                   ) AS response_id,
                   (
                     SELECT qr.ai_summary FROM questionnaire_responses qr
                     WHERE qr.questionnaire_request_id = qreq.id
                     ORDER BY qr.submitted_at DESC LIMIT 1
                   ) AS ai_summary
            FROM questionnaire_requests qreq
            LEFT JOIN questionnaire_templates qt ON qt.id = qreq.template_id
            WHERE qreq.tenant_id = ? AND qreq.patient_phone = ?
        """
        params: tuple = (tenant_id, phone)
        if template_type:
            sql += " AND qt.type = ?"
            params = (tenant_id, phone, template_type)
        sql += " ORDER BY qreq.created_at DESC LIMIT 20"
        raw = conn.execute(sql, params).fetchall()
        return [dict(r) for r in raw]
    finally:
        conn.close()


def public_questionnaire_payload(raw_token: str) -> Dict[str, Any]:
    expire_stale_questionnaire_requests()
    req = resolve_token(raw_token)
    if not req:
        raise ValueError("Lien invalide, expiré ou déjà utilisé.")
    mark_request_opened(str(req["id"]))
    tenant_id = int(req["tenant_id"])
    phone = normalize_patient_phone(req["patient_phone"])
    profile = get_cabinet_client_by_phone(tenant_id, phone) or {}
    template = get_template(tenant_id, str(req.get("template_id") or "")) or ensure_default_admin_template(tenant_id)
    hds = _hds_active(tenant_id)
    tpl_type = str(template.get("type") or "admin")
    prefill = prefill_public_answers(profile, phone, template_type=tpl_type)
    request_id = str(req["id"])
    pending_uploads = list_documents_for_request(request_id) if hds else []
    return {
        "tenant_id": tenant_id,
        "patient_phone": phone,
        "patient_name": profile.get("display_name") or profile.get("validated_name") or "",
        "prefill_answers": prefill,
        "template": {
            "id": template["id"],
            "name": template["name"],
            "type": tpl_type,
            "description": template["description"],
            "sections_json": template["sections_json"],
            "is_health": bool(template.get("is_health")),
            "hds_active": hds,
            "medical_upload_allowed": hds,
        },
        "request_id": request_id,
        "pending_uploads": pending_uploads,
        "expires_at": str(req.get("expires_at") or ""),
    }
