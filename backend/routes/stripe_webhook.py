# backend/routes/stripe_webhook.py
"""
Webhook Stripe : sync tenant_billing (subscription created/updated/deleted, invoice.*, checkout.session.completed).
Agnostique prix ; vérification signature obligatoire.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.billing_pg import (
    clear_subscription,
    set_stripe_metered_item_id,
    try_acquire_stripe_event,
    tenant_id_by_stripe_customer_id,
    update_billing_status,
    upsert_billing_from_subscription,
    set_tenant_unsuspended,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_ts(ob: object, key: str) -> datetime | None:
    v = getattr(ob, key, None)
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, int):
        try:
            return datetime.utcfromtimestamp(v)
        except Exception:
            return None
    return None


def _sync_subscription(subscription: object) -> bool:
    """Sync tenant_billing à partir d'un objet Stripe Subscription. Source de vérité pour billing_status = subscription.status (active, past_due, canceled, trialing, unpaid)."""
    customer_id = getattr(subscription, "customer", None)
    if customer_id is None:
        return False
    if hasattr(customer_id, "id"):
        customer_id = customer_id.id
    customer_id = (customer_id or "").strip()
    if not customer_id:
        return False
    tenant_id = tenant_id_by_stripe_customer_id(customer_id)
    if tenant_id is None:
        logger.info("stripe webhook: no tenant for customer %s", customer_id[:20])
        return False
    status = (getattr(subscription, "status", None) or "").strip() or None
    sub_id = (getattr(subscription, "id", None) or "").strip()
    if not sub_id:
        return False
    plan_key = None
    if hasattr(subscription, "metadata") and subscription.metadata and getattr(subscription.metadata, "get", None):
        plan_key = (subscription.metadata.get("plan_key") or "").strip() or None
    if not plan_key and hasattr(subscription, "items") and subscription.items and getattr(subscription.items, "data", None):
        data = subscription.items.data or []
        if data and hasattr(data[0], "price") and data[0].price:
            plan_key = getattr(data[0].price, "nickname", None) or getattr(data[0].price, "lookup_key", None)
            plan_key = (plan_key or "").strip() or None
    period_start = _get_ts(subscription, "current_period_start")
    period_end = _get_ts(subscription, "current_period_end")
    trial_end = _get_ts(subscription, "trial_end") if getattr(subscription, "trial_end", None) else None
    ok = upsert_billing_from_subscription(
        tenant_id=tenant_id,
        stripe_subscription_id=sub_id,
        billing_status=status or "unknown",
        plan_key=plan_key,
        current_period_start=period_start,
        current_period_end=period_end,
        trial_ends_at=trial_end,
        stripe_customer_id=customer_id,
    )
    if ok:
        metered_item_id = _get_metered_subscription_item_id(subscription)
        if metered_item_id:
            set_stripe_metered_item_id(tenant_id, metered_item_id)
    return ok


def _get_metered_subscription_item_id(subscription: object) -> str | None:
    """
    Retourne le subscription item id (metered) depuis subscription.items.data.
    Si STRIPE_METERED_PRICE_ID est défini : item dont price.id == STRIPE_METERED_PRICE_ID.
    Sinon : premier item dont price.recurring.usage_type == 'metered'.
    """
    metered_price_id = (os.environ.get("STRIPE_METERED_PRICE_ID") or "").strip()
    if not hasattr(subscription, "items") or not subscription.items or not getattr(subscription.items, "data", None):
        return None
    fallback_item_id = None
    for item in subscription.items.data or []:
        price = getattr(item, "price", None)
        if not price:
            continue
        pid = (getattr(price, "id", None) or "").strip()
        recurring = getattr(price, "recurring", None)
        is_metered = recurring and getattr(recurring, "usage_type", None) == "metered"
        if metered_price_id:
            if pid == metered_price_id:
                return (getattr(item, "id", None) or "").strip() or None
        elif is_metered:
            fallback_item_id = (getattr(item, "id", None) or "").strip() or None
            if fallback_item_id:
                return fallback_item_id
    return fallback_item_id


@router.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    """
    Webhook Stripe. Utilise le body brut (bytes) pour vérification signature STRIPE_WEBHOOK_SECRET.
    Idempotence + concurrence : INSERT event_id d'abord ; si conflit (déjà présent) → 200 sans retraitement.
    """
    secret = (os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()
    if not secret:
        logger.warning("STRIPE_WEBHOOK_SECRET not set, rejecting webhook")
        return JSONResponse(status_code=503, content={"detail": "Webhook not configured"})
    # Raw body obligatoire : Stripe signe le payload brut (pas de JSON parsé avant construct_event).
    payload = await request.body()
    sig = request.headers.get("stripe-signature") or ""
    if not sig:
        return JSONResponse(status_code=400, content={"detail": "Missing stripe-signature"})
    try:
        import stripe
        event = stripe.Webhook.construct_event(payload, sig, secret)
    except ValueError as e:
        logger.warning("stripe webhook invalid payload: %s", e)
        return JSONResponse(status_code=400, content={"detail": "Invalid payload"})
    except Exception as e:
        logger.warning("stripe webhook signature error: %s", e)
        return JSONResponse(status_code=400, content={"detail": "Invalid signature"})
    event_id = (getattr(event, "id", None) or "").strip()
    if event_id and not try_acquire_stripe_event(event_id):
        return {"received": True}
    typ = getattr(event, "type", None) or ""
    data = getattr(event, "data", None)
    obj = getattr(data, "object", None) if data else None
    try:
        if typ == "customer.subscription.created" or typ == "customer.subscription.updated":
            if obj:
                status = (getattr(obj, "status", None) or "").strip()
                ok = _sync_subscription(obj)
                # Reprise de paiement : si subscription repasse active/trialing → lever suspension (évite client payé bloqué).
                if ok and status in ("active", "trialing"):
                    customer_id = getattr(obj, "customer", None)
                    if hasattr(customer_id, "id"):
                        customer_id = customer_id.id
                    customer_id = (customer_id or "").strip()
                    if customer_id:
                        tid = tenant_id_by_stripe_customer_id(customer_id)
                        if tid is not None:
                            set_tenant_unsuspended(tid)
                            from backend.log_events import TENANT_UNSUSPENDED_STRIPE_PAYMENT
                            logger.info("TENANT_UNSUSPENDED_STRIPE_PAYMENT tenant_id=%s status=%s", tid, status, extra={"event": TENANT_UNSUSPENDED_STRIPE_PAYMENT})
        elif typ == "customer.subscription.deleted":
            if obj:
                customer_id = getattr(obj, "customer", None)
                if hasattr(customer_id, "id"):
                    customer_id = customer_id.id
                customer_id = (customer_id or "").strip()
                if customer_id:
                    tenant_id = tenant_id_by_stripe_customer_id(customer_id)
                    if tenant_id is not None:
                        clear_subscription(tenant_id, set_status_canceled=True)
        elif typ == "invoice.paid":
            pass  # optional: last_paid_at
        elif typ == "invoice.payment_failed":
            if obj and getattr(obj, "customer", None):
                cid = getattr(obj.customer, "id", None) or obj.customer
                cid = (cid or "").strip()
                if cid:
                    tenant_id = tenant_id_by_stripe_customer_id(cid)
                    if tenant_id is not None:
                        update_billing_status(tenant_id, "past_due")
        elif typ == "checkout.session.completed":
            if obj:
                customer_id = getattr(obj, "customer", None) or getattr(obj, "customer_email", None)
                if hasattr(customer_id, "id"):
                    customer_id = customer_id.id
                customer_id = (customer_id or "").strip()
                sub_id = (getattr(obj, "subscription", None) or "").strip()
                if customer_id and sub_id:
                    tenant_id = tenant_id_by_stripe_customer_id(customer_id)
                    if tenant_id is None and getattr(obj, "metadata", None) and getattr(obj.metadata, "get", None):
                        tid = (obj.metadata.get("tenant_id") or "").strip()
                        if tid.isdigit():
                            tenant_id = int(tid)
                    if tenant_id is not None:
                        import stripe
                        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
                        try:
                            sub = stripe.Subscription.retrieve(sub_id)
                            _sync_subscription(sub)
                        except Exception as e:
                            logger.warning("checkout.session.completed sync subscription: %s", e)
    except Exception as e:
        logger.exception("stripe webhook handler: %s", e)
        return JSONResponse(status_code=500, content={"detail": "Handler error"})
    return {"received": True}
