"""Router admin demo : intercepte les endpoints lecture critiques.

Monte ce router AVANT le router admin standard si ADMIN_DEMO_MODE=true.
FastAPI matche la premiere route trouvee, donc toutes les routes definies
ici prennent la priorite. Les endpoints non couverts (auth, write, ...)
tombent naturellement sur le router admin standard.

Les actions write ne sont volontairement pas mockees pour l'instant : si
un click ecrit (ex. changer plan), l'endpoint reel est appele et echoue
proprement (DB absente). Le frontend pourra detecter le mode demo via
GET /api/admin/_meta et afficher un avertissement.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from . import dataset as ds
from . import is_demo_mode

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Auth dependency : on importe celle de routes/admin.py pour rester coherent
# (cookie ou Bearer token)
# ---------------------------------------------------------------------------

from backend.routes.admin import _verify_admin  # noqa: E402  (import positionnel apres APIRouter)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_billing_for(tenant: ds.DemoTenant) -> Dict[str, Any]:
    plan = ds.PLANS[tenant.plan_key]
    period_end = ds.get_now() + timedelta(days=12)
    period_start = period_end - timedelta(days=30)
    return {
        "tenant_id": tenant.tenant_id,
        "stripe_customer_id": tenant.stripe_customer_id,
        "stripe_subscription_id": tenant.stripe_subscription_id,
        "billing_status": tenant.billing_status,
        "plan_key": tenant.plan_key,
        "plan_name": plan["name"],
        "price_eur": plan["price_eur"],
        "current_period_start": ds.iso(period_start),
        "current_period_end": ds.iso(period_end),
        "trial_ends_at": ds.iso(period_end) if tenant.billing_status == "trialing" else None,
        "updated_at": ds.iso(ds.get_now()),
    }


def _build_quota_for(tenant: ds.DemoTenant) -> Dict[str, Any]:
    plan = ds.PLANS[tenant.plan_key]
    used = tenant.used_minutes_month
    included = plan["included_minutes_month"]
    over = max(0, used - included)
    return {
        "tenant_id": tenant.tenant_id,
        "month_utc": ds.get_now().strftime("%Y-%m"),
        "plan_key": tenant.plan_key,
        "included_minutes_month": included,
        "used_minutes_month": round(used, 1),
        "extra_minutes": round(over, 1),
        "extra_minute_eur": plan["extra_minute_eur"],
        "extra_amount_eur": round(over * plan["extra_minute_eur"], 2),
        "used_pct": round((used / included * 100) if included else 0, 1),
    }


def _build_usage_for(tenant: ds.DemoTenant) -> Dict[str, Any]:
    return {
        "tenant_id": tenant.tenant_id,
        "month_utc": ds.get_now().strftime("%Y-%m"),
        "minutes_total": round(tenant.used_minutes_month, 1),
        "minutes": round(tenant.used_minutes_month, 1),  # alias UI
        "cost_usd": round(tenant.cost_usd_month, 4),
        "cost_currency": "USD",
    }


def _build_invoices_for(tenant: ds.DemoTenant) -> List[Dict[str, Any]]:
    """Retourne 3 factures simulees."""
    if not tenant.stripe_customer_id:
        return []
    out = []
    plan = ds.PLANS[tenant.plan_key]
    for i in range(3):
        created_dt = ds.get_now() - timedelta(days=30 * (i + 1) - 5)
        status = "paid" if not (tenant.billing_status == "past_due" and i == 0) else "open"
        out.append({
            "id": f"in_demo_{tenant.tenant_id:03d}_{i}",
            "created": int(created_dt.timestamp()),
            "amount_due": float(plan["price_eur"]),
            "amount_paid": float(plan["price_eur"]) if status == "paid" else 0.0,
            "currency": "eur",
            "status": status,
            "invoice_pdf": "https://example.invalid/demo.pdf",
            "hosted_invoice_url": "https://example.invalid/demo",
            "period_start": int((created_dt - timedelta(days=30)).timestamp()),
            "period_end": int(created_dt.timestamp()),
        })
    return out


def _build_call_item(c: ds.DemoCall, include_tenant_name: bool = False) -> Dict[str, Any]:
    item = {
        "tenant_id": c.tenant_id,
        "call_id": c.call_id,
        "customer_number": c.customer_number,
        "started_at": ds.iso(c.started_at),
        "ended_at": ds.iso(c.ended_at),
        "duration_min": round(c.duration_sec / 60.0, 2),
        "duration_sec": c.duration_sec,
        "result": c.result,
        "ended_reason": c.ended_reason,
        "last_event_at": ds.iso(c.ended_at),
        "cost_usd": c.cost_usd,
    }
    if include_tenant_name:
        t = ds.get_tenant(c.tenant_id)
        item["tenant_name"] = t.name if t else None
    return item


# ---------------------------------------------------------------------------
# Meta endpoint (utilise par le frontend pour afficher le badge)
# Cet endpoint est volontairement sans auth : il sert juste a verifier le
# flag, pas a exposer de donnees.
# ---------------------------------------------------------------------------


@router.get("/api/admin/_meta")
def admin_meta():
    """Indique au frontend si on est en mode demo (pas d'auth requise)."""
    return {
        "demo_mode": is_demo_mode(),
        "tenants_count": len(ds.get_tenants()) if is_demo_mode() else None,
        "dataset_label": "Dataset factice (8 cabinets, 60+ appels, 12 leads)",
    }


@router.get("/api/admin/twilio/numbers")
def demo_twilio_numbers(_: None = Depends(_verify_admin)):
    """Retourne une liste fictive de numeros Twilio disponibles pour le wizard."""
    return [
        {"number": "+33186652301", "friendly": "Paris 01", "available": True},
        {"number": "+33186652302", "friendly": "Paris 02", "available": True},
        {"number": "+33186652303", "friendly": "Paris 03", "available": True},
        {"number": "+33486990511", "friendly": "Lyon 04", "available": True},
        {"number": "+33586990611", "friendly": "Marseille 05", "available": True},
    ]


# ---------------------------------------------------------------------------
# Tenants
# ---------------------------------------------------------------------------


@router.get("/api/admin/tenants")
def demo_list_tenants(
    include_inactive: int = Query(0),
    _: None = Depends(_verify_admin),
):
    items = [t.to_summary() for t in ds.get_tenants(include_inactive=bool(include_inactive))]
    return {"tenants": items}


@router.get("/api/admin/tenants/enriched")
def demo_tenants_enriched(
    month: Optional[str] = Query(None),
    _: None = Depends(_verify_admin),
):
    tenants_out = []
    for t in ds.get_tenants(include_inactive=True):
        plan = ds.PLANS[t.plan_key]
        used = t.used_minutes_month
        included = plan["included_minutes_month"]
        used_pct = round((used / included * 100) if included else 0, 1)

        # Tech health : critical si suspended ou no vapi or no transfer
        tech_status = "ok"
        if t.status == "suspended":
            tech_status = "critical"
        elif (not t.vapi_assistant_id) or (not t.transfer_number) or (t.calendar_status == "not_configured"):
            tech_status = "critical"
        elif t.error_count_window >= 3 or used_pct > 90:
            tech_status = "warning"

        tenants_out.append({
            "tenant_id": t.tenant_id,
            "name": t.name,
            "status": t.status,
            "contact_email": t.contact_email,
            "created_at": ds.iso(t.created_at),
            "plan_key": t.plan_key,
            "billing_status": t.billing_status,
            "stripe_customer_id": t.stripe_customer_id,
            "stripe_subscription_id": t.stripe_subscription_id,
            "mrr_eur": float(plan["price_eur"]) if t.billing_status in ("active", "trialing") else 0.0,
            "vapi_assistant_id": t.vapi_assistant_id,
            "primary_did": t.primary_did,
            "voice_numbers": [t.primary_did] if t.primary_did else [],
            "used_minutes_month": round(used, 1),
            "included_minutes_month": included,
            "used_pct": used_pct,
            "cost_usd_month": round(t.cost_usd_month, 2),
            "last_event_at": ds.iso(t.last_event_at),
            "tech_status": tech_status,
        })
    return {
        "month_utc": month or ds.get_now().strftime("%Y-%m"),
        "tenants": tenants_out,
    }


@router.get("/api/admin/tenants/{tenant_id}")
def demo_get_tenant(
    tenant_id: int,
    _: None = Depends(_verify_admin),
):
    t = ds.get_tenant(tenant_id)
    if not t:
        raise HTTPException(404, "Tenant not found (demo)")
    return t.to_detail()


@router.get("/api/admin/tenants/{tenant_id}/dashboard")
def demo_tenant_dashboard(
    tenant_id: int,
    _: None = Depends(_verify_admin),
):
    t = ds.get_tenant(tenant_id)
    if not t:
        raise HTTPException(404, "Tenant not found (demo)")

    # Compteurs 7 derniers jours
    calls_7d = ds.get_calls(tenant_id=tenant_id, days=7, limit=1000)
    counters_7d = {
        "calls_total": len(calls_7d),
        "bookings_confirmed": sum(1 for c in calls_7d if c.result == "rdv"),
        "transfers": sum(1 for c in calls_7d if c.result == "transfer"),
        "abandons": sum(1 for c in calls_7d if c.result == "abandoned"),
    }

    last_call = None
    last_booking = None
    if calls_7d:
        first = calls_7d[0]
        last_call = {
            "call_id": first.call_id,
            "created_at": ds.iso(first.started_at),
            "outcome": first.result,
            "motif": first.motif,
            "name": first.patient_name,
        }
        bookings = [c for c in calls_7d if c.result == "rdv"]
        if bookings:
            b = bookings[0]
            last_booking = {
                "name": b.patient_name,
                "slot_label": (b.started_at + timedelta(days=2)).strftime("%A %d %B %Hh%M"),
                "source": "vapi",
            }

    transfer_reasons = []
    transfer_calls = [c for c in calls_7d if c.result == "transfer"]
    if transfer_calls:
        reasons = {}
        for c in transfer_calls:
            reasons[c.motif] = reasons.get(c.motif, 0) + 1
        transfer_reasons = [
            {"reason": k, "count": v} for k, v in sorted(reasons.items(), key=lambda x: -x[1])[:5]
        ]

    service_status = "online"
    if t.status == "suspended":
        service_status = "offline"
    elif not t.vapi_assistant_id or not t.primary_did:
        service_status = "unknown"

    return {
        "tenant_id": tenant_id,
        "service_status": {"status": service_status, "last_event_at": ds.iso(t.last_event_at)},
        "counters_7d": counters_7d,
        "last_call": last_call,
        "last_booking": last_booking,
        "transfer_reasons": {"top_transferred": transfer_reasons},
    }


@router.get("/api/admin/tenants/{tenant_id}/technical-status")
def demo_tenant_technical_status(
    tenant_id: int,
    _: None = Depends(_verify_admin),
):
    t = ds.get_tenant(tenant_id)
    if not t:
        raise HTTPException(404, "Tenant not found (demo)")
    last_event_iso = ds.iso(t.last_event_at) if t.last_event_at else None
    last_event_ago = None
    if t.last_event_at:
        delta = ds.get_now() - t.last_event_at
        if delta.total_seconds() < 3600:
            last_event_ago = f"il y a {int(delta.total_seconds() / 60)} min"
        elif delta.total_seconds() < 86400:
            last_event_ago = f"il y a {int(delta.total_seconds() / 3600)} h"
        else:
            last_event_ago = f"il y a {delta.days} j"

    return {
        "tenant_id": tenant_id,
        "did": t.primary_did,
        "routing_status": "active" if t.primary_did else "missing",
        "vapi_assistant_id": t.vapi_assistant_id,
        "service_agent": "online" if t.status == "active" else "offline",
        "calendar_status": t.calendar_status,
        "calendar_provider": t.calendar_provider,
        "last_event_at": last_event_iso,
        "last_event_ago": last_event_ago,
        "call_lock_timeout_rate_pct": 0.5,
        "call_lock_timeout_alert": False,
    }


@router.get("/api/admin/tenants/{tenant_id}/billing")
def demo_tenant_billing(
    tenant_id: int,
    _: None = Depends(_verify_admin),
):
    t = ds.get_tenant(tenant_id)
    if not t:
        raise HTTPException(404, "Tenant not found (demo)")
    return _build_billing_for(t)


@router.get("/api/admin/tenants/{tenant_id}/usage")
def demo_tenant_usage(
    tenant_id: int,
    month: Optional[str] = Query(None),
    _: None = Depends(_verify_admin),
):
    t = ds.get_tenant(tenant_id)
    if not t:
        raise HTTPException(404, "Tenant not found (demo)")
    return _build_usage_for(t)


@router.get("/api/admin/tenants/{tenant_id}/quota")
def demo_tenant_quota(
    tenant_id: int,
    month: Optional[str] = Query(None),
    _: None = Depends(_verify_admin),
):
    t = ds.get_tenant(tenant_id)
    if not t:
        raise HTTPException(404, "Tenant not found (demo)")
    q = _build_quota_for(t)
    # Compatibilite : certaines pages utilisent `used` / `included`
    q["used"] = q["used_minutes_month"]
    q["included"] = q["included_minutes_month"]
    return q


@router.get("/api/admin/tenants/{tenant_id}/billing/invoices")
def demo_tenant_invoices(
    tenant_id: int,
    _: None = Depends(_verify_admin),
):
    t = ds.get_tenant(tenant_id)
    if not t:
        raise HTTPException(404, "Tenant not found (demo)")
    return {"items": _build_invoices_for(t)}


@router.get("/api/admin/tenants/{tenant_id}/activity")
def demo_tenant_activity(
    tenant_id: int,
    limit: int = Query(50),
    _: None = Depends(_verify_admin),
):
    t = ds.get_tenant(tenant_id)
    if not t:
        raise HTTPException(404, "Tenant not found (demo)")
    calls = ds.get_calls(tenant_id=tenant_id, days=30, limit=limit)
    items = []
    for c in calls:
        items.append({
            "event": ds.EVENT_BY_RESULT.get(c.result, "call"),
            "created_at": ds.iso(c.started_at),
            "date": ds.iso(c.started_at),
            "meta": {"call_id": c.call_id, "motif": c.motif},
        })
    return {"items": items}


@router.get("/api/admin/tenants/{tenant_id}/faq")
def demo_tenant_faq(
    tenant_id: int,
    _: None = Depends(_verify_admin),
):
    t = ds.get_tenant(tenant_id)
    if not t:
        raise HTTPException(404, "Tenant not found (demo)")
    return [
        {
            "question": "Quels sont vos horaires d'ouverture ?",
            "answer": "Le cabinet est ouvert du lundi au vendredi de 8h00 a 19h00.",
        },
        {
            "question": "Acceptez-vous les nouveaux patients ?",
            "answer": "Oui, sous reserve de disponibilite. Demandez un rendez-vous au standard.",
        },
        {
            "question": "Comment annuler un rendez-vous ?",
            "answer": "Vous pouvez annuler en rappelant le standard au minimum 24h a l'avance.",
        },
    ]


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------


@router.get("/api/admin/calls")
def demo_calls(
    tenant_id: Optional[int] = Query(None),
    days: int = Query(7, ge=1, le=90),
    result: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    cursor: Optional[str] = Query(None),
    _: None = Depends(_verify_admin),
):
    calls = ds.get_calls(tenant_id=tenant_id, days=days, result=result, limit=limit)
    items = [_build_call_item(c, include_tenant_name=tenant_id is None) for c in calls]
    return {
        "items": items,
        "next_cursor": None,
        "has_more": False,
        "count": len(items),
    }


@router.get("/api/admin/tenants/{tenant_id}/calls/{call_id}")
def demo_call_detail(
    tenant_id: int,
    call_id: str,
    _: None = Depends(_verify_admin),
):
    c = ds.get_call(tenant_id, call_id)
    if not c:
        raise HTTPException(404, "Call not found (demo)")
    t = ds.get_tenant(tenant_id)

    timeline = [
        {
            "event": "call_started",
            "created_at": ds.iso(c.started_at),
            "meta": {"customer_number": c.customer_number, "ended_reason": None},
        }
    ]
    if c.transcript:
        timeline.append({
            "event": "transcript_first_message",
            "created_at": c.transcript[0]["created_at"],
            "meta": {"role": c.transcript[0]["role"]},
        })
    if c.result == "rdv":
        timeline.append({
            "event": "booking_confirmed",
            "created_at": ds.iso(c.ended_at - timedelta(seconds=20)),
            "meta": {"motif": c.motif, "name": c.patient_name},
        })
    elif c.result == "transfer":
        timeline.append({
            "event": "transferred_human",
            "created_at": ds.iso(c.ended_at - timedelta(seconds=15)),
            "meta": {"target": t.transfer_number if t else None},
        })
    elif c.result == "abandoned":
        timeline.append({
            "event": "user_abandon",
            "created_at": ds.iso(c.ended_at),
            "meta": {},
        })
    elif c.result == "error":
        timeline.append({
            "event": "anti_loop_trigger",
            "created_at": ds.iso(c.ended_at - timedelta(seconds=10)),
            "meta": {"reason": "loop_detected"},
        })
    timeline.append({
        "event": "call_ended",
        "created_at": ds.iso(c.ended_at),
        "meta": {"ended_reason": c.ended_reason, "duration_sec": c.duration_sec},
    })

    return {
        "tenant_id": tenant_id,
        "tenant_name": t.name if t else None,
        "call_id": c.call_id,
        "customer_number": c.customer_number,
        "started_at": ds.iso(c.started_at),
        "ended_at": ds.iso(c.ended_at),
        "duration_min": round(c.duration_sec / 60.0, 2),
        "duration_sec": c.duration_sec,
        "result": c.result,
        "ended_reason": c.ended_reason,
        "cost_usd": c.cost_usd,
        "events": timeline,
        "timeline": timeline,  # alias
        "transcript": c.transcript,
    }


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------


@router.get("/api/admin/leads")
def demo_leads_list(
    status: Optional[str] = Query(None),
    enterprise: Optional[int] = Query(None),
    _: None = Depends(_verify_admin),
):
    items = ds.get_leads(status=status, enterprise_only=(enterprise == 1))
    return {"leads": items}


@router.get("/api/admin/leads/count-new")
def demo_leads_count_new(_: None = Depends(_verify_admin)):
    items = ds.get_leads(status="new")
    return {"count": len(items)}


@router.get("/api/admin/leads/{lead_id}")
def demo_lead_detail(
    lead_id: str,
    _: None = Depends(_verify_admin),
):
    lead = ds.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found (demo)")
    return lead


# ---------------------------------------------------------------------------
# Stats globaux (dashboard)
# ---------------------------------------------------------------------------


def _global_stats(window_days: int) -> Dict[str, Any]:
    cutoff = ds.get_now() - timedelta(days=window_days)
    calls = [c for c in ds.get_calls(days=window_days, limit=10_000)]

    by_result: Dict[str, int] = {}
    minutes_total = 0.0
    cost_total = 0.0
    for c in calls:
        by_result[c.result] = by_result.get(c.result, 0) + 1
        minutes_total += c.duration_sec / 60.0
        cost_total += c.cost_usd

    tenants_all = ds.get_tenants(include_inactive=True)
    return {
        "window_days": window_days,
        "tenants_total": len(tenants_all),
        "tenants_active": sum(1 for t in tenants_all if t.status == "active"),
        "calls_total": len(calls),
        "calls_abandoned": by_result.get("abandoned", 0),
        "appointments_total": by_result.get("rdv", 0),
        "transfers_total": by_result.get("transfer", 0),
        "errors_total": by_result.get("error", 0),
        "minutes_total": round(minutes_total, 1),
        "cost_usd_total": round(cost_total, 2),
        "last_activity_at": ds.iso(calls[0].started_at) if calls else None,
    }


@router.get("/api/admin/stats/global")
def demo_stats_global(
    window_days: int = Query(30, ge=1, le=180),
    _: None = Depends(_verify_admin),
):
    return _global_stats(window_days)


def _delta(curr: float, prev: float) -> Dict[str, Any]:
    if not prev:
        return {"prev": prev, "delta_pct": None, "trend": "flat"}
    pct = round(((curr - prev) / prev) * 100, 1)
    if abs(pct) < 2:
        trend = "flat"
    elif pct > 0:
        trend = "up"
    else:
        trend = "down"
    return {"prev": prev, "delta_pct": pct, "trend": trend}


@router.get("/api/admin/stats/dashboard-payload")
def demo_dashboard_payload(
    window_days: int = Query(30, ge=7, le=90),
    _: None = Depends(_verify_admin),
):
    current = _global_stats(window_days)
    previous = _global_stats(window_days * 2)
    # previous = doubled - current (recalcul propre)
    prev = {}
    for k in (
        "calls_total",
        "appointments_total",
        "transfers_total",
        "minutes_total",
        "cost_usd_total",
        "errors_total",
        "calls_abandoned",
    ):
        prev[k] = max(0, previous.get(k, 0) - current.get(k, 0))
    deltas = {k: _delta(current.get(k, 0), prev.get(k, 0)) for k in prev}

    # Timeseries fictive : volume calls/jour
    series = []
    for i in range(window_days, 0, -1):
        day = ds.get_now() - timedelta(days=i)
        n = sum(1 for c in ds._CALLS if c.started_at.date() == day.date())  # type: ignore
        series.append({"date": day.strftime("%Y-%m-%d"), "calls": n})

    # Top tenants (calls + cost)
    by_tenant_calls: Dict[int, int] = {}
    by_tenant_cost: Dict[int, float] = {}
    for c in ds._CALLS:  # type: ignore
        if c.started_at < ds.get_now() - timedelta(days=window_days):
            continue
        by_tenant_calls[c.tenant_id] = by_tenant_calls.get(c.tenant_id, 0) + 1
        by_tenant_cost[c.tenant_id] = by_tenant_cost.get(c.tenant_id, 0.0) + c.cost_usd

    top_calls = sorted(by_tenant_calls.items(), key=lambda x: -x[1])[:10]
    top_cost = sorted(by_tenant_cost.items(), key=lambda x: -x[1])[:10]

    def _enrich(items, value_key):
        out = []
        for tid, v in items:
            t = ds.get_tenant(tid)
            out.append({
                "tenant_id": tid,
                "tenant_name": t.name if t else f"#{tid}",
                value_key: round(v, 2) if isinstance(v, float) else v,
            })
        return out

    return {
        "global": current,
        "previous": prev,
        "deltas": deltas,
        "timeseries": series,
        "topTenantsCalls": _enrich(top_calls, "calls"),
        "topTenantsCost": _enrich(top_cost, "cost_usd"),
        "billing": _billing_snapshot(),
        "activationQueue": _activation_queue(8),
    }


def _billing_snapshot() -> Dict[str, Any]:
    tenants = ds.get_tenants(include_inactive=True)
    plans_breakdown = {}
    mrr_eur = 0.0
    for t in tenants:
        plan = ds.PLANS[t.plan_key]
        plans_breakdown[t.plan_key] = plans_breakdown.get(t.plan_key, 0) + 1
        if t.billing_status == "active":
            mrr_eur += plan["price_eur"]
        elif t.billing_status == "trialing":
            mrr_eur += 0
    return {
        "month_utc": ds.get_now().strftime("%Y-%m"),
        "mrr_eur": round(mrr_eur, 2),
        "active_subscriptions": sum(1 for t in tenants if t.billing_status == "active"),
        "trialing": sum(1 for t in tenants if t.billing_status == "trialing"),
        "past_due": sum(1 for t in tenants if t.billing_status == "past_due"),
        "canceled": sum(1 for t in tenants if t.billing_status == "canceled"),
        "plans_breakdown": plans_breakdown,
        "cost_usd_this_month": round(sum(t.cost_usd_month for t in tenants), 2),
    }


def _activation_queue(limit: int = 8) -> List[Dict[str, Any]]:
    """Items prioritaires : tenants avec config incomplete + leads qualifies."""
    out = []
    for t in ds.get_tenants(include_inactive=True):
        if t.status != "active":
            continue
        if not t.vapi_assistant_id:
            out.append({
                "type": "missing_vapi",
                "priority": "high",
                "title": f"{t.name} : Vapi assistant manquant",
                "tenantId": t.tenant_id,
                "tenantName": t.name,
                "reason": "Aucun assistant Vapi configure",
                "createdAt": ds.iso(t.created_at),
            })
        elif not t.transfer_number:
            out.append({
                "type": "missing_transfer",
                "priority": "medium",
                "title": f"{t.name} : numero de transfert manquant",
                "tenantId": t.tenant_id,
                "tenantName": t.name,
                "reason": "Pas de numero de transfert humain",
                "createdAt": ds.iso(t.created_at),
            })
        elif t.calendar_status == "not_configured":
            out.append({
                "type": "missing_calendar",
                "priority": "medium",
                "title": f"{t.name} : agenda non configure",
                "tenantId": t.tenant_id,
                "tenantName": t.name,
                "reason": "Calendar Google non connecte",
                "createdAt": ds.iso(t.created_at),
            })
    # Ajout leads qualifies
    for lead in ds.get_leads(status="new", enterprise_only=True):
        out.append({
            "type": "lead_enterprise",
            "priority": "high",
            "title": f"Lead grand compte : {lead['email']}",
            "leadId": lead["id"],
            "tenantId": None,
            "reason": lead.get("medical_specialty_label") or "Specialite non precisee",
            "createdAt": lead["created_at"],
        })
    return out[:limit]


@router.get("/api/admin/stats/billing-snapshot")
def demo_billing_snapshot(_: None = Depends(_verify_admin)):
    return _billing_snapshot()


@router.get("/api/admin/stats/platform-health")
def demo_platform_health(_: None = Depends(_verify_admin)):
    return {
        "overall": "ok",
        "services": {
            "backend": {"status": "ok", "checked_at": ds.iso(ds.get_now())},
            "vapi": {"status": "ok", "checked_at": ds.iso(ds.get_now())},
            "twilio": {"status": "ok", "checked_at": ds.iso(ds.get_now())},
            "stripe": {"status": "ok", "checked_at": ds.iso(ds.get_now())},
            "postmark": {"status": "ok", "checked_at": ds.iso(ds.get_now())},
            "calendar": {"status": "ok", "checked_at": ds.iso(ds.get_now())},
        },
        "indicators": {
            "errors_24h": 2,
            "failed_calls_24h": 5,
            "last_event_at": ds.iso(ds.get_now() - timedelta(minutes=12)),
        },
    }


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


@router.get("/api/admin/stats/operations-snapshot")
def demo_operations_snapshot(
    window_days: int = Query(7, ge=1, le=30),
    _: None = Depends(_verify_admin),
):
    tenants = ds.get_tenants(include_inactive=True)
    cutoff = ds.get_now() - timedelta(days=window_days)

    # Past due
    past_due = []
    for t in tenants:
        if t.billing_status == "past_due":
            past_due.append({
                "tenant_id": t.tenant_id,
                "name": t.name,
                "billing_status": "past_due",
                "current_period_end": ds.iso(ds.get_now() + timedelta(days=5)),
            })

    # Quota
    over_80 = []
    over_100 = []
    for t in tenants:
        plan = ds.PLANS[t.plan_key]
        if not plan["included_minutes_month"]:
            continue
        used_pct = t.used_minutes_month / plan["included_minutes_month"] * 100
        info = {
            "tenant_id": t.tenant_id,
            "name": t.name,
            "plan_key": t.plan_key,
            "used_minutes": round(t.used_minutes_month, 1),
            "included_minutes": plan["included_minutes_month"],
            "used_pct": round(used_pct, 1),
        }
        if used_pct >= 100:
            over_100.append(info)
        elif used_pct >= 80:
            over_80.append(info)

    # Suspendus
    suspended_items = []
    for t in tenants:
        if t.suspension and t.status == "suspended":
            suspended_items.append({
                "tenant_id": t.tenant_id,
                "name": t.name,
                "reason": t.suspension["reason"],
                "mode": t.suspension["mode"],
                "suspended_at": t.suspension["suspended_at"],
            })

    # Erreurs
    error_calls = [c for c in ds._CALLS if c.result == "error" and c.started_at >= cutoff]  # type: ignore
    by_tenant: Dict[int, Dict[str, Any]] = {}
    for c in error_calls:
        e = by_tenant.setdefault(c.tenant_id, {"errors_total": 0, "last_error_at": c.started_at})
        e["errors_total"] += 1
        if c.started_at > e["last_error_at"]:
            e["last_error_at"] = c.started_at
    error_top = []
    for tid, info in sorted(by_tenant.items(), key=lambda x: -x[1]["errors_total"])[:5]:
        t = ds.get_tenant(tid)
        error_top.append({
            "tenant_id": tid,
            "name": t.name if t else f"#{tid}",
            "errors_total": info["errors_total"],
            "last_error_at": ds.iso(info["last_error_at"]),
        })

    # Couts
    cost_today = sum(t.cost_usd_today for t in tenants)
    cost_7d = sum(t.cost_usd_7d for t in tenants)
    cost_month = sum(t.cost_usd_month for t in tenants)

    def _top_cost(field: str, n: int = 5):
        return [
            {
                "tenant_id": t.tenant_id,
                "name": t.name,
                "cost_usd": round(getattr(t, field), 2),
            }
            for t in sorted(tenants, key=lambda x: -getattr(x, field))[:n]
            if getattr(t, field) > 0
        ]

    return {
        "window_days": window_days,
        "billing": {
            "month_utc": ds.get_now().strftime("%Y-%m"),
            "tenants_past_due": past_due,
            "cost_usd_this_month": round(cost_month, 2),
            "top_tenants_by_cost_this_month": _top_cost("cost_usd_month", 5),
        },
        "quota": {
            "month_utc": ds.get_now().strftime("%Y-%m"),
            "over_80": over_80,
            "over_100": over_100,
        },
        "suspensions": {
            "suspended_total": len(suspended_items),
            "items": suspended_items,
        },
        "cost": {
            "today_utc": {
                "date_utc": ds.get_now().strftime("%Y-%m-%d"),
                "total_usd": round(cost_today, 2),
                "top": _top_cost("cost_usd_today", 5),
            },
            "last_7d": {
                "window_days": 7,
                "total_usd": round(cost_7d, 2),
                "top": _top_cost("cost_usd_7d", 5),
            },
        },
        "errors": {
            "window_days": window_days,
            "errors_total": sum(int(t.error_count_window) for t in tenants),
            "top_tenants": error_top,
        },
    }


# ---------------------------------------------------------------------------
# Billing overview (page Billing)
# ---------------------------------------------------------------------------


@router.get("/api/admin/billing/overview")
def demo_billing_overview(
    month: Optional[str] = Query(None),
    _: None = Depends(_verify_admin),
):
    tenants = ds.get_tenants(include_inactive=True)
    rows = []
    for t in tenants:
        plan = ds.PLANS[t.plan_key]
        used_pct = (
            round(t.used_minutes_month / plan["included_minutes_month"] * 100, 1)
            if plan["included_minutes_month"]
            else 0
        )
        rows.append({
            "tenant_id": t.tenant_id,
            "name": t.name,
            "plan_key": t.plan_key,
            "billing_status": t.billing_status,
            "stripe_customer_id": t.stripe_customer_id,
            "stripe_subscription_id": t.stripe_subscription_id,
            "current_period_end": ds.iso(ds.get_now() + timedelta(days=12)),
            "mrr_eur": float(plan["price_eur"]) if t.billing_status == "active" else 0.0,
            "used_minutes_month": round(t.used_minutes_month, 1),
            "included_minutes_month": plan["included_minutes_month"],
            "used_pct": used_pct,
            "cost_usd_month": round(t.cost_usd_month, 4),
        })
    snapshot = _billing_snapshot()
    return {
        "month_utc": month or ds.get_now().strftime("%Y-%m"),
        "tenants": rows,
        "summary": snapshot,
    }


@router.get("/api/admin/billing/plans")
def demo_billing_plans(_: None = Depends(_verify_admin)):
    return {
        "plans": [
            {
                "key": p["key"],
                "name": p["name"],
                "price_eur": p["price_eur"],
                "included_minutes_month": p["included_minutes_month"],
                "extra_minute_eur": p["extra_minute_eur"],
                "stripe_price_id": p["stripe_price_id"],
            }
            for p in ds.PLANS.values()
        ]
    }


# ---------------------------------------------------------------------------
# Quality snapshot (vue admin/quality si utilisee)
# ---------------------------------------------------------------------------


@router.get("/api/admin/stats/quality-snapshot")
def demo_quality_snapshot(
    window_days: int = Query(7, ge=1, le=30),
    _: None = Depends(_verify_admin),
):
    calls = [c for c in ds.get_calls(days=window_days, limit=10_000)]
    total = len(calls)
    by_result: Dict[str, int] = {}
    for c in calls:
        by_result[c.result] = by_result.get(c.result, 0) + 1

    # Top tenants par categorie (count + last_at)
    def _top_for(result_key: str, n: int = 10):
        agg: Dict[int, Dict[str, Any]] = {}
        for c in calls:
            if c.result != result_key:
                continue
            e = agg.setdefault(c.tenant_id, {"count": 0, "last_at": c.started_at})
            e["count"] += 1
            if c.started_at > e["last_at"]:
                e["last_at"] = c.started_at
        rows = []
        for tid, info in sorted(agg.items(), key=lambda x: -x[1]["count"])[:n]:
            t = ds.get_tenant(tid)
            rows.append({
                "tenant_id": tid,
                "name": t.name if t else f"#{tid}",
                "count": info["count"],
                "last_at": ds.iso(info["last_at"]),
            })
        return rows

    abandons = by_result.get("abandoned", 0)
    return {
        "window_days": window_days,
        "generated_at": ds.iso(ds.get_now()),
        "kpis": {
            "calls_total": total,
            "appointments": by_result.get("rdv", 0),
            "transfers": by_result.get("transfer", 0),
            "abandons": abandons,
            "anti_loop": by_result.get("error", 0),
            "abandon_rate_pct": round((abandons / total * 100) if total else 0, 1),
        },
        "top": {
            "anti_loop": _top_for("error"),
            "abandons": _top_for("abandoned"),
            "transfers": _top_for("transfer"),
        },
    }
