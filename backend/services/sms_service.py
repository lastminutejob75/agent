"""Utilitaires SMS Twilio pour les envois applicatifs."""
from __future__ import annotations

import os
from typing import Optional, Tuple


def send_sms_message(to_number: str, body: str) -> Tuple[bool, Optional[str]]:
    """Envoie un SMS via Twilio. Retourne (ok, erreur)."""
    sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
    token = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
    from_number = (os.environ.get("TWILIO_PHONE_NUMBER") or "").strip()
    to_norm = (to_number or "").strip()
    msg = (body or "").strip()
    if not to_norm:
        return False, "Numéro destinataire manquant"
    if not msg:
        return False, "Message vide"
    if not (sid and token and from_number):
        return False, "SMS non configuré (TWILIO_*)"
    try:
        from twilio.rest import Client

        Client(sid, token).messages.create(
            body=msg[:1500],
            from_=from_number,
            to=to_norm,
        )
        return True, None
    except Exception as exc:  # pragma: no cover - dépend réseau/provider
        return False, str(exc)
