"""
RÈGLE 7 : extraction de contraintes horaires depuis le message utilisateur.
Ex: "je finis à 17h", "après 18h30", "avant 16h".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Literal

ConstraintType = Literal["after", "before"]


@dataclass
class TimeConstraint:
    type: ConstraintType
    minute_of_day: int
    raw: str


# Match phrases type: "à partir de 17h", "après 18h30", "avant 16h", "jusqu'à 15h"
HOUR_RE = re.compile(
    r"(?:à\s*partir\s*de|après|vers|jusqu[' ]?à|avant)\s*(\d{1,2})(?:h|:)?(\d{0,2})",
    re.IGNORECASE,
)


def extract_time_constraint(text: str) -> Optional[TimeConstraint]:
    """
    Extrait une contrainte horaire simple depuis un message utilisateur.
    Exemple:
      - "je finis à 17h" => after 17:00
      - "après 18h30"   => after 18:30
      - "avant 16h"     => before 16:00
      - "jusqu'à 15h"   => before 15:00
    """
    t = (text or "").strip().lower()
    if not t:
        return None

    m = HOUR_RE.search(t)
    if not m:
        # Cas courant: "je finis/termine/travaille jusqu'à/à 17h"
        m2 = re.search(
            r"(finis|termine|travaille)\s*(?:jusqu[' ]?à|à)\s*(\d{1,2})(?:h|:)?(\d{0,2})",
            t,
        )
        if not m2:
            return None
        hh = int(m2.group(2))
        mm = int(m2.group(3) or "0")
        return TimeConstraint(type="after", minute_of_day=hh * 60 + mm, raw=m2.group(0))

    keyword = m.group(0).lower()
    hh = int(m.group(1))
    mm = int(m.group(2) or "0")
    minute = hh * 60 + mm

    if "avant" in keyword or "jusqu" in keyword:
        ctype: ConstraintType = "before"
    else:
        ctype = "after"

    return TimeConstraint(type=ctype, minute_of_day=minute, raw=keyword)
