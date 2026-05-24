"""
Origine métier d'un RDV (canal / acteur créateur).

Valeurs stables renvoyées par l'API agenda : voice, public_page, praticien, unknown.
Stockées en Postgres sur `appointments.booking_origin` et dans les descriptions Google
via la balise canonique `[uwi-origin:value]`.
"""
from __future__ import annotations

import re
from typing import Optional

VOICE = "voice"
PUBLIC_PAGE = "public_page"
PRATICIEN = "praticien"
UNKNOWN = "unknown"

_TAG_RE = re.compile(r"\[uwi-origin:([a-z_]+)\]", re.IGNORECASE)

# Origines autorisées à l'écriture (API praticien, Google)
ALLOWED_TAGS = frozenset({VOICE, PUBLIC_PAGE, PRATICIEN})


def format_google_origin_tag(origin: Optional[str]) -> str:
    o = canonical(str(origin or "").strip().lower())
    if o == UNKNOWN:
        return ""
    if o not in ALLOWED_TAGS:
        return ""
    return f"\n[uwi-origin:{o}]"


def parse_google_description(description: Optional[str]) -> Optional[str]:
    raw = description or ""
    m = _TAG_RE.search(raw)
    if not m:
        return None
    cand = canonical(m.group(1))
    return cand if cand != UNKNOWN else None


def canonical(raw: Optional[str]) -> str:
    s = str(raw or "").strip().lower()
    if not s:
        return UNKNOWN
    if s in ALLOWED_TAGS:
        return s
    # Alias historiques / BDD publique
    if s in {"page_publique", "chat", "chat_public"}:
        return PUBLIC_PAGE
    if s in {"vapi", "vocal", "phone", "ivr"}:
        return VOICE
    if s in {"cabinet_ui", "praticien_ui", "praticienne", "cabinet"}:
        return PRATICIEN
    return UNKNOWN


def normalize_for_agenda(value: Optional[str]) -> str:
    c = canonical(value)
    return c

