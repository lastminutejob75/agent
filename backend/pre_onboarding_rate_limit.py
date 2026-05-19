# backend/pre_onboarding_rate_limit.py — Rate limit POST /api/pre-onboarding/commit
from __future__ import annotations

from backend.rate_limit import check_sliding_window, client_ip


def check_pre_onboarding_commit(request, identity: str) -> None:
    """identity = email ou téléphone (clé anti-spam)."""
    ip = client_ip(request)
    check_sliding_window(f"pre_commit_ip:{ip}", limit=8, window_sec=60)
    ident = (identity or "").strip().lower()
    if ident:
        check_sliding_window(f"pre_commit_id:{ident}", limit=5, window_sec=60)
