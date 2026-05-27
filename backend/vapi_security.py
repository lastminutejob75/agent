"""Verification de la signature des webhooks Vapi (audit securite 2026-05).

Vapi supporte deux modes d'authentification quand `server.secret` est configure :

1. **Shared secret (legacy)** : Vapi envoie le secret en clair dans le header
   `X-Vapi-Secret`. On compare en temps constant avec notre secret local.

2. **HMAC-SHA256 (recommande)** : Vapi calcule HMAC-SHA256(body, secret) et
   l'envoie dans le header `X-Vapi-Signature`. La valeur peut etre prefixee
   `sha256=` ou non. On recalcule et compare en temps constant.

Cf. https://docs.vapi.ai/server-url/server-authentication

---

## Configuration

| Variable | Defaut | Role |
|---|---|---|
| `VAPI_WEBHOOK_SECRET` | — | Secret partage avec Vapi (envoye dans `server.secret` a la creation d'assistant). |
| `VAPI_REQUIRE_SIGNATURE` | `false` | Si `true`, rejette les requetes sans signature valide (401). Si `false` (defaut), log un warning et accepte (mode migration douce). |
| `VAPI_SIGNATURE_DISABLED` | `false` | Skip total de la verification (uniquement en dev/CI). Override `VAPI_REQUIRE_SIGNATURE`. |

## Migration douce recommandee

1. **Phase 1 — Audit** : `VAPI_REQUIRE_SIGNATURE=false` (defaut). Le code log un
   `vapi_signature_invalid` quand il rejetterait. On surveille les logs sur
   3-7 jours pour detecter les mismatchs (header manquant, format different, etc.).
2. **Phase 2 — Strict** : `VAPI_REQUIRE_SIGNATURE=true`. Les webhooks non
   signes correctement sont rejetes en 401.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Mapping, Optional, Tuple

logger = logging.getLogger(__name__)

# Resultats possibles de verify_vapi_signature
VERIFY_OK = "ok"
VERIFY_NO_SECRET = "no_secret"
VERIFY_MISSING_HEADER = "missing"
VERIFY_BAD_SHARED_SECRET = "bad_shared_secret"
VERIFY_BAD_HMAC = "bad_hmac"
VERIFY_DISABLED = "disabled"


def _get_secret() -> str:
    return (os.environ.get("VAPI_WEBHOOK_SECRET") or "").strip()


def _is_disabled() -> bool:
    """`VAPI_SIGNATURE_DISABLED=true` pour skipper en dev/CI."""
    return (os.environ.get("VAPI_SIGNATURE_DISABLED") or "").strip().lower() in (
        "true", "1", "yes", "on"
    )


def is_strict_mode() -> bool:
    """`VAPI_REQUIRE_SIGNATURE=true` pour rejeter les requetes non signees."""
    return (os.environ.get("VAPI_REQUIRE_SIGNATURE") or "").strip().lower() in (
        "true", "1", "yes", "on"
    )


def verify_vapi_signature(
    body: bytes,
    headers: Mapping[str, str],
) -> Tuple[bool, str]:
    """Verifie la signature d'un webhook Vapi.

    Args:
        body: Le corps brut de la requete (bytes, NON parse).
        headers: Mapping insensible a la casse des headers HTTP.

    Returns:
        (ok, reason) ou `reason` est une des constantes VERIFY_*.

    Logique :
    - Si `VAPI_SIGNATURE_DISABLED=true` → (True, "disabled") sans verifier.
    - Si pas de secret configure → (False, "no_secret").
    - Si header `X-Vapi-Secret` present : compare en temps constant.
    - Sinon si header `X-Vapi-Signature` present : recalcule HMAC-SHA256
      et compare en temps constant. Accepte les prefixes `sha256=`.
    - Sinon : (False, "missing").
    """
    if _is_disabled():
        return True, VERIFY_DISABLED

    secret = _get_secret()
    if not secret:
        return False, VERIFY_NO_SECRET

    # Mode 1 : shared secret (X-Vapi-Secret)
    # Les headers FastAPI/Starlette sont en lowercase normalisees.
    legacy = _get_header(headers, "x-vapi-secret")
    if legacy:
        ok = hmac.compare_digest(legacy.encode("utf-8"), secret.encode("utf-8"))
        return ok, VERIFY_OK if ok else VERIFY_BAD_SHARED_SECRET

    # Mode 2 : HMAC-SHA256 (X-Vapi-Signature)
    sig = _get_header(headers, "x-vapi-signature")
    if sig:
        # Vapi peut prefixer par "sha256=" (style GitHub) ou pas
        if sig.startswith("sha256="):
            sig = sig[len("sha256="):]
        expected = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        ok = hmac.compare_digest(expected.encode("utf-8"), sig.encode("utf-8"))
        return ok, VERIFY_OK if ok else VERIFY_BAD_HMAC

    return False, VERIFY_MISSING_HEADER


def _get_header(headers: Mapping[str, str], name: str) -> str:
    """Recupere un header de facon insensible a la casse, retourne strippe."""
    # Tentative directe (FastAPI normalise deja en lowercase)
    val = headers.get(name) or headers.get(name.lower()) or headers.get(name.upper())
    if val is not None:
        return str(val).strip()
    # Fallback : iterer en insensible casse
    target = name.lower()
    for k, v in headers.items():
        if k.lower() == target:
            return str(v).strip()
    return ""


def make_test_signature(body: bytes, secret: Optional[str] = None) -> str:
    """Helper pour les tests : genere une signature HMAC-SHA256 valide pour `body`."""
    sec = secret if secret is not None else _get_secret()
    if not sec:
        raise ValueError("Aucun secret Vapi configure (et aucun fourni)")
    return hmac.new(sec.encode("utf-8"), body, hashlib.sha256).hexdigest()
