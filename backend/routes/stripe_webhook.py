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


def _get_metered_price_ids_from_env() -> set:
    """Ensemble des price ids metered (STRIPE_PRICE_METERED_STARTER/GROWTH/PRO + legacy)."""
    ids = set()
    for key in ("STRIPE_PRICE_METERED_STARTER", "STRIPE_PRICE_METERED_GROWTH", "STRIPE_PRICE_METERED_PRO",
                "STRIPE_METERED_PRICE_ID", "STRIPE_PRICE_METERED_MINUTES"):
        v = (os.environ.get(key) or "").strip()
        if v:
            ids.add(v)
    return ids


def _get_subscription_items_list(subscription: object) -> list:
    """Extrait la liste des items depuis subscription (StripeObject ou dict)."""
    items_obj = None
    if hasattr(subscription, "items"):
        items_obj = subscription.items
    elif isinstance(subscription, dict):
        items_obj = subscription.get("items")
    # Accès dict (StripeObject supporte __getitem__)
    if items_obj is None and hasattr(subscription, "__getitem__"):
        try:
            items_obj = subscription["items"]
        except (KeyError, TypeError):
            pass
    if items_obj is None:
        return []
    data = None
    if hasattr(items_obj, "data"):
        data = items_obj.data
    elif isinstance(items_obj, dict):
        data = items_obj.get("data")
    elif hasattr(items_obj, "__getitem__"):
        try:
            data = items_obj["data"]
        except (KeyError, TypeError):
            pass
    if data is None:
        return []
    return list(data) if not isinstance(data, list) else data


def _subscription_items_debug(subscription: object) -> list[dict]:
    """Retourne [{item_id, price_id, usage_type}] pour diagnostic."""
    out = []
    items_list = _get_subscription_items_list(subscription)
    for item in items_list:
        item_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
        price = item.get("price") if isinstance(item, dict) else getattr(item, "price", None)
        if not price:
            out.append({"item_id": item_id, "price_id": None, "usage_type": None})
            continue
        if isinstance(price, str):
            out.append({"item_id": item_id, "price_id": price, "usage_type": "? (price not expanded)"})
        else:
            pid = price.get("id") if isinstance(price, dict) else getattr(price, "id", None)
            recurring = price.get("recurring") if isinstance(price, dict) else getattr(price, "recurring", None)
            usage_type = (recurring.get("usage_type") if isinstance(recurring, dict) else getattr(recurring, "usage_type", None)) if recurring else None
            out.append({"item_id": item_id, "price_id": pid, "usage_type": usage_type})
    return out


def resync_metered_item_for_tenant(tenant_id: int) -> dict:
    """
    Re-fetch subscription depuis Stripe (expand items.data.price) et met à jour stripe_metered_item_id.
    Utile pour backfill si webhook n'a pas persisté le metered item.
    Retourne {ok, stripe_metered_item_id, error, items_debug?}.
    """
    from backend.billing_pg import get_tenant_billing, set_stripe_metered_item_id
    billing = get_tenant_billing(tenant_id)
    if not billing:
        return {"ok": False, "stripe_metered_item_id": None, "error": "no_billing"}
    sub_id = (billing.get("stripe_subscription_id") or "").strip()
    if not sub_id:
        return {"ok": False, "stripe_metered_item_id": None, "error": "no_subscription"}
    try:
        sub = _retrieve_subscription_with_items(sub_id)
        items_list = _get_subscription_items_list(sub)
        if not items_list:
            items_list = _list_subscription_items(sub_id)
            sub = {"items": {"data": items_list}} if items_list else sub
        items_debug = _subscription_items_debug(sub)
        for d in items_debug:
            logger.info("resync_metered_item tenant_id=%s item=%s price=%s usage_type=%s",
                        tenant_id, d.get("item_id"), d.get("price_id"), d.get("usage_type"))
        metered_id = _get_metered_subscription_item_id(sub)
        if metered_id:
            set_stripe_metered_item_id(tenant_id, metered_id)
            logger.info("resync_metered_item tenant_id=%s sub=%s metered_item=%s", tenant_id, sub_id, metered_id)
            return {"ok": True, "stripe_metered_item_id": metered_id, "error": None}
        return {
            "ok": False,
            "stripe_metered_item_id": None,
            "error": "no_metered_item_in_subscription",
            "items_debug": items_debug,
            "expected_metered_price_ids": list(_get_metered_price_ids_from_env()),
        }
    except Exception as e:
        logger.warning("resync_metered_item tenant_id=%s error=%s", tenant_id, e)
        return {"ok": False, "stripe_metered_item_id": None, "error": str(e)}


def _retrieve_subscription_with_items(sub_id: str):
    """Re-fetch subscription avec expand items.data.price pour accéder à price.recurring.usage_type."""
    import stripe
    stripe.api_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    return stripe.Subscription.retrieve(sub_id, expand=["items.data.price"])


def _list_subscription_items(sub_id: str) -> list:
    """Liste les subscription items via API dédiée (plus fiable que expand)."""
    import stripe
    stripe.api_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    items = stripe.SubscriptionItem.list(subscription=sub_id, expand=["data.price"])
    return list(items.data) if items and getattr(items, "data", None) else []


def _get_metered_subscription_item_id(subscription: object) -> str | None:
    """
    Retourne le subscription item id (metered) depuis subscription.items.data.
    Si des STRIPE_PRICE_METERED_* sont définis : item dont price.id est dans cet ensemble.
    Sinon : premier item dont price.recurring.usage_type == 'metered'.
    Gère price objet ou dict (expand).
    """
    metered_price_ids = _get_metered_price_ids_from_env()
    items_list = _get_subscription_items_list(subscription)
    fallback_item_id = None
    for item in items_list:
        item_id = (item.get("id") if isinstance(item, dict) else getattr(item, "id", None)) or ""
        item_id = (item_id or "").strip()
        price = item.get("price") if isinstance(item, dict) else getattr(item, "price", None)
        if not price:
            continue
        # price peut être string (id), objet ou dict selon expand
        if isinstance(price, str):
            pid = price.strip()
            is_metered = pid in metered_price_ids if metered_price_ids else False
        else:
            pid = (price.get("id") if isinstance(price, dict) else getattr(price, "id", None)) or ""
            pid = (pid or "").strip()
            recurring = price.get("recurring") if isinstance(price, dict) else getattr(price, "recurring", None)
            usage_type = (recurring.get("usage_type") if isinstance(recurring, dict) else getattr(recurring, "usage_type", None)) if recurring else None
            is_metered = usage_type == "metered"
        if metered_price_ids and pid in metered_price_ids:
            return item_id or None
        if is_metered:
            fallback_item_id = item_id or None
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
                sub_id = (getattr(obj, "id", None) or "").strip()
                status = (getattr(obj, "status", None) or "").strip()
                # Re-fetch avec expand pour accéder à price.recurring.usage_type (event brut souvent sans expand)
                if sub_id:
                    try:
                        sub = _retrieve_subscription_with_items(sub_id)
                        ok = _sync_subscription(sub)
                    except Exception as e:
                        logger.warning("subscription.%s re-fetch failed: %s, fallback to event obj", typ.split(".")[-1], e)
                        ok = _sync_subscription(obj)
                else:
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
                sub_id = getattr(obj, "subscription", None)
                sub_id = getattr(sub_id, "id", sub_id) if sub_id else ""
                sub_id = (sub_id or "").strip() if isinstance(sub_id, str) else ""
                if customer_id and sub_id:
                    tenant_id = tenant_id_by_stripe_customer_id(customer_id)
                    if tenant_id is None and getattr(obj, "metadata", None) and getattr(obj.metadata, "get", None):
                        tid = (obj.metadata.get("tenant_id") or "").strip()
                        if tid.isdigit():
                            tenant_id = int(tid)
                    if tenant_id is not None:
                        try:
                            sub = _retrieve_subscription_with_items(sub_id)
                            _sync_subscription(sub)
                            metered_id = _get_metered_subscription_item_id(sub)
                            logger.info("checkout.session.completed sub=%s metered_item=%s items=%d",
                                        sub_id, metered_id or "none", len(getattr(getattr(sub, "items"), "data", None) or []))
                        except Exception as e:
                            logger.warning("checkout.session.completed sync subscription: %s", e)
    except Exception as e:
        logger.exception("stripe webhook handler: %s", e)
        return JSONResponse(status_code=500, content={"detail": "Handler error"})
    return {"received": True}
