"""
Chiffrement symétrique des données sensibles "at rest" (notes patients,
transcripts d'appels, etc.).

Objectif : qu'un dump SQL de la base (vol des sauvegardes Railway, accès lecture
à la base par un opérateur cloud) ne suffise pas à exfiltrer les données PHI/PII.
La clé reste sur l'application (env var `DATA_ENCRYPTION_KEY`).

Format colonne :
- `enc:v1:<token_fernet_base64>`  → chiffré
- toute autre chaîne                → considérée comme **clair legacy**
  (rétrocompatibilité avec les données préexistantes ; un script de backfill
   peut migrer progressivement le clair vers le chiffré).

Rotation de clé :
- `DATA_ENCRYPTION_KEY` accepte 1 clé Fernet (urlsafe base64 32 bytes).
- `DATA_ENCRYPTION_KEYS_OLD` (CSV) liste les anciennes clés acceptées en
  déchiffrement uniquement. Au rollout d'une nouvelle clé, on ajoute
  l'ancienne dans `DATA_ENCRYPTION_KEYS_OLD` puis on backfill (re-encrypt
  en lisant + écrivant) pour migrer.

Génération initiale :
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

_PREFIX = "enc:v1:"
_fernet_primary = None
_fernet_multi = None  # MultiFernet primary + old keys


def _load_fernet():
    """Charge (paresseusement) les MultiFernet à partir des variables d'env."""
    global _fernet_primary, _fernet_multi
    if _fernet_primary is not None:
        return _fernet_primary, _fernet_multi
    try:
        from cryptography.fernet import Fernet, MultiFernet
    except Exception:
        logger.warning("crypto_at_rest: cryptography indisponible, chiffrement désactivé")
        return None, None

    primary_raw = (os.environ.get("DATA_ENCRYPTION_KEY") or "").strip()
    if not primary_raw:
        return None, None
    try:
        primary = Fernet(primary_raw.encode())
    except Exception as e:
        logger.error("crypto_at_rest: DATA_ENCRYPTION_KEY invalide (%s) → chiffrement désactivé", e)
        return None, None

    old_keys_raw = (os.environ.get("DATA_ENCRYPTION_KEYS_OLD") or "").strip()
    old_fernets: List = []
    if old_keys_raw:
        for k in old_keys_raw.split(","):
            k = k.strip()
            if not k:
                continue
            try:
                old_fernets.append(Fernet(k.encode()))
            except Exception as e:
                logger.warning("crypto_at_rest: DATA_ENCRYPTION_KEYS_OLD: clé ignorée (%s)", e)

    _fernet_primary = primary
    _fernet_multi = MultiFernet([primary, *old_fernets]) if old_fernets else primary
    return _fernet_primary, _fernet_multi


def is_encryption_enabled() -> bool:
    """Vrai si une `DATA_ENCRYPTION_KEY` valide est chargée."""
    primary, _ = _load_fernet()
    return primary is not None


def encrypt_str(plaintext: Optional[str]) -> Optional[str]:
    """
    Chiffre une chaîne. Retourne `enc:v1:<token>` ou la chaîne d'origine si
    le chiffrement est désactivé. None / chaîne vide retournés tels quels.
    """
    if plaintext is None or plaintext == "":
        return plaintext
    primary, _ = _load_fernet()
    if primary is None:
        return plaintext
    try:
        tok = primary.encrypt(plaintext.encode("utf-8")).decode("ascii")
    except Exception as e:
        logger.error("crypto_at_rest.encrypt failed: %s", e)
        return plaintext
    return _PREFIX + tok


def decrypt_str(value: Optional[str]) -> Optional[str]:
    """
    Déchiffre une chaîne au format `enc:v1:...`. Si elle ne commence pas
    par le préfixe, on retourne tel quel (legacy clair).
    Tolère l'absence de clé : retourne la chaîne brute (mais logue).
    """
    if value is None or value == "":
        return value
    if not isinstance(value, str) or not value.startswith(_PREFIX):
        return value
    _, multi = _load_fernet()
    if multi is None:
        logger.warning("crypto_at_rest.decrypt: token chiffré rencontré mais DATA_ENCRYPTION_KEY absente")
        return ""
    token = value[len(_PREFIX):]
    try:
        return multi.decrypt(token.encode("ascii")).decode("utf-8")
    except Exception as e:
        logger.error("crypto_at_rest.decrypt failed (token tronqué/clé erronée): %s", e)
        return ""


__all__ = ["encrypt_str", "decrypt_str", "is_encryption_enabled"]
