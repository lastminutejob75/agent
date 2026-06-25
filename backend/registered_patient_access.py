"""Accès réservé aux patients déjà enregistrés (fiche ``cabinet_clients``)."""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

import backend.db as db
from backend.handoffs import _normalized_phone_from_session

REGISTERED_PATIENT_ONLY_DETAIL = (
    "Cette demande est réservée aux patients déjà enregistrés au cabinet. "
    "Pour un premier contact, prenez rendez-vous en ligne ou appelez le cabinet."
)

TWO_FACTOR_REQUIRED_DETAIL = (
    "Identification insuffisante : indiquez votre téléphone ET votre email "
    "(ou votre nom et prénom) tels qu'enregistrés au cabinet."
)

_NAME_STOPWORDS = frozenset(
    {"de", "du", "des", "le", "la", "les", "monsieur", "madame", "mr", "mme", "dr", "docteur"}
)


def _strip_accents(value: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _name_tokens(value: Optional[str]) -> set:
    base = _strip_accents(value).lower()
    raw = re.split(r"[^a-z0-9]+", base)
    return {t for t in raw if len(t) >= 2 and t not in _NAME_STOPWORDS}


def verify_registered_patient_2fa(
    tenant_id: int,
    *,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    name: Optional[str] = None,
) -> Optional[dict]:
    """Vérification 2 facteurs.

    Facteur 1 obligatoire : le téléphone doit correspondre à une fiche patient.
    Facteur 2 (au choix) : l'email OU le nom+prénom fournis doivent correspondre
    à CETTE MÊME fiche. Le téléphone seul ne suffit jamais.
    """
    phone_s = (phone or "").strip()
    if not phone_s:
        return None
    profile = db.find_cabinet_client(int(tenant_id), phone=phone_s)
    if not profile:
        return None

    email_s = (email or "").strip().lower()
    if email_s:
        prof_email = str(profile.get("email") or "").strip().lower()
        if prof_email and prof_email == email_s:
            return profile

    provided = _name_tokens(name)
    if len(provided) >= 2:
        prof_tokens: set = set()
        for key in ("display_name", "validated_name", "raw_name"):
            prof_tokens |= _name_tokens(profile.get(key))
        if len(provided & prof_tokens) >= 2:
            return profile

    return None


def find_registered_patient(
    tenant_id: int,
    *,
    phone: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[dict]:
    """Retourne la fiche patient si le numéro ou l'email est connu du cabinet."""
    return db.find_cabinet_client(int(tenant_id), phone=phone or "", email=email or "")


def find_registered_patient_for_session(tenant_id: int, session: Any) -> Optional[dict]:
    qualif = getattr(session, "qualif_data", None)
    email = getattr(qualif, "email", None) if qualif else None
    phone = _normalized_phone_from_session(session)
    return find_registered_patient(tenant_id, phone=phone, email=email)


def is_registered_patient(
    tenant_id: int,
    *,
    phone: Optional[str] = None,
    email: Optional[str] = None,
) -> bool:
    return find_registered_patient(tenant_id, phone=phone, email=email) is not None


def registered_patient_only_message(channel: str) -> str:
    from backend import prompts

    if (channel or "").strip().lower() == "vocal":
        return prompts.VOCAL_REGISTERED_PATIENT_ONLY
    return prompts.MSG_REGISTERED_PATIENT_ONLY_WEB
