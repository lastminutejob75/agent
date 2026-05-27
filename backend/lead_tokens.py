"""Tokens d'acces signes pour les endpoints sensibles du flow pre-onboarding.

Probleme : les endpoints `/api/pre-onboarding/leads/{id}/...` sont publics (pas
d'auth admin) parce qu'ils sont consommes par le wizard self-service apres le
commit. Mais avec juste l'UUID du lead, n'importe qui peut :
  - lire l'email du lead,
  - reserver un creneau de rappel,
  - creer un compte tenant + user (avec mot de passe temporaire envoye par email).

Solution : a `commit`, on emet un token HMAC signe lie au `lead_id` avec un
TTL, retourne au client une seule fois. Le client le stocke et le passe en
query string (`?token=...`) ou en header (`X-Lead-Token`) pour acceder aux
endpoints sensibles.

Format du token (compact, 3 parties separees par `.`) :
    base64url(lead_id).base64url(exp_timestamp).base64url(hmac)

ou hmac = HMAC-SHA256(secret, f"{lead_id}.{exp_timestamp}").

Secret : LEAD_TOKEN_SECRET, fallback JWT_SECRET, fallback ADMIN_SESSION_SECRET.
TTL par defaut : 7 jours (suffisant pour un flow d'onboarding).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 jours
LEAD_TOKEN_VERSION = "v1"  # prefixe pour permettre une rotation future


def _get_secret() -> str:
    """Recupere le secret pour signer les tokens lead.

    Priorite : LEAD_TOKEN_SECRET > JWT_SECRET > ADMIN_SESSION_SECRET.
    Si rien n'est configure, retourne une string vide -> les tokens generes
    seront vides et la verification echouera systematiquement (fail-closed).
    """
    return (
        (os.environ.get("LEAD_TOKEN_SECRET") or "").strip()
        or (os.environ.get("JWT_SECRET") or "").strip()
        or (os.environ.get("ADMIN_SESSION_SECRET") or "").strip()
    )


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("ascii"))


def make_lead_token(lead_id: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    """Genere un token signe pour un lead.

    Args:
        lead_id: UUID du lead.
        ttl_seconds: duree de validite (default 7 jours).

    Returns:
        Token sous forme `v1.{lead_b64}.{exp_b64}.{hmac_b64}`.

    Note : si aucun secret n'est configure, log un error mais retourne quand
    meme un token (qui sera invalide a la verif) pour ne pas casser le flow
    en environnement mal configure.
    """
    secret = _get_secret()
    if not secret:
        logger.error(
            "make_lead_token: aucun secret configure (LEAD_TOKEN_SECRET / JWT_SECRET / "
            "ADMIN_SESSION_SECRET). Les tokens emis seront invalides."
        )
    lead_id = (lead_id or "").strip()
    if not lead_id:
        raise ValueError("lead_id requis")
    exp = int(time.time()) + int(ttl_seconds)
    payload = f"{lead_id}.{exp}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return ".".join([
        LEAD_TOKEN_VERSION,
        _b64url_encode(lead_id.encode("utf-8")),
        _b64url_encode(str(exp).encode("ascii")),
        _b64url_encode(sig),
    ])


def verify_lead_token(token: str, expected_lead_id: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """Verifie un token et retourne (ok, lead_id, error_reason).

    Args:
        token: token a verifier (peut etre None / vide).
        expected_lead_id: si fourni, verifie en plus que le lead_id du token
            correspond (defense en profondeur contre les confusions).

    Returns:
        (True, lead_id, None) si valide.
        (False, None, "raison") sinon. Les raisons possibles :
            "missing", "malformed", "version", "expired", "bad_signature",
            "lead_mismatch", "no_secret".
    """
    if not token:
        return (False, None, "missing")
    secret = _get_secret()
    if not secret:
        return (False, None, "no_secret")
    parts = token.split(".")
    if len(parts) != 4:
        return (False, None, "malformed")
    version, lead_b64, exp_b64, sig_b64 = parts
    if version != LEAD_TOKEN_VERSION:
        return (False, None, "version")
    try:
        lead_id = _b64url_decode(lead_b64).decode("utf-8")
        exp = int(_b64url_decode(exp_b64).decode("ascii"))
        sig = _b64url_decode(sig_b64)
    except Exception:
        return (False, None, "malformed")
    if exp < int(time.time()):
        return (False, None, "expired")
    expected_payload = f"{lead_id}.{exp}".encode("utf-8")
    expected_sig = hmac.new(secret.encode("utf-8"), expected_payload, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected_sig):
        return (False, None, "bad_signature")
    if expected_lead_id is not None:
        exp_id = (expected_lead_id or "").strip()
        if exp_id and exp_id != lead_id:
            return (False, None, "lead_mismatch")
    return (True, lead_id, None)


def extract_token_from_request(request) -> str:
    """Extrait un token depuis la query string `?token=...` ou le header
    `X-Lead-Token`. Retourne une string (vide si absent).
    """
    try:
        token = request.query_params.get("token") or ""
    except Exception:
        token = ""
    if not token:
        try:
            token = request.headers.get("x-lead-token") or request.headers.get("X-Lead-Token") or ""
        except Exception:
            token = ""
    return (token or "").strip()
