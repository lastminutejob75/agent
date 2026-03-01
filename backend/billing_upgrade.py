"""
Simulation d'upgrade de plan (Starter → Growth → Pro) selon les minutes consommées.
V1 : pas d'appel Stripe ; retourne le plan suggéré + coûts pour log / note interne.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from backend.billing_pg import (
    get_plan_included_minutes,
    get_plan_overage_rate,
    get_tenant_billing,
)

logger = logging.getLogger(__name__)

# Base mensuelle € (pour simulation coût). Aligné avec Stripe prices.
PLAN_BASE_EUR = {
    "starter": 99,
    "growth": 149,
    "pro": 199,
}

# Ordre pour "plan supérieur" (upgrade uniquement, pas de downgrade auto).
PLAN_ORDER = ("starter", "growth", "pro")


def _simulate_cost(plan_key: str, minutes_used: float) -> Optional[float]:
    """
    Coût simulé pour un plan et un nombre de minutes.
    base_fee + max(0, minutes - included) * overage_rate.
    """
    if plan_key not in PLAN_BASE_EUR:
        return None
    base = PLAN_BASE_EUR[plan_key]
    included = get_plan_included_minutes(plan_key)
    overage_rate = get_plan_overage_rate(plan_key)
    if overage_rate is None:
        overage = 0.0
    else:
        overage_minutes = max(0.0, minutes_used - included)
        overage = overage_minutes * overage_rate
    return round(base + overage, 2)


def maybe_upgrade_plan(
    tenant_id: int,
    minutes_in_period: float,
    current_plan_key: Optional[str] = None,
) -> Tuple[Optional[str], Optional[float], Optional[float]]:
    """
    Suggère un plan plus avantageux si les minutes consommées le justifient.
    Règle : pas de downgrade automatique ; upgrade si coût simulé d'un plan supérieur < coût actuel.

    Entrées:
        tenant_id: id du tenant
        minutes_in_period: minutes utilisées sur la période courante (ex. mois en cours)
        current_plan_key: plan actuel (si None, lu depuis tenant_billing)

    Returns:
        (suggested_plan_key, current_cost, suggested_cost)
        - suggested_plan_key = None si pas d'upgrade recommandé ou plan actuel inconnu
        - current_cost / suggested_cost = coûts simulés en €
    """
    if current_plan_key is None:
        billing = get_tenant_billing(tenant_id)
        current_plan_key = (billing or {}).get("plan_key") or ""
        current_plan_key = (current_plan_key or "").strip().lower() or None
    if not current_plan_key or current_plan_key not in PLAN_ORDER:
        return (None, None, None)

    current_cost = _simulate_cost(current_plan_key, minutes_in_period)
    if current_cost is None:
        return (None, None, None)

    try:
        current_idx = PLAN_ORDER.index(current_plan_key)
    except ValueError:
        return (None, current_cost, None)

    best_plan = current_plan_key
    best_cost = current_cost
    for i in range(current_idx + 1, len(PLAN_ORDER)):
        candidate = PLAN_ORDER[i]
        candidate_cost = _simulate_cost(candidate, minutes_in_period)
        if candidate_cost is not None and candidate_cost < best_cost:
            best_cost = candidate_cost
            best_plan = candidate

    if best_plan == current_plan_key:
        return (None, current_cost, None)
    return (best_plan, current_cost, best_cost)
