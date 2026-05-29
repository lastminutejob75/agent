"""Questionnaire médical d'onboarding patient.

Un questionnaire par patient (clé tenant_id + téléphone). Deux modes de saisie :
- le praticien le remplit lui-même depuis la fiche patient ;
- le praticien envoie un lien sécurisé (token HMAC) au patient, qui le remplit
  lui-même ; à la soumission, les réponses remplissent automatiquement le
  questionnaire de la fiche.

Certaines réponses enrichissent le **profil patient** (date de naissance,
médecin traitant) et le **contexte patient** (note de synthèse :
allergies, traitements, antécédents, etc.).

Stockage : table `patient_questionnaires`, réponses sérialisées en JSON et
chiffrées au repos (comme les notes patient) si DATA_ENCRYPTION_KEY est défini.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from backend.db import (
    _pg_events_url,
    _pg_table_exists,
    get_conn,
    insert_patient_note,
    normalize_phone_number,
    update_patient_fields,
)
from backend.lead_tokens import make_lead_token, verify_lead_token

logger = logging.getLogger(__name__)

STATUS_DRAFT = "draft"
STATUS_SENT = "sent"
STATUS_COMPLETED = "completed"

FILLED_BY_PRACTITIONER = "practitioner"
FILLED_BY_PATIENT = "patient"

# Schéma du questionnaire (MVP fixe). `maps_to` décrit comment la réponse
# enrichit la fiche : "profile.<champ>" → champ profil patient ; "context" →
# note de synthèse ajoutée au contexte patient.
QUESTIONNAIRE_FIELDS: List[Dict[str, Any]] = [
    {"id": "birth_date", "label": "Date de naissance", "type": "date", "maps_to": "profile.birth_date"},
    {"id": "treating_physician_name", "label": "Médecin traitant", "type": "text", "maps_to": "profile.treating_physician_name"},
    {"id": "treating_physician_city", "label": "Ville du médecin traitant", "type": "text", "maps_to": "profile.treating_physician_city"},
    {"id": "allergies", "label": "Allergies connues", "type": "textarea", "maps_to": "context"},
    {"id": "current_treatments", "label": "Traitements en cours", "type": "textarea", "maps_to": "context"},
    {"id": "medical_history", "label": "Antécédents médicaux", "type": "textarea", "maps_to": "context"},
    {"id": "emergency_contact", "label": "Personne à contacter en cas d'urgence", "type": "text", "maps_to": "context"},
    {"id": "main_reason", "label": "Motif principal de consultation", "type": "textarea", "maps_to": "context"},
]

_FIELD_IDS = {f["id"] for f in QUESTIONNAIRE_FIELDS}
_FIELD_BY_ID = {f["id"]: f for f in QUESTIONNAIRE_FIELDS}
_TOKEN_PREFIX = "pq"


def questionnaire_schema() -> List[Dict[str, Any]]:
    """Schéma exposé au front (sans la cuisine interne `maps_to`)."""
    return [{"id": f["id"], "label": f["label"], "type": f["type"]} for f in QUESTIONNAIRE_FIELDS]


def sanitize_answers(answers: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Ne garde que les champs connus, en chaînes nettoyées (max 2000 car.)."""
    out: Dict[str, str] = {}
    if not isinstance(answers, dict):
        return out
    for key, value in answers.items():
        if key not in _FIELD_IDS:
            continue
        if value is None:
            continue
        out[key] = str(value).strip()[:2000]
    return out


def make_questionnaire_token(tenant_id: int, phone: str) -> str:
    phone_norm = normalize_phone_number(phone) or phone.strip()
    return make_lead_token(f"{_TOKEN_PREFIX}:{int(tenant_id)}:{phone_norm}")


def parse_questionnaire_token(token: str) -> Optional[Dict[str, Any]]:
    """Vérifie le token et renvoie {tenant_id, phone} si valide, sinon None."""
    ok, ref, _reason = verify_lead_token(token)
    if not ok or not ref:
        return None
    parts = ref.split(":", 2)
    if len(parts) != 3 or parts[0] != _TOKEN_PREFIX:
        return None
    try:
        tenant_id = int(parts[1])
    except (TypeError, ValueError):
        return None
    phone = parts[2].strip()
    if not phone:
        return None
    return {"tenant_id": tenant_id, "phone": phone}


def _ensure_table_sqlite(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_questionnaires (
            tenant_id INTEGER NOT NULL,
            phone TEXT NOT NULL,
            answers_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'draft',
            filled_by TEXT,
            sent_to_email TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT,
            PRIMARY KEY (tenant_id, phone)
        )
        """
    )


def _ensure_table_pg(conn) -> None:
    if _pg_table_exists(conn, "patient_questionnaires"):
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS patient_questionnaires (
                tenant_id INTEGER NOT NULL,
                phone TEXT NOT NULL,
                answers_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'draft',
                filled_by TEXT,
                sent_to_email TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                completed_at TIMESTAMPTZ,
                PRIMARY KEY (tenant_id, phone)
            )
            """
        )


def _decode_answers(raw: Any) -> Dict[str, str]:
    from backend.crypto_at_rest import decrypt_str

    if not raw:
        return {}
    text = decrypt_str(raw) if isinstance(raw, str) else raw
    try:
        data = json.loads(text) if isinstance(text, str) else (text or {})
    except (TypeError, ValueError):
        return {}
    return sanitize_answers(data if isinstance(data, dict) else {})


def _row_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": str(row.get("status") or STATUS_DRAFT),
        "filled_by": str(row.get("filled_by") or ""),
        "sent_to_email": str(row.get("sent_to_email") or ""),
        "answers": _decode_answers(row.get("answers_json")),
        "updated_at": str(row.get("updated_at") or ""),
        "completed_at": str(row.get("completed_at") or ""),
    }


def get_questionnaire(tenant_id: int, phone: str) -> Dict[str, Any]:
    """Renvoie l'état du questionnaire (statut + réponses). Vide si inexistant."""
    phone_norm = normalize_phone_number(phone) or phone.strip()
    empty = {
        "status": STATUS_DRAFT,
        "filled_by": "",
        "sent_to_email": "",
        "answers": {},
        "updated_at": "",
        "completed_at": "",
    }
    url = _pg_events_url()
    if url:
        try:
            from backend.pg_pool import pg_connection_for

            with pg_connection_for(url) as conn:
                _ensure_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT status, filled_by, sent_to_email, answers_json, updated_at, completed_at
                        FROM patient_questionnaires
                        WHERE tenant_id = %s AND phone = %s
                        """,
                        (tenant_id, phone_norm),
                    )
                    row = cur.fetchone()
                    if row:
                        return _row_to_dict(dict(row))
        except Exception:
            logger.debug("get_questionnaire pg failed", exc_info=True)
    conn = get_conn()
    try:
        _ensure_table_sqlite(conn)
        cur = conn.execute(
            """
            SELECT status, filled_by, sent_to_email, answers_json, updated_at, completed_at
            FROM patient_questionnaires
            WHERE tenant_id = ? AND phone = ?
            """,
            (tenant_id, phone_norm),
        )
        row = cur.fetchone()
        if row:
            return _row_to_dict(dict(row))
    finally:
        conn.close()
    return empty


def save_questionnaire(
    tenant_id: int,
    phone: str,
    *,
    answers: Dict[str, Any],
    status: str,
    filled_by: str,
    sent_to_email: Optional[str] = None,
    mark_completed: bool = False,
) -> Dict[str, Any]:
    """Upsert le questionnaire (réponses chiffrées). Retourne l'état à jour."""
    from backend.crypto_at_rest import encrypt_str

    phone_norm = normalize_phone_number(phone) or phone.strip()
    clean = sanitize_answers(answers)
    stored = encrypt_str(json.dumps(clean, ensure_ascii=False))
    email_clean = (sent_to_email or "").strip().lower()[:254] or None

    url = _pg_events_url()
    if url:
        try:
            from backend.pg_pool import pg_connection_for

            with pg_connection_for(url) as conn:
                _ensure_table_pg(conn)
                completed_sql = "now()" if mark_completed else "patient_questionnaires.completed_at"
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        INSERT INTO patient_questionnaires
                            (tenant_id, phone, answers_json, status, filled_by, sent_to_email,
                             completed_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, {'now()' if mark_completed else 'NULL'}, now())
                        ON CONFLICT (tenant_id, phone) DO UPDATE SET
                            answers_json = EXCLUDED.answers_json,
                            status = EXCLUDED.status,
                            filled_by = EXCLUDED.filled_by,
                            sent_to_email = COALESCE(EXCLUDED.sent_to_email, patient_questionnaires.sent_to_email),
                            completed_at = {completed_sql},
                            updated_at = now()
                        """,
                        (tenant_id, phone_norm, stored, status, filled_by or None, email_clean),
                    )
                conn.commit()
        except Exception:
            logger.debug("save_questionnaire pg failed", exc_info=True)

    conn = get_conn()
    try:
        _ensure_table_sqlite(conn)
        completed_expr = "datetime('now')" if mark_completed else "completed_at"
        conn.execute(
            f"""
            INSERT INTO patient_questionnaires
                (tenant_id, phone, answers_json, status, filled_by, sent_to_email,
                 completed_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, {"datetime('now')" if mark_completed else "NULL"}, datetime('now'))
            ON CONFLICT(tenant_id, phone) DO UPDATE SET
                answers_json = excluded.answers_json,
                status = excluded.status,
                filled_by = excluded.filled_by,
                sent_to_email = COALESCE(excluded.sent_to_email, patient_questionnaires.sent_to_email),
                completed_at = {completed_expr},
                updated_at = datetime('now')
            """,
            (tenant_id, phone_norm, stored, status, filled_by or None, email_clean),
        )
        conn.commit()
    finally:
        conn.close()
    return get_questionnaire(tenant_id, phone_norm)


def merge_profile_into_answers(
    profile: Optional[Dict[str, Any]],
    answers: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """Pré-remplit les champs profil du questionnaire avec ce que la fiche connaît déjà.

    Les réponses déjà saisies (questionnaire) restent prioritaires : on ne
    complète que les champs profil encore vides (date de naissance, médecin
    traitant, ville). Permet de gagner du temps sur une fiche existante.
    """
    merged = sanitize_answers(answers)
    if not profile:
        return merged
    for field in QUESTIONNAIRE_FIELDS:
        maps_to = field["maps_to"]
        if not maps_to.startswith("profile."):
            continue
        field_id = field["id"]
        if (merged.get(field_id) or "").strip():
            continue
        column = maps_to.split(".", 1)[1]
        raw = profile.get(column)
        if raw is None:
            continue
        value = str(raw).strip()
        if field["type"] == "date":
            value = value[:10]
        if value:
            merged[field_id] = value[:2000]
    return merged


def _context_note_from_answers(answers: Dict[str, str], *, source_label: str) -> str:
    """Construit une note de synthèse pour le contexte patient."""
    lines: List[str] = []
    for field in QUESTIONNAIRE_FIELDS:
        if field["maps_to"] != "context":
            continue
        value = (answers.get(field["id"]) or "").strip()
        if value:
            lines.append(f"- {field['label']} : {value}")
    if not lines:
        return ""
    header = f"Questionnaire médical ({source_label})"
    return header + "\n" + "\n".join(lines)


def apply_answers_to_patient(
    tenant_id: int,
    phone: str,
    answers: Dict[str, str],
    *,
    source_label: str,
    add_context_note: bool = True,
) -> None:
    """Enrichit le profil patient + ajoute une note de contexte de synthèse."""
    clean = sanitize_answers(answers)

    profile_kwargs: Dict[str, Any] = {}
    for field in QUESTIONNAIRE_FIELDS:
        maps_to = field["maps_to"]
        if not maps_to.startswith("profile."):
            continue
        value = (clean.get(field["id"]) or "").strip()
        if value:
            profile_kwargs[maps_to.split(".", 1)[1]] = value
    if profile_kwargs:
        try:
            update_patient_fields(tenant_id, phone, **profile_kwargs)
        except Exception:
            logger.warning("apply_answers_to_patient: update_patient_fields failed", exc_info=True)

    if add_context_note:
        note_text = _context_note_from_answers(clean, source_label=source_label)
        if note_text:
            try:
                insert_patient_note(tenant_id, phone, note_text=note_text, author="Questionnaire patient")
            except Exception:
                logger.warning("apply_answers_to_patient: insert_patient_note failed", exc_info=True)
