"""Utilitaires SMS Twilio pour les envois applicatifs.

Auth supportée (par ordre de priorité) :
1. Clés d'API Twilio : TWILIO_API_KEY_SID (SK...) + TWILIO_API_KEY_SECRET + TWILIO_ACCOUNT_SID
2. Account SID + Auth Token : TWILIO_ACCOUNT_SID (AC...) + TWILIO_AUTH_TOKEN

Le numéro expéditeur TWILIO_PHONE_NUMBER (E.164) est requis dans les deux cas.
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def twilio_auth_configured() -> bool:
    """True si une méthode d'authentification Twilio est complète (hors numéro)."""
    account_sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
    api_key_sid = (os.environ.get("TWILIO_API_KEY_SID") or "").strip()
    api_key_secret = (os.environ.get("TWILIO_API_KEY_SECRET") or "").strip()
    auth_token = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
    if account_sid and api_key_sid and api_key_secret:
        return True
    if account_sid and auth_token:
        return True
    return False


def sms_is_configured() -> bool:
    """True si l'auth Twilio ET le numéro expéditeur sont présents."""
    from_number = (os.environ.get("TWILIO_PHONE_NUMBER") or "").strip()
    return bool(from_number) and twilio_auth_configured()


def _missing_twilio_keys() -> list[str]:
    """Liste lisible de ce qui manque pour envoyer un SMS."""
    missing: list[str] = []
    if not (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip():
        missing.append("TWILIO_ACCOUNT_SID")
    if not twilio_auth_configured():
        missing.append("TWILIO_AUTH_TOKEN ou (TWILIO_API_KEY_SID + TWILIO_API_KEY_SECRET)")
    if not (os.environ.get("TWILIO_PHONE_NUMBER") or "").strip():
        missing.append("TWILIO_PHONE_NUMBER")
    return missing


def get_twilio_client():
    """Crée un client Twilio (clés d'API ou Account SID/Auth Token). None si non configuré."""
    account_sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
    api_key_sid = (os.environ.get("TWILIO_API_KEY_SID") or "").strip()
    api_key_secret = (os.environ.get("TWILIO_API_KEY_SECRET") or "").strip()
    auth_token = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
    try:
        from twilio.rest import Client
    except ImportError:  # pragma: no cover - dépend de l'install
        logger.error("Twilio non installé (pip install twilio)")
        return None
    if account_sid and api_key_sid and api_key_secret:
        return Client(api_key_sid, api_key_secret, account_sid)
    if account_sid and auth_token:
        return Client(account_sid, auth_token)
    return None


def send_sms_message(to_number: str, body: str) -> Tuple[bool, Optional[str]]:
    """Envoie un SMS via Twilio. Retourne (ok, erreur)."""
    from_number = (os.environ.get("TWILIO_PHONE_NUMBER") or "").strip()
    to_norm = (to_number or "").strip()
    msg = (body or "").strip()
    if not to_norm:
        return False, "Numéro destinataire manquant"
    if not msg:
        return False, "Message vide"
    client = get_twilio_client()
    if client is None or not from_number:
        missing = _missing_twilio_keys()
        logger.warning("SMS non envoyé: configuration Twilio incomplète (manquant: %s)", ", ".join(missing))
        return False, "SMS non configuré (TWILIO_*)"
    try:
        client.messages.create(
            body=msg[:1500],
            from_=from_number,
            to=to_norm,
        )
        logger.info("SMS envoyé via Twilio vers %s", _mask_number(to_norm))
        return True, None
    except Exception as exc:  # pragma: no cover - dépend réseau/provider
        logger.warning("Échec envoi SMS Twilio vers %s: %s", _mask_number(to_norm), exc)
        return False, str(exc)


def _mask_number(num: str) -> str:
    num = (num or "").strip()
    if len(num) <= 4:
        return "***"
    return f"***{num[-4:]}"
