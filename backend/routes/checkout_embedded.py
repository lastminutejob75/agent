# backend/routes/checkout_embedded.py
# POST /create-checkout-session : session Embedded Checkout pour la page /checkout (lead « Profiter du mois gratuit »).
# Utilise les 6 prices existants : plan=starter|growth|pro → STRIPE_PRICE_BASE_* ; sinon body.price_id ou STRIPE_PRICE_ID.
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["checkout_embedded"])

PLAN_KEYS = ("starter", "growth", "pro")


def _get_base_price_id_for_plan(plan_key: str) -> Optional[str]:
    """Résout le price ID base depuis les env STRIPE_PRICE_BASE_STARTER/GROWTH/PRO."""
    pk = (plan_key or "").strip().lower()
    if pk not in PLAN_KEYS:
        return None
    return (os.environ.get(f"STRIPE_PRICE_BASE_{pk.upper()}") or "").strip() or None


class CreateCheckoutSessionBody(BaseModel):
    price_id: Optional[str] = Field(None, description="Stripe Price ID (optionnel si plan ou STRIPE_PRICE_ID)")
    quantity: int = Field(1, ge=1, le=100)
    plan: Optional[str] = Field("starter", description="starter | growth | pro — utilise STRIPE_PRICE_BASE_* (défaut: starter pour mois gratuit)")
    trial_days: Optional[int] = Field(30, ge=0, le=365, description="Jours d'essai gratuit (défaut 30 = mois gratuit)")


@router.post("/create-checkout-session")
def create_checkout_session_embedded(body: CreateCheckoutSessionBody) -> dict[str, Any]:
    """
    Crée une session Stripe Checkout en mode embedded (clientSecret pour EmbeddedCheckout).
    Utilise les 6 prices : plan=starter|growth|pro → STRIPE_PRICE_BASE_* ; sinon price_id ou STRIPE_PRICE_ID.
    """
    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        raise HTTPException(503, "Stripe non configuré (STRIPE_SECRET_KEY)")
    # Priorité : body.price_id > plan (STRIPE_PRICE_BASE_*) > STRIPE_PRICE_ID
    price_id = (body.price_id or "").strip()
    if not price_id and body.plan:
        price_id = _get_base_price_id_for_plan(body.plan) or ""
    if not price_id:
        price_id = (os.environ.get("STRIPE_PRICE_ID") or "").strip()
    if not price_id:
        raise HTTPException(400, "Price manquant : envoyez plan=starter|growth|pro ou price_id, ou définissez STRIPE_PRICE_ID / STRIPE_PRICE_BASE_STARTER en env")
    frontend_url = (os.environ.get("STRIPE_EMBEDDED_RETURN_URL") or os.environ.get("FRONTEND_URL") or "https://uwiapp.com").strip().rstrip("/")
    return_url = f"{frontend_url}/checkout/return?session_id={{CHECKOUT_SESSION_ID}}"
    # Les prix base (plan starter/growth/pro) sont des abonnements ; sinon paiement one-shot
    from_plan = _get_base_price_id_for_plan(body.plan or "") == price_id
    mode = "subscription" if from_plan else "payment"
    kwargs = {
        "ui_mode": "embedded",
        "line_items": [{"price": price_id, "quantity": body.quantity}],
        "mode": mode,
        "return_url": return_url,
    }
    if mode == "subscription" and (body.trial_days or 0) >= 1:
        kwargs["subscription_data"] = {"trial_period_days": min(body.trial_days or 30, 365)}
    try:
        import stripe
        stripe.api_key = stripe_key
        session = stripe.checkout.Session.create(**kwargs)
        secret = (getattr(session, "client_secret", None) or "").strip()
        if not secret:
            raise HTTPException(500, "Stripe n'a pas renvoyé client_secret")
        return {"clientSecret": secret}
    except Exception as e:
        logger.warning("create_checkout_session_embedded failed: %s", e)
        raise HTTPException(502, str(e) or "Erreur Stripe")
