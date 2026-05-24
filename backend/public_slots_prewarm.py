"""
Pré-chauffage du cache créneaux page publique (/api/public/slots).

Évite le cold-start Google Calendar à chaque 1re visite après deploy :
le cron remplit _SLOTS_HTTP_CACHE + tools_booking._slots_cache toutes les 2 min.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    return os.getenv("PUBLIC_SLOTS_PREWARM_ENABLED", "true").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def prewarm_public_slots_cache(
    *,
    slugs: List[str] | None = None,
    count: int = 12,
) -> Dict[str, Any]:
    """
    Remplit le cache HTTP + moteur booking pour chaque slug public actif.
    Retourne un résumé { ok, failed, skipped, duration_ms }.
    """
    from backend.routes.public_pages import prewarm_slots_for_slug, load_public_slugs

    if not _enabled():
        return {"ok": 0, "failed": 0, "skipped": 0, "disabled": True}

    targets = slugs if slugs is not None else load_public_slugs()
    t0 = time.time()
    ok = failed = skipped = 0

    for slug in targets:
        s = (slug or "").strip()
        if not s:
            skipped += 1
            continue
        try:
            result = prewarm_slots_for_slug(s, count=count)
            if result.get("skipped"):
                skipped += 1
            elif result.get("ok"):
                ok += 1
            else:
                failed += 1
        except Exception as exc:
            failed += 1
            logger.warning("public_slots_prewarm slug=%s failed: %s", s, exc)

    summary = {
        "ok": ok,
        "failed": failed,
        "skipped": skipped,
        "slugs": len(targets),
        "duration_ms": int((time.time() - t0) * 1000),
    }
    if ok or failed:
        logger.info("public_slots_prewarm %s", summary)
    return summary


def run_public_slots_prewarm_job() -> None:
    """Job APScheduler — intervalle configurable (défaut 2 min)."""
    try:
        prewarm_public_slots_cache()
    except Exception as exc:
        logger.warning("public_slots_prewarm_job failed: %s", exc)
