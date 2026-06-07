"""Providers de contexte pour le résumé IA patient (V2)."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

from backend.db import get_cabinet_client_by_phone, list_patient_notes
from backend.patient_v2_db import fetch_all_pg, normalize_patient_phone
from backend.services.patient_metrics import get_patient_metrics
from backend.tenants_pg import pg_get_tenant_params
from backend.tenant_config import get_params

logger = logging.getLogger(__name__)


class ContextProvider(ABC):
    capability: str | None = None
    is_health_data: bool = False

    @abstractmethod
    def fetch(
        self,
        db,
        tenant_id: int,
        patient_phone: str,
        *,
        hds_active: bool,
    ) -> Tuple[dict, bool]:
        """Retourne (data, exposes_health)."""


def _fetch_identite(tenant_id: int, patient_phone: str) -> Dict[str, Any]:
    try:
        profile = get_cabinet_client_by_phone(tenant_id, patient_phone) or {}
    except Exception:
        logger.warning(
            "context_providers identite fetch failed tenant=%s phone=%s",
            tenant_id,
            str(patient_phone)[-4:] if patient_phone else "?",
            exc_info=True,
        )
        profile = {}
    return {
        "prenom": profile.get("display_name") or profile.get("validated_name") or profile.get("raw_name") or "",
        "telephone": patient_phone,
        "email": profile.get("email") or "",
        "birth_date": str(profile.get("birth_date") or "")[:10] or None,
        "medecin_traitant": profile.get("treating_physician_name") or "",
        "ville_medecin": profile.get("treating_physician_city") or "",
    }


def _fetch_notes(db, tenant_id: int, patient_phone: str, *, limit: int = 5) -> List[Dict[str, Any]]:
    notes = list_patient_notes(tenant_id, patient_phone, limit=limit)
    out = []
    for n in notes:
        out.append(
            {
                "author": n.get("author") or "Cabinet",
                "content": (n.get("note_text") or "")[:500],
                "created_at": str(n.get("created_at") or ""),
            }
        )
    return out


def _fetch_cabinet_team_notes(tenant_id: int, *, limit: int = 5) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {}
    try:
        got = pg_get_tenant_params(tenant_id)
        maybe_params = got[0] if got else {}
        if isinstance(maybe_params, dict):
            params = maybe_params
    except Exception:
        params = {}
    if not params:
        try:
            maybe_params = get_params(tenant_id)
            if isinstance(maybe_params, dict):
                params = maybe_params
        except Exception:
            params = {}

    raw_notes = params.get("dashboard_team_notes_json")
    if isinstance(raw_notes, str):
        try:
            raw_notes = json.loads(raw_notes)
        except Exception:
            raw_notes = []
    out: List[Dict[str, Any]] = []
    if isinstance(raw_notes, list):
        for item in raw_notes:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or item.get("note") or "").strip()
            if not text:
                continue
            out.append(
                {
                    "author": str(item.get("author") or "Equipe")[:80],
                    "content": text[:500],
                    "created_at": str(item.get("created_at") or item.get("updated_at") or ""),
                }
            )
            if len(out) >= limit:
                break
    if out:
        return out

    legacy = str(params.get("dashboard_team_note") or "").strip()
    if legacy:
        return [
            {
                "author": "Equipe",
                "content": legacy[:500],
                "created_at": str(params.get("dashboard_team_note_updated_at") or ""),
            }
        ]
    return []


def _fetch_events(db, tenant_id: int, patient_phone: str, *, limit: int = 5) -> List[Dict[str, Any]]:
    phone = normalize_patient_phone(patient_phone)
    rows = fetch_all_pg(
        """
        SELECT type, occurred_at, statut, motif, payload_json
        FROM patient_events
        WHERE tenant_id = %s AND patient_phone = %s
        ORDER BY occurred_at DESC
        LIMIT %s
        """,
        (tenant_id, phone, limit),
    )
    if rows:
        return [
            {
                "type": r.get("type"),
                "occurred_at": str(r.get("occurred_at") or ""),
                "statut": r.get("statut"),
                "motif": r.get("motif"),
            }
            for r in rows
        ]
    conn = db
    try:
        raw = conn.execute(
            """
            SELECT type, occurred_at, statut, motif
            FROM patient_events
            WHERE tenant_id = ? AND patient_phone = ?
            ORDER BY occurred_at DESC
            LIMIT ?
            """,
            (tenant_id, phone, limit),
        ).fetchall()
        return [dict(r) for r in raw]
    except Exception:
        return []


def _fetch_flags(db, tenant_id: int, patient_phone: str) -> List[str]:
    metrics = get_patient_metrics(tenant_id, patient_phone)
    flags: List[str] = []
    if metrics.get("nb_no_shows", 0) >= 2:
        flags.append("historique_no_show")
    if metrics.get("nb_annul_tardive", 0) >= 2:
        flags.append("annulations_tardives")
    if metrics.get("taux_assiduite") is None:
        flags.append("historique_insuffisant")
    elif metrics.get("taux_assiduite", 100) < 70:
        flags.append("assiduite_faible")
    return flags


def _fetch_questionnaire_responses(db, tenant_id: int, patient_phone: str, *, limit: int = 5) -> List[Dict[str, Any]]:
    phone = normalize_patient_phone(patient_phone)
    rows = fetch_all_pg(
        """
        SELECT qr.id, qr.answers_json, qr.ai_summary, qr.structured_summary_json,
               qr.is_health, qr.submitted_at, qreq.status
        FROM questionnaire_responses qr
        JOIN questionnaire_requests qreq ON qreq.id = qr.questionnaire_request_id
        WHERE qr.tenant_id = %s AND qr.patient_phone = %s
        ORDER BY qr.submitted_at DESC
        LIMIT %s
        """,
        (tenant_id, phone, limit),
    )
    if rows:
        return [_normalize_response_row(r) for r in rows]
    try:
        raw = db.execute(
            """
            SELECT qr.id, qr.answers_json, qr.ai_summary, qr.structured_summary_json,
                   qr.is_health, qr.submitted_at, qreq.status
            FROM questionnaire_responses qr
            JOIN questionnaire_requests qreq ON qreq.id = qr.questionnaire_request_id
            WHERE qr.tenant_id = ? AND qr.patient_phone = ?
            ORDER BY qr.submitted_at DESC
            LIMIT ?
            """,
            (tenant_id, phone, limit),
        ).fetchall()
        return [_normalize_response_row(dict(r)) for r in raw]
    except Exception:
        return []


def _normalize_response_row(row: Dict[str, Any]) -> Dict[str, Any]:
    answers = row.get("answers_json")
    if isinstance(answers, str):
        try:
            answers = json.loads(answers)
        except json.JSONDecodeError:
            answers = {}
    structured = row.get("structured_summary_json")
    if isinstance(structured, str):
        try:
            structured = json.loads(structured)
        except json.JSONDecodeError:
            structured = {}
    return {
        "id": str(row.get("id") or ""),
        "answers": answers or {},
        "ai_summary": row.get("ai_summary") or "",
        "structured_summary": structured or {},
        "is_health": bool(row.get("is_health")),
        "submitted_at": str(row.get("submitted_at") or ""),
        "request_status": row.get("status") or "",
    }


def _project_admin(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        out.append(
            {
                "submitted_at": r.get("submitted_at"),
                "type_demande": (r.get("answers") or {}).get("type_demande"),
                "resume": r.get("ai_summary") or "",
                "status": r.get("request_status"),
            }
        )
    return out


def _project_health(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        out.append(
            {
                "submitted_at": r.get("submitted_at"),
                "resume": r.get("ai_summary") or "",
                "elements": r.get("structured_summary") or {},
            }
        )
    return out


class ReceptionProvider(ContextProvider):
    capability = None
    is_health_data = False

    def fetch(self, db, tenant_id, patient_phone, *, hds_active):
        try:
            metriques = get_patient_metrics(tenant_id, patient_phone)
        except Exception:
            logger.warning(
                "context_providers metrics fetch failed tenant=%s phone=%s",
                tenant_id,
                str(patient_phone)[-4:] if patient_phone else "?",
                exc_info=True,
            )
            metriques = {}
        try:
            flags = _fetch_flags(db, tenant_id, patient_phone)
        except Exception:
            logger.warning(
                "context_providers flags fetch failed tenant=%s phone=%s",
                tenant_id,
                str(patient_phone)[-4:] if patient_phone else "?",
                exc_info=True,
            )
            flags = []
        try:
            notes = _fetch_notes(db, tenant_id, patient_phone, limit=5)
        except Exception:
            logger.warning(
                "context_providers notes fetch failed tenant=%s phone=%s",
                tenant_id,
                str(patient_phone)[-4:] if patient_phone else "?",
                exc_info=True,
            )
            notes = []
        try:
            cabinet_notes = _fetch_cabinet_team_notes(tenant_id, limit=5)
        except Exception:
            logger.warning(
                "context_providers cabinet notes fetch failed tenant=%s phone=%s",
                tenant_id,
                str(patient_phone)[-4:] if patient_phone else "?",
                exc_info=True,
            )
            cabinet_notes = []
        try:
            events = _fetch_events(db, tenant_id, patient_phone, limit=5)
        except Exception:
            logger.warning(
                "context_providers events fetch failed tenant=%s phone=%s",
                tenant_id,
                str(patient_phone)[-4:] if patient_phone else "?",
                exc_info=True,
            )
            events = []
        data = {
            "metriques": metriques,
            "flags": flags,
            "notes_recentes": notes,
            "notes_cabinet": cabinet_notes,
            "events_recents": events,
        }
        return data, False


class QuestionnaireProvider(ContextProvider):
    capability = None
    is_health_data = False

    def fetch(self, db, tenant_id, patient_phone, *, hds_active):
        rows = _fetch_questionnaire_responses(db, tenant_id, patient_phone, limit=5)
        admin, health = [], []
        for r in rows:
            (health if r.get("is_health") else admin).append(r)
        exposes_health = bool(health) and hds_active
        pending = _fetch_pending_questionnaires(db, tenant_id, patient_phone)
        data = {
            "questionnaires_admin": _project_admin(admin),
            "questionnaires_sante": _project_health(health) if hds_active else [],
            "questionnaires_en_attente": pending,
        }
        return data, exposes_health


def _fetch_pending_questionnaires(db, tenant_id: int, patient_phone: str) -> List[Dict[str, Any]]:
    phone = normalize_patient_phone(patient_phone)
    rows = fetch_all_pg(
        """
        SELECT id, status, sent_to_email, created_at, expires_at
        FROM questionnaire_requests
        WHERE tenant_id = %s AND patient_phone = %s
          AND status IN ('sent', 'opened', 'started')
        ORDER BY created_at DESC
        LIMIT 5
        """,
        (tenant_id, phone),
    )
    if rows:
        return [
            {
                "id": str(r.get("id") or ""),
                "status": r.get("status"),
                "sent_to": r.get("sent_to_email") or "",
                "created_at": str(r.get("created_at") or ""),
                "expires_at": str(r.get("expires_at") or ""),
            }
            for r in rows
        ]
    try:
        raw = db.execute(
            """
            SELECT id, status, sent_to_email, created_at, expires_at
            FROM questionnaire_requests
            WHERE tenant_id = ? AND patient_phone = ?
              AND status IN ('sent', 'opened', 'started')
            ORDER BY created_at DESC
            LIMIT 5
            """,
            (tenant_id, phone),
        ).fetchall()
        return [dict(r) for r in raw]
    except Exception:
        return []


class SanteProvider(ContextProvider):
    """Données cliniques MVP + questionnaires V2 santé (HDS requis)."""

    capability = "hds_enabled"
    is_health_data = True

    def fetch(self, db, tenant_id, patient_phone, *, hds_active):
        from backend.patient_questionnaire import get_questionnaire

        q = get_questionnaire(tenant_id, patient_phone)
        answers = q.get("answers") or {}
        antecedents: List[str] = []
        traitements: List[str] = []
        notes_cliniques: List[str] = []

        hist = str(answers.get("medical_history") or "").strip()
        if hist:
            antecedents.append(hist[:500])
        treat = str(answers.get("current_treatments") or "").strip()
        if treat:
            traitements.append(treat[:500])
        allergies = str(answers.get("allergies") or "").strip()
        if allergies:
            notes_cliniques.append(f"Allergies : {allergies[:300]}")
        motif = str(answers.get("main_reason") or "").strip()
        if motif:
            notes_cliniques.append(f"Motif : {motif[:300]}")
        emergency = str(answers.get("emergency_contact") or "").strip()
        if emergency:
            notes_cliniques.append(f"Contact urgence : {emergency[:120]}")

        health_rows = [
            r for r in _fetch_questionnaire_responses(db, tenant_id, patient_phone, limit=3)
            if r.get("is_health")
        ]
        for row in health_rows:
            summary = str(row.get("ai_summary") or "").strip()
            if summary:
                notes_cliniques.append(summary[:400])

        return {
            "antecedents": antecedents[:3],
            "traitements_en_cours": traitements[:3],
            "allergies": allergies[:300],
            "notes_cliniques": notes_cliniques[:6],
            "questionnaire_mvp_status": q.get("status") or "",
        }, True


PROVIDERS: List[ContextProvider] = [
    ReceptionProvider(),
    QuestionnaireProvider(),
    SanteProvider(),
]


def build_context_pack(db, tenant_id: int, patient_phone: str, tenant_caps: set) -> Tuple[dict, bool]:
    hds_active = "hds_enabled" in tenant_caps
    pack = {"identite": _fetch_identite(tenant_id, patient_phone)}
    contains_health = False
    for provider in PROVIDERS:
        if provider.capability and provider.capability not in tenant_caps:
            continue
        try:
            data, exposes_health = provider.fetch(db, tenant_id, patient_phone, hds_active=hds_active)
        except Exception:
            logger.warning(
                "context_providers provider failed provider=%s tenant=%s phone=%s",
                provider.__class__.__name__,
                tenant_id,
                str(patient_phone)[-4:] if patient_phone else "?",
                exc_info=True,
            )
            if isinstance(provider, ReceptionProvider):
                data = {"metriques": {}, "flags": [], "notes_recentes": [], "notes_cabinet": [], "events_recents": []}
            elif isinstance(provider, QuestionnaireProvider):
                data = {"questionnaires_admin": [], "questionnaires_sante": [], "questionnaires_en_attente": []}
            elif isinstance(provider, SanteProvider):
                data = {
                    "antecedents": [],
                    "traitements_en_cours": [],
                    "allergies": "",
                    "notes_cliniques": [],
                    "questionnaire_mvp_status": "",
                }
            else:
                data = {}
            exposes_health = False
        pack[provider.__class__.__name__] = data
        contains_health = contains_health or exposes_health
    return pack, contains_health
