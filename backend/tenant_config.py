# backend/tenant_config.py
"""
Feature flags par tenant (client).
Permet d'activer/désactiver des features sans hotfix.
Source de vérité : tenant_config.flags_json (JSON).
Fallback : config.DEFAULT_FLAGS.
"""
from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend import config, db

logger = logging.getLogger(__name__)

FLAG_KEYS = (
    "ENABLE_LLM_ASSIST_START",
    "ENABLE_BARGEIN_SLOT_CHOICE",
    "ENABLE_SEQUENTIAL_SLOTS",
    "ENABLE_NO_FAQ_GUARD",
    "ENABLE_YES_AMBIGUOUS_ROUTER",
)

DAY_LABELS_SHORT = {0: "Lun", 1: "Mar", 2: "Mer", 3: "Jeu", 4: "Ven", 5: "Sam", 6: "Dim"}
OPENING_DAY_MAP = {
    "monday": 0, "mon": 0, "lun": 0, "0": 0,
    "tuesday": 1, "tue": 1, "mar": 1, "1": 1,
    "wednesday": 2, "wed": 2, "mer": 2, "2": 2,
    "thursday": 3, "thu": 3, "jeu": 3, "3": 3,
    "friday": 4, "fri": 4, "ven": 4, "4": 4,
    "saturday": 5, "sat": 5, "sam": 5, "5": 5,
    "sunday": 6, "sun": 6, "dim": 6, "6": 6,
}

DEFAULT_FAQ = {
    "medecin_generaliste": [
        {
            "category": "Horaires",
            "items": [
                {"id": "h1", "question": "Quels sont vos horaires d'ouverture ?", "answer": "Le cabinet est ouvert du lundi au vendredi de 9h à 12h30 et de 14h à 18h.", "active": True},
                {"id": "h2", "question": "Êtes-vous ouvert le samedi ?", "answer": "Non, le cabinet est fermé le samedi et le dimanche.", "active": True},
                {"id": "h3", "question": "Êtes-vous ouvert pendant les vacances ?", "answer": "Le cabinet peut être fermé pendant certaines périodes de vacances. Contactez-nous pour connaître les dates exactes.", "active": True},
            ],
        },
        {
            "category": "Tarifs et paiement",
            "items": [
                {"id": "t1", "question": "Quel est le prix d'une consultation ?", "answer": "La consultation est à 25 euros en secteur 1, prise en charge par l'assurance maladie.", "active": True},
                {"id": "t2", "question": "Acceptez-vous la carte vitale ?", "answer": "Oui, nous acceptons la carte vitale. Pensez à l'apporter à chaque consultation.", "active": True},
                {"id": "t3", "question": "Quels moyens de paiement acceptez-vous ?", "answer": "Nous acceptons la carte bancaire, les espèces et les chèques.", "active": True},
                {"id": "t4", "question": "Prenez-vous les mutuelles ?", "answer": "Oui, nous pratiquons le tiers payant avec la plupart des mutuelles.", "active": True},
            ],
        },
        {
            "category": "Adresse et accès",
            "items": [
                {"id": "a1", "question": "Quelle est votre adresse ?", "answer": "L'adresse du cabinet vous sera confirmée lors de la prise de rendez-vous.", "active": True},
                {"id": "a2", "question": "Y a-t-il un parking ?", "answer": "Un parking est disponible à proximité du cabinet.", "active": True},
                {"id": "a3", "question": "Le cabinet est-il accessible aux personnes à mobilité réduite ?", "answer": "Oui, le cabinet est accessible aux personnes à mobilité réduite.", "active": True},
            ],
        },
        {
            "category": "Urgences",
            "items": [
                {"id": "u1", "question": "Que faire en cas d'urgence ?", "answer": "En cas d'urgence vitale, appelez le 15 pour le SAMU ou le 112. Pour une urgence non vitale, contactez le cabinet.", "active": True},
                {"id": "u2", "question": "Consultez-vous sans rendez-vous ?", "answer": "Le cabinet fonctionne sur rendez-vous. En cas d'urgence, appelez-nous et nous ferons notre possible pour vous recevoir.", "active": True},
            ],
        },
        {
            "category": "Rendez-vous",
            "items": [
                {"id": "r1", "question": "Comment prendre rendez-vous ?", "answer": "Vous pouvez prendre rendez-vous directement via cet assistant vocal ou en rappelant le cabinet.", "active": True},
                {"id": "r2", "question": "Puis-je annuler un rendez-vous ?", "answer": "Oui, merci de nous prévenir au moins 24 heures à l'avance pour annuler ou reporter.", "active": True},
                {"id": "r3", "question": "Que se passe-t-il si j'arrive en retard ?", "answer": "En cas de retard important, le médecin pourrait ne pas pouvoir vous recevoir. Merci de prévenir le cabinet.", "active": True},
            ],
        },
        {
            "category": "Ordonnances et documents",
            "items": [
                {"id": "o1", "question": "Puis-je demander un renouvellement d'ordonnance ?", "answer": "Oui, laissez votre demande et le cabinet vous recontactera. Une consultation peut être nécessaire.", "active": True},
                {"id": "o2", "question": "Comment obtenir un certificat médical ?", "answer": "Les certificats médicaux nécessitent une consultation. Prenez rendez-vous avec le médecin.", "active": True},
            ],
        },
        {
            "category": "Contact",
            "items": [
                {"id": "c1", "question": "Comment vous contacter ?", "answer": "Vous pouvez nous joindre par téléphone aux horaires d'ouverture ou laisser un message via cet assistant.", "active": True},
                {"id": "c2", "question": "Peut-on vous envoyer un email ?", "answer": "Pour toute demande, le plus simple est de contacter le cabinet par téléphone ou via cet assistant vocal.", "active": True},
            ],
        },
    ],
    "dentiste": [
        {
            "category": "Horaires",
            "items": [
                {"id": "h1", "question": "Quels sont vos horaires d'ouverture ?", "answer": "Le cabinet dentaire est ouvert du lundi au vendredi de 9h à 12h30 et de 14h à 19h.", "active": True},
                {"id": "h2", "question": "Êtes-vous ouvert le samedi ?", "answer": "Non, le cabinet est fermé le week-end.", "active": True},
            ],
        },
        {
            "category": "Tarifs et paiement",
            "items": [
                {"id": "t1", "question": "Quels sont vos tarifs ?", "answer": "Les tarifs varient selon le type de soin. Le cabinet vous fournira un devis détaillé avant tout traitement.", "active": True},
                {"id": "t2", "question": "Prenez-vous en charge les mutuelles ?", "answer": "Oui, nous travaillons avec la plupart des mutuelles et pratiquons le tiers payant.", "active": True},
                {"id": "t3", "question": "Quels moyens de paiement acceptez-vous ?", "answer": "Nous acceptons la carte bancaire, les espèces et les chèques. Le paiement en plusieurs fois est possible pour les gros traitements.", "active": True},
                {"id": "t4", "question": "Acceptez-vous la carte vitale ?", "answer": "Oui, pensez à apporter votre carte vitale et votre mutuelle à chaque rendez-vous.", "active": True},
            ],
        },
        {
            "category": "Adresse et accès",
            "items": [
                {"id": "a1", "question": "Quelle est votre adresse ?", "answer": "L'adresse du cabinet vous sera confirmée lors de la prise de rendez-vous.", "active": True},
                {"id": "a2", "question": "Le cabinet est-il accessible aux personnes à mobilité réduite ?", "answer": "Oui, le cabinet est accessible aux personnes à mobilité réduite.", "active": True},
            ],
        },
        {
            "category": "Urgences",
            "items": [
                {"id": "u1", "question": "Gérez-vous les urgences dentaires ?", "answer": "Oui, nous réservons des créneaux pour les urgences chaque jour. Appelez le cabinet dès que possible.", "active": True},
                {"id": "u2", "question": "J'ai mal aux dents, que faire ?", "answer": "Contactez le cabinet rapidement. En dehors des horaires, appelez le 15 ou rendez-vous aux urgences dentaires les plus proches.", "active": True},
            ],
        },
        {
            "category": "Rendez-vous",
            "items": [
                {"id": "r1", "question": "Comment prendre rendez-vous ?", "answer": "Vous pouvez prendre rendez-vous via cet assistant vocal ou en appelant le cabinet.", "active": True},
                {"id": "r2", "question": "Puis-je annuler un rendez-vous ?", "answer": "Oui, merci de prévenir au moins 24 heures à l'avance.", "active": True},
            ],
        },
        {
            "category": "Contact",
            "items": [
                {"id": "c1", "question": "Comment vous contacter ?", "answer": "Vous pouvez nous joindre par téléphone aux horaires d'ouverture ou laisser un message via cet assistant.", "active": True},
            ],
        },
    ],
    "kine": [
        {
            "category": "Horaires",
            "items": [
                {"id": "h1", "question": "Quels sont vos horaires ?", "answer": "Le cabinet de kinésithérapie vous reçoit du lundi au vendredi de 8h à 20h sur rendez-vous.", "active": True},
                {"id": "h2", "question": "Êtes-vous ouvert le samedi ?", "answer": "Non, le cabinet est fermé le week-end.", "active": True},
            ],
        },
        {
            "category": "Tarifs et paiement",
            "items": [
                {"id": "t1", "question": "Quels sont vos tarifs ?", "answer": "Les tarifs sont conventionnés. Avec une ordonnance, les séances sont prises en charge par l'assurance maladie et votre mutuelle.", "active": True},
                {"id": "t2", "question": "Les séances sont-elles remboursées ?", "answer": "Oui, avec une ordonnance médicale, les séances sont remboursées par la sécurité sociale et votre complémentaire.", "active": True},
                {"id": "t3", "question": "Quels moyens de paiement acceptez-vous ?", "answer": "Nous acceptons la carte bancaire, les espèces et les chèques.", "active": True},
            ],
        },
        {
            "category": "Adresse et accès",
            "items": [
                {"id": "a1", "question": "Quelle est votre adresse ?", "answer": "L'adresse du cabinet vous sera confirmée lors de la prise de rendez-vous.", "active": True},
                {"id": "a2", "question": "Le cabinet est-il accessible aux personnes à mobilité réduite ?", "answer": "Oui, le cabinet est accessible aux personnes à mobilité réduite.", "active": True},
            ],
        },
        {
            "category": "Rendez-vous",
            "items": [
                {"id": "r1", "question": "Comment prendre rendez-vous ?", "answer": "Vous pouvez prendre rendez-vous via cet assistant vocal ou en appelant le cabinet.", "active": True},
                {"id": "r2", "question": "Faut-il une ordonnance ?", "answer": "Pour les soins remboursés, une ordonnance du médecin est nécessaire. Apportez-la au premier rendez-vous.", "active": True},
                {"id": "r3", "question": "Puis-je annuler un rendez-vous ?", "answer": "Oui, merci de prévenir au moins 24 heures à l'avance.", "active": True},
            ],
        },
        {
            "category": "Contact",
            "items": [
                {"id": "c1", "question": "Comment vous contacter ?", "answer": "Vous pouvez nous joindre par téléphone aux horaires d'ouverture ou laisser un message via cet assistant.", "active": True},
            ],
        },
    ],
    "specialiste": [
        {
            "category": "Horaires",
            "items": [
                {"id": "h1", "question": "Quels sont vos horaires ?", "answer": "Le cabinet vous reçoit sur rendez-vous du lundi au vendredi. Les horaires précis dépendent du praticien.", "active": True},
            ],
        },
        {
            "category": "Tarifs et paiement",
            "items": [
                {"id": "t1", "question": "Quels sont vos tarifs ?", "answer": "Les tarifs dépendent du type de consultation et du praticien. Le cabinet vous les précisera.", "active": True},
                {"id": "t2", "question": "Quels moyens de paiement acceptez-vous ?", "answer": "Nous acceptons la carte bancaire, les espèces et les chèques.", "active": True},
                {"id": "t3", "question": "Acceptez-vous la carte vitale ?", "answer": "Oui, pensez à apporter votre carte vitale et votre attestation de mutuelle.", "active": True},
            ],
        },
        {
            "category": "Adresse et accès",
            "items": [
                {"id": "a1", "question": "Quelle est votre adresse ?", "answer": "L'adresse du cabinet vous sera confirmée lors de la prise de rendez-vous.", "active": True},
            ],
        },
        {
            "category": "Rendez-vous",
            "items": [
                {"id": "r1", "question": "Comment prendre rendez-vous ?", "answer": "Vous pouvez prendre rendez-vous via cet assistant vocal ou en appelant le cabinet.", "active": True},
                {"id": "r2", "question": "Puis-je annuler un rendez-vous ?", "answer": "Oui, merci de prévenir au moins 48 heures à l'avance.", "active": True},
            ],
        },
        {
            "category": "Contact",
            "items": [
                {"id": "c1", "question": "Comment vous contacter ?", "answer": "Vous pouvez nous joindre par téléphone aux horaires d'ouverture ou laisser un message via cet assistant.", "active": True},
            ],
        },
    ],
    "infirmier": [
        {
            "category": "Horaires",
            "items": [
                {"id": "h1", "question": "Quels sont vos horaires ?", "answer": "Le cabinet et les tournées sont organisés du lundi au samedi de 7h à 19h.", "active": True},
                {"id": "h2", "question": "Faites-vous des visites à domicile ?", "answer": "Oui, nous effectuons des soins à domicile sur prescription médicale.", "active": True},
            ],
        },
        {
            "category": "Tarifs et paiement",
            "items": [
                {"id": "t1", "question": "Les soins sont-ils remboursés ?", "answer": "Oui, avec une ordonnance, les soins infirmiers sont pris en charge par l'assurance maladie.", "active": True},
                {"id": "t2", "question": "Quels moyens de paiement acceptez-vous ?", "answer": "Nous acceptons la carte bancaire, les espèces et les chèques. Le tiers payant est pratiqué.", "active": True},
            ],
        },
        {
            "category": "Rendez-vous",
            "items": [
                {"id": "r1", "question": "Comment prendre rendez-vous ?", "answer": "Vous pouvez prendre rendez-vous via cet assistant vocal ou en appelant le cabinet.", "active": True},
                {"id": "r2", "question": "Faut-il une ordonnance ?", "answer": "Oui, une ordonnance médicale est nécessaire pour les soins infirmiers remboursés.", "active": True},
            ],
        },
        {
            "category": "Contact",
            "items": [
                {"id": "c1", "question": "Comment vous contacter ?", "answer": "Vous pouvez nous joindre par téléphone ou laisser un message via cet assistant. L'équipe vous recontactera.", "active": True},
            ],
        },
    ],
    "default": [
        {
            "category": "Horaires",
            "items": [
                {"id": "h1", "question": "Quels sont vos horaires d'ouverture ?", "answer": "Le cabinet est ouvert du lundi au vendredi de 9h à 12h30 et de 14h à 18h.", "active": True},
                {"id": "h2", "question": "Êtes-vous ouvert le samedi ?", "answer": "Non, le cabinet est fermé le week-end.", "active": True},
            ],
        },
        {
            "category": "Tarifs et paiement",
            "items": [
                {"id": "t1", "question": "Quels sont vos tarifs ?", "answer": "Les tarifs dépendent du type de consultation. Le cabinet vous les précisera lors de votre rendez-vous.", "active": True},
                {"id": "t2", "question": "Quels moyens de paiement acceptez-vous ?", "answer": "Nous acceptons la carte bancaire, les espèces et les chèques.", "active": True},
                {"id": "t3", "question": "Acceptez-vous la carte vitale ?", "answer": "Oui, pensez à apporter votre carte vitale à chaque consultation.", "active": True},
            ],
        },
        {
            "category": "Adresse et accès",
            "items": [
                {"id": "a1", "question": "Quelle est votre adresse ?", "answer": "L'adresse du cabinet vous sera confirmée lors de la prise de rendez-vous.", "active": True},
                {"id": "a2", "question": "Le cabinet est-il accessible aux personnes à mobilité réduite ?", "answer": "Oui, le cabinet est accessible aux personnes à mobilité réduite.", "active": True},
            ],
        },
        {
            "category": "Rendez-vous",
            "items": [
                {"id": "r1", "question": "Comment prendre rendez-vous ?", "answer": "Vous pouvez prendre rendez-vous directement via cet assistant vocal ou en rappelant le cabinet.", "active": True},
                {"id": "r2", "question": "Puis-je annuler un rendez-vous ?", "answer": "Oui, merci de nous prévenir au moins 24 heures à l'avance.", "active": True},
            ],
        },
        {
            "category": "Urgences",
            "items": [
                {"id": "u1", "question": "Que faire en cas d'urgence ?", "answer": "En cas d'urgence vitale, appelez le 15 pour le SAMU ou le 112. Pour une urgence non vitale, contactez le cabinet.", "active": True},
            ],
        },
        {
            "category": "Contact",
            "items": [
                {"id": "c1", "question": "Comment vous contacter ?", "answer": "Vous pouvez nous joindre par téléphone aux horaires d'ouverture ou laisser un message via cet assistant.", "active": True},
            ],
        },
    ],
}


def _coerce_booking_days(raw_days: Any) -> List[int]:
    if isinstance(raw_days, (list, tuple)):
        booking_days = [int(x) for x in raw_days if str(x).strip().isdigit()]
    elif isinstance(raw_days, str):
        try:
            parsed = json.loads(raw_days)
            booking_days = [int(x) for x in parsed] if isinstance(parsed, (list, tuple)) else [0, 1, 2, 3, 4]
        except Exception:
            booking_days = [int(x.strip()) for x in raw_days.split(",") if x.strip().isdigit()]
    else:
        booking_days = [0, 1, 2, 3, 4]
    if not booking_days:
        booking_days = [0, 1, 2, 3, 4]
    return sorted({d for d in booking_days if 0 <= int(d) <= 6})


def derive_horaires_text(params: dict) -> str:
    """Génère un texte horaires lisible depuis les booking_rules / params structurés."""
    days = _coerce_booking_days((params or {}).get("booking_days"))
    start = int((params or {}).get("booking_start_hour") or (params or {}).get("start_hour") or 9)
    end = int((params or {}).get("booking_end_hour") or (params or {}).get("end_hour") or 18)
    days_str = ", ".join(DAY_LABELS_SHORT[d] for d in days if d in DAY_LABELS_SHORT)
    return f"{days_str} · {start}h–{end}h"


def convert_opening_hours_to_booking_rules(opening_hours: dict) -> Dict[str, Any]:
    """
    Convertit les horaires structurés du lead en booking_rules tenant.
    Accepte les variantes open/close ou start/end et clés monday..sunday / 0..6.
    """
    days: List[int] = []
    starts: List[int] = []
    ends: List[int] = []
    for day_name, val in (opening_hours or {}).items():
        if not isinstance(val, dict):
            continue
        day_idx = OPENING_DAY_MAP.get(str(day_name).strip().lower())
        if day_idx is None or val.get("closed"):
            continue
        days.append(day_idx)
        open_val = (val.get("open") or val.get("start") or "").strip()
        close_val = (val.get("close") or val.get("end") or "").strip()
        if open_val and ":" in open_val:
            try:
                starts.append(int(open_val.split(":")[0]))
            except Exception:
                pass
        if close_val and ":" in close_val:
            try:
                ends.append(int(close_val.split(":")[0]))
            except Exception:
                pass
    return {
        "booking_days": sorted(set(days)) or [0, 1, 2, 3, 4],
        "booking_start_hour": min(starts) if starts else 9,
        "booking_end_hour": max(ends) if ends else 18,
        "booking_duration_minutes": 15,
        "booking_buffer_minutes": 0,
    }


@dataclass(frozen=True)
class TenantFlags:
    tenant_id: int
    flags: Dict[str, bool]
    source: str  # "db" | "default"
    updated_at: Optional[str] = None


def _parse_flags(raw: str) -> Dict[str, bool]:
    try:
        data = json.loads(raw or "{}")
        if not isinstance(data, dict):
            return {}
        out: Dict[str, bool] = {}
        for k, v in data.items():
            if k in FLAG_KEYS and isinstance(v, bool):
                out[k] = v
        return out
    except Exception:
        return {}


def load_tenant_flags(conn, tenant_id: Optional[int]) -> TenantFlags:
    """Charge les flags depuis la DB. Merge avec config.DEFAULT_FLAGS."""
    tid = int(tenant_id or config.DEFAULT_TENANT_ID)
    merged = dict(config.DEFAULT_FLAGS)
    try:
        row = conn.execute(
            "SELECT flags_json, updated_at FROM tenant_config WHERE tenant_id = ?",
            (tid,),
        ).fetchone()
        if row and row[0]:
            merged.update(_parse_flags(row[0]))
            return TenantFlags(tenant_id=tid, flags=merged, source="db", updated_at=row[1])
    except Exception as e:
        logger.debug("load_tenant_flags: %s (using defaults)", e)
    return TenantFlags(tenant_id=tid, flags=merged, source="default", updated_at=None)


def get_flags(tenant_id: Optional[int] = None) -> Dict[str, bool]:
    """
    Retourne les flags effectifs (sans cache).
    PG-first read, SQLite fallback.
    """
    tid = tenant_id if tenant_id is not None and tenant_id > 0 else config.DEFAULT_TENANT_ID
    if config.USE_PG_TENANTS:
        try:
            from backend.tenants_pg import pg_get_tenant_flags
            result = pg_get_tenant_flags(tid)
            if result is not None:
                flags_dict, _ = result
                merged = dict(config.DEFAULT_FLAGS)
                for k, v in flags_dict.items():
                    if k in FLAG_KEYS and isinstance(v, bool):
                        merged[k] = v
                logger.debug("TENANT_READ source=pg get_flags tenant_id=%s", tid)
                return merged
        except Exception as e:
            logger.debug("TENANT_READ pg get_flags failed: %s (fallback sqlite)", e)
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        tf = load_tenant_flags(conn, tid)
        return tf.flags
    finally:
        conn.close()


def get_consent_mode(tenant_id: Optional[int] = None) -> str:
    """
    Retourne le mode consentement pour un tenant : "implicit" (défaut) ou "explicit".
    Utilisé uniquement pour le canal vocal.
    """
    params = get_params(tenant_id)
    raw = (params.get("consent_mode") or "").strip().lower()
    if raw in ("implicit", "explicit"):
        return raw
    return "implicit"


def get_tenant_display_config(tenant_id: Optional[int] = None) -> Dict[str, str]:
    """
    Retourne {business_name, transfer_phone, horaires} pour affichage / prompts.
    Lecture depuis params_json avec repli sur config (OPENING_HOURS_DEFAULT pour horaires).
    """
    params = get_params(tenant_id)
    horaires = (params.get("horaires") or "").strip()
    if not horaires and hasattr(config, "OPENING_HOURS_DEFAULT"):
        horaires = derive_horaires_text(params) if params else config.OPENING_HOURS_DEFAULT
    if not horaires:
        horaires = derive_horaires_text(params)
    return {
        "business_name": (params.get("business_name") or "").strip() or config.BUSINESS_NAME,
        "transfer_phone": (params.get("transfer_phone") or "").strip() or config.TRANSFER_PHONE,
        "horaires": horaires or "horaires d'ouverture",
    }


def get_booking_rules(tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Retourne les règles de réservation pour un tenant (params_json).
    Fallbacks : duration=15, start=9, end=18, buffer=0, days=[0..4].
    """
    params = get_params(tenant_id) or {}
    booking_days = _coerce_booking_days(params.get("booking_days"))
    return {
        "duration_minutes": int(params.get("booking_duration_minutes") or 15),
        "start_hour": int(params.get("booking_start_hour") or 9),
        "end_hour": int(params.get("booking_end_hour") or 18),
        "buffer_minutes": int(params.get("booking_buffer_minutes") or 0),
        "booking_days": booking_days,
    }


def _normalize_faq_items(raw_items: Any) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not isinstance(raw_items, list):
        return items
    for idx, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        if not question or not answer:
            continue
        item_id = str(item.get("id") or f"faq_{idx + 1}").strip() or f"faq_{idx + 1}"
        items.append(
            {
                "id": item_id,
                "question": question,
                "answer": answer,
                "active": bool(item.get("active", True)),
            }
        )
    return items


def normalize_faq_payload(raw_faq: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    if not isinstance(raw_faq, list):
        return normalized
    for idx, category in enumerate(raw_faq):
        if not isinstance(category, dict):
            continue
        category_name = str(category.get("category") or "").strip() or f"Catégorie {idx + 1}"
        items = _normalize_faq_items(category.get("items") or [])
        normalized.append({"category": category_name, "items": items})
    return normalized


def get_faq(tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retourne la FAQ du tenant, ou la FAQ par défaut selon sa spécialité."""
    params = get_params(tenant_id)
    faq = params.get("faq_json")
    if faq:
        if isinstance(faq, str):
            try:
                parsed = json.loads(faq)
                normalized = normalize_faq_payload(parsed)
                if normalized:
                    return normalized
            except Exception:
                pass
        elif isinstance(faq, list):
            normalized = normalize_faq_payload(faq)
            if normalized:
                return normalized
    specialty = str(params.get("sector") or "default").strip() or "default"
    return copy.deepcopy(DEFAULT_FAQ.get(specialty, DEFAULT_FAQ["default"]))


def faq_to_prompt_text(faq: List[Dict[str, Any]]) -> str:
    """Sérialise la FAQ pour injection dans le prompt Vapi."""
    lines = ["=== FAQ DU CABINET ==="]
    for cat in normalize_faq_payload(faq):
        lines.append(f"\n[{cat['category'].upper()}]")
        for item in cat.get("items", []):
            if item.get("active", True):
                lines.append(f"Q: {item['question']}")
                lines.append(f"R: {item['answer']}")
    lines.append("\n=== FIN FAQ ===")
    return "\n".join(lines)


def get_params(tenant_id: Optional[int] = None) -> Dict[str, str]:
    """
    Retourne params_json pour un tenant (calendar_provider, calendar_id, etc.).
    PG-first read, SQLite fallback.
    """
    tid = tenant_id if tenant_id is not None and tenant_id > 0 else config.DEFAULT_TENANT_ID
    if config.USE_PG_TENANTS:
        try:
            from backend.tenants_pg import pg_get_tenant_params
            result = pg_get_tenant_params(tid)
            if result is not None:
                params_dict, _ = result
                if isinstance(params_dict, dict):
                    logger.debug("TENANT_READ source=pg get_params tenant_id=%s", tid)
                    return params_dict
        except Exception as e:
            logger.debug("TENANT_READ pg get_params failed: %s (fallback sqlite)", e)
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT params_json FROM tenant_config WHERE tenant_id = ?",
            (tid,),
        ).fetchone()
        if row and row[0]:
            data = json.loads(row[0])
            return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.debug("get_params: %s", e)
    finally:
        conn.close()
    return {}


def set_params(tenant_id: int, params: Dict[str, str]) -> None:
    """Met à jour params_json (merge shallow). Clés à plat."""
    allowed = (
        "calendar_provider", "calendar_id", "contact_email", "timezone", "consent_mode", "business_name",
        "transfer_phone", "transfer_number", "horaires",
        "responsible_phone", "manager_name", "billing_email", "vapi_assistant_id", "plan_key", "notes",
        "custom_included_minutes_month",
        "assistant_name", "phone_number", "sector",
        "specialty_label", "address_line1", "postal_code", "city", "agenda_software",
        "client_onboarding_completed", "dashboard_tour_completed",
        "faq_json",
        "booking_duration_minutes", "booking_start_hour", "booking_end_hour",
        "booking_buffer_minutes", "booking_days",
        "mirror_google_bookings_to_internal",
        "transfer_assistant_phone", "transfer_practitioner_phone",
        "transfer_live_enabled", "transfer_callback_enabled",
        "transfer_cases", "transfer_hours", "transfer_always_urgent", "transfer_no_consultation",
        "transfer_config_confirmed_signature", "transfer_config_confirmed_at",
    )
    filtered = {}
    for k, v in params.items():
        if k not in allowed or v is None:
            continue
        if k == "booking_days":
            if isinstance(v, (list, tuple)):
                filtered[k] = [int(x) for x in v]
            elif isinstance(v, str):
                try:
                    parsed = json.loads(v)
                    filtered[k] = [int(x) for x in parsed] if isinstance(parsed, (list, tuple)) else [0, 1, 2, 3, 4]
                except Exception:
                    filtered[k] = [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
                if not filtered[k]:
                    filtered[k] = [0, 1, 2, 3, 4]
            else:
                filtered[k] = [0, 1, 2, 3, 4]
        elif k == "faq_json":
            filtered[k] = normalize_faq_payload(v)
        elif k == "transfer_cases":
            if isinstance(v, (list, tuple)):
                filtered[k] = [str(x) for x in v if str(x).strip()]
            elif isinstance(v, str):
                try:
                    parsed = json.loads(v)
                    filtered[k] = [str(x) for x in parsed] if isinstance(parsed, (list, tuple)) else []
                except Exception:
                    filtered[k] = [x.strip() for x in v.split(",") if x.strip()]
            else:
                filtered[k] = []
        elif k == "transfer_hours":
            if isinstance(v, dict):
                filtered[k] = v
            elif isinstance(v, str):
                try:
                    parsed = json.loads(v)
                    filtered[k] = parsed if isinstance(parsed, dict) else {}
                except Exception:
                    filtered[k] = {}
            else:
                filtered[k] = {}
        else:
            filtered[k] = str(v)
    if any(k in filtered for k in ("booking_days", "booking_start_hour", "booking_end_hour")):
        horaires_params = {
            "booking_days": filtered.get("booking_days", params.get("booking_days")),
            "booking_start_hour": filtered.get("booking_start_hour", params.get("booking_start_hour")),
            "booking_end_hour": filtered.get("booking_end_hour", params.get("booking_end_hour")),
        }
        filtered["horaires"] = derive_horaires_text(horaires_params)
    if not filtered:
        return
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        cur = conn.execute("SELECT params_json FROM tenant_config WHERE tenant_id = ?", (tenant_id,))
        row = cur.fetchone()
        current = json.loads(row[0]) if row and row[0] else {}
        merged = {**current, **filtered}
        cur2 = conn.execute("SELECT flags_json FROM tenant_config WHERE tenant_id = ?", (tenant_id,))
        row2 = cur2.fetchone()
        flags = row2[0] if row2 and row2[0] else "{}"
        conn.execute(
            """
            INSERT OR REPLACE INTO tenant_config (tenant_id, flags_json, params_json, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (tenant_id, flags, json.dumps(merged)),
        )
        conn.commit()
    finally:
        conn.close()


def reset_faq_params(tenant_id: int) -> None:
    """Supprime faq_json du tenant en SQLite pour revenir au défaut de spécialité."""
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        cur = conn.execute("SELECT params_json FROM tenant_config WHERE tenant_id = ?", (tenant_id,))
        row = cur.fetchone()
        current = json.loads(row[0]) if row and row[0] else {}
        if not isinstance(current, dict):
            current = {}
        current.pop("faq_json", None)
        cur2 = conn.execute("SELECT flags_json FROM tenant_config WHERE tenant_id = ?", (tenant_id,))
        row2 = cur2.fetchone()
        flags = row2[0] if row2 and row2[0] else "{}"
        conn.execute(
            """
            INSERT OR REPLACE INTO tenant_config (tenant_id, flags_json, params_json, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (tenant_id, flags, json.dumps(current)),
        )
        conn.commit()
    finally:
        conn.close()


def set_flags(tenant_id: int, flags: Dict[str, bool]) -> None:
    """Met à jour les flags d'un tenant (merge avec existant)."""
    filtered = {k: v for k, v in flags.items() if k in FLAG_KEYS and isinstance(v, bool)}
    if not filtered:
        return
    db.ensure_tenant_config()
    current = get_flags(tenant_id)
    merged = {**current, **filtered}
    conn = db.get_conn()
    try:
        cur = conn.execute("SELECT params_json FROM tenant_config WHERE tenant_id = ?", (tenant_id,))
        row = cur.fetchone()
        params = row[0] if row and row[0] else "{}"
        conn.execute(
            """
            INSERT OR REPLACE INTO tenant_config (tenant_id, flags_json, params_json, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (tenant_id, json.dumps(merged), params),
        )
        conn.commit()
    finally:
        conn.close()
