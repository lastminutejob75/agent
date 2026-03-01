# backend/routes/checkout_embedded.py
# POST /create-checkout-session : session Embedded Checkout pour la page /checkout (lead « Profiter du mois gratuit »).
# Compatible avec le frontend qui appelle stripeApiUrl + /create-checkout-session et attend { clientSecret }.
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["checkout_embedded"])


class CreateCheckoutSessionBody(BaseModel):
    price_id: Optional[str] = Field(None, description="Stripe Price ID (optionnel si STRIPE_PRICE_ID en env)")
    quantity: int = Field(1, ge=1, le=100)


@router.post("/create-checkout-session")
def create_checkout_session_embedded(body: CreateCheckoutSessionBody) -> dict[str, Any]:
    """
    Crée une session Stripe Checkout en mode embedded (clientSecret pour EmbeddedCheckout).
    Utilisé par la landing /checkout quand VITE_STRIPE_API_URL pointe vers ce backend.
    """
    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        raise HTTPException(503, "Stripe non configuré (STRIPE_SECRET_KEY)")
    price_id = (body.price_id or "").strip() or (os.environ.get("STRIPE_PRICE_ID") or "").strip()
    if not price_id:
        raise HTTPException(400, "STRIPE_PRICE_ID manquant (env ou body.price_id)")
    frontend_url = (os.environ.get("STRIPE_EMBEDDED_RETURN_URL") or os.environ.get("FRONTEND_URL") or "https://uwiapp.com").strip().rstrip("/")
    return_url = f"{frontend_url}/checkout/return?session_id={{CHECKOUT_SESSION_ID}}"
    try:
        import stripe
        stripe.api_key = stripe_key
        session = stripe.checkout.Session.create(
            ui_mode="embedded",
            line_items=[{"price": price_id, "quantity": body.quantity}],
            mode="payment",
            return_url=return_url,
        )
        secret = (getattr(session, "client_secret", None) or "").strip()
        if not secret:
            raise HTTPException(500, "Stripe n'a pas renvoyé client_secret")
        return {"clientSecret": secret}
    except Exception as e:
        logger.warning("create_checkout_session_embedded failed: %s", e)
        raise HTTPException(502, str(e) or "Erreur Stripe")
