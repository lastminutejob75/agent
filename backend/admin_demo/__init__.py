"""Mode demo admin (lecture seule).

Active via ADMIN_DEMO_MODE=true. Quand actif, le router demo est monte AVANT
le router admin standard et intercepte les endpoints critiques pour servir
un dataset coherent et factice. Pratique pour valider l'UI/UX sans Postgres
ni donnees reelles.

Modules :
    - dataset.py : genere un dataset deterministe (seed fixe)
    - router.py  : endpoints alternatifs (memes paths que routes/admin.py)
"""

from __future__ import annotations

import os


def is_demo_mode() -> bool:
    """Retourne True si ADMIN_DEMO_MODE est active dans l'environnement."""
    return (os.getenv("ADMIN_DEMO_MODE") or "").strip().lower() in ("true", "1", "yes", "on")
