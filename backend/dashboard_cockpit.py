# backend/dashboard_cockpit.py
"""Agrégations cockpit /api/admin/dashboard/* (importé depuis routes.admin après définition des helpers)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


DASHBOARD_PERIODS = frozenset({"24h", "7d", "30d", "month"})


def dash_normalize_period(period: Optional[str]) -> str:
    p = (period or "30d").strip()
    return p if p in DASHBOARD_PERIODS else "30d"


def dash_leads_cutoff_utc(period: str) -> datetime:
    """Instant de début (UTC) inclus pour compter les leads « nouveaux » dans la fenêtre cockpit."""
    now = datetime.now(timezone.utc)
    p = dash_normalize_period(period)
    if p == "24h":
        return now - timedelta(hours=24)
    if p == "7d":
        return now - timedelta(days=7)
    if p == "30d":
        return now - timedelta(days=30)
    if p == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return now - timedelta(days=7)


def dash_parse_dt_utc(val: Any) -> Optional[datetime]:
    """Parse une date renvoyée par PG ou sérialisée JSON vers UTC timezone-aware."""
    if val is None:
        return None
    if isinstance(val, datetime):
        dt = val
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    raw = str(val).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw).astimezone(timezone.utc)
    except Exception:
        return None


def dash_lead_activity_utc(row: dict) -> Optional[datetime]:
    """
    Dernière activité utile pour le bloc leads cockpit.
    Un re-commit wizard (même email) fait UPDATE et met à jour last_submitted_at sans toucher
    created_at : filtrer uniquement sur created_at faisait « disparaître » le lead de la fenêtre.
    """
    ts: List[datetime] = []
    for key in ("last_submitted_at", "updated_at", "created_at"):
        dt = dash_parse_dt_utc(row.get(key))
        if dt:
            ts.append(dt)
    return max(ts) if ts else None


def dash_pct_change(cur_val: Optional[float], prev_val: Optional[float]) -> Optional[float]:
    try:
        if cur_val is None or prev_val is None:
            return None
        cv = float(cur_val)
        pv = float(prev_val)
        if pv <= 0:
            return 100.0 if cv > 0 else None
        return round((cv - pv) / pv * 100.0, 1)
    except Exception:
        return None


def dash_fmt_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def dash_paired_intervals_utc(period: str) -> tuple[datetime, datetime, datetime, datetime]:
    now = datetime.now(timezone.utc)
    if period == "24h":
        cur_end = now
        cur_start = cur_end - timedelta(hours=24)
    elif period == "7d":
        cur_end = now
        cur_start = cur_end - timedelta(days=7)
    elif period == "month":
        cur_end = now
        cur_start = cur_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        cur_end = now
        cur_start = cur_end - timedelta(days=30)
    delta = cur_end - cur_start
    prev_end = cur_start
    prev_start = cur_start - delta
    return cur_start, cur_end, prev_start, prev_end


def dash_window_days(period: str) -> int:
    now = datetime.now(timezone.utc)
    fixed = {"24h": 1, "7d": 7, "30d": 30}.get(period)
    if fixed is not None:
        return fixed
    return max(1, now.day) if period == "month" else 30


def dash_ivr_between(ctx: Any, start_dt: datetime, end_dt: datetime) -> Dict[str, int]:
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    out = {"calls_handled_count": 0, "appointments_created_count": 0}
    if not url:
        return out
    start_s = dash_fmt_ts(start_dt)
    end_s = dash_fmt_ts(end_dt)
    try:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT call_id) AS c
                    FROM ivr_events
                    WHERE call_id IS NOT NULL AND TRIM(call_id) != ''
                      AND created_at >= %s AND created_at <= %s
                    """,
                    (start_s, end_s),
                )
                out["calls_handled_count"] = int((cur.fetchone() or {}).get("c") or 0)
                cur.execute(
                    """
                    SELECT COUNT(*) AS c FROM ivr_events
                    WHERE event = 'booking_confirmed'
                      AND created_at >= %s AND created_at <= %s
                    """,
                    (start_s, end_s),
                )
                out["appointments_created_count"] = int((cur.fetchone() or {}).get("c") or 0)
    except Exception as e:
        if "does not exist" not in str(e).lower():
            logger.warning("dashboard ivr_between: %s", e)
    return out


def dash_slots_appointment_between(ctx: Any, start_dt: datetime, end_dt: datetime) -> int:
    from backend import config

    if not getattr(config, "USE_PG_SLOTS", False):
        return 0
    url_slots = os.environ.get("DATABASE_URL") or os.environ.get("PG_SLOTS_URL")
    if not url_slots:
        return 0
    start_s = dash_fmt_ts(start_dt)
    end_s = dash_fmt_ts(end_dt)
    try:
        import psycopg

        with psycopg.connect(url_slots) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM appointments WHERE created_at >= %s AND created_at <= %s",
                    (start_s, end_s),
                )
                row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except Exception as e:
        logger.debug("dashboard appointments_between: %s", e)
        return 0


def dash_web_requests_between(start_dt: datetime, end_dt: datetime) -> int:
    """Handoffs hors canal téléphone + événements web/composer grossiers dans ivr_events."""
    total = 0
    start_s = dash_fmt_ts(start_dt)
    end_s = dash_fmt_ts(end_dt)
    url_tenants = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")
    if url_tenants:
        try:
            import psycopg

            with psycopg.connect(url_tenants) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COUNT(*) FROM human_handoffs
                        WHERE created_at >= %s::timestamptz AND created_at <= %s::timestamptz
                          AND LOWER(TRIM(COALESCE(channel, ''))) NOT IN ('', 'vocal', 'voice', 'phone')
                        """,
                        (start_s, end_s),
                    )
                    total += int((cur.fetchone() or [0])[0])
        except Exception as e:
            if "does not exist" not in str(e).lower():
                logger.debug("dashboard web_handoffs aggregate: %s", e)

    url_ev = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    if url_ev:
        try:
            import psycopg

            with psycopg.connect(url_ev) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COUNT(*) FROM ivr_events
                        WHERE created_at >= %s AND created_at <= %s
                          AND (
                                event ILIKE '%%web%%'
                                OR event ILIKE '%%composer%%'
                                OR event ILIKE '%%formulaire%%'
                              )
                          AND event NOT IN (
                              'booking_confirmed', 'user_abandon', 'abandon', 'hangup', 'user_hangup',
                              'transferred_human', 'transferred', 'transfer_human', 'transfer', 'anti_loop_trigger'
                          )
                        """,
                        (start_s, end_s),
                    )
                    total += int((cur.fetchone() or [0])[0])
        except Exception:
            pass
    return total


def dash_voice_and_cost_between(ctx: Any, start_dt: datetime, end_dt: datetime) -> tuple[float, float]:
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    if not url:
        return (0.0, 0.0)
    start_s = dash_fmt_ts(start_dt)
    end_s = dash_fmt_ts(end_dt)
    mins, cost_usd = ctx["_get_vapi_usage_for_window"](url, start_s, end_s, None)
    return (round(float(mins or 0), 1), round(float(cost_usd or 0), 4))


def dash_month_voice_and_included(
    ctx: Any,
) -> tuple[float, Optional[int], Optional[float]]:
    from backend.billing_pg import get_plan_included_minutes, get_tenant_billing

    now = datetime.now(timezone.utc)
    month_utc = now.strftime("%Y-%m")
    month_start = f"{month_utc}-01 00:00:00"
    try:
        y, mo = int(month_utc[:4]), int(month_utc[5:7])
        month_end = f"{y}-{mo + 1:02d}-01 00:00:00" if mo < 12 else f"{y + 1}-01-01 00:00:00"
    except ValueError:
        month_end = month_start

    used_by_tenant: Dict[int, float] = {}
    url_ev = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    if url_ev:
        try:
            import psycopg
            from psycopg.rows import dict_row

            with psycopg.connect(url_ev, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT tenant_id, COALESCE(SUM(duration_sec), 0) / 60.0 AS used_minutes
                        FROM vapi_call_usage
                        WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at < %s
                        GROUP BY tenant_id
                        """,
                        (month_start, month_end),
                    )
                    for r in cur.fetchall():
                        tid = r.get("tenant_id")
                        if tid is None:
                            continue
                        used_by_tenant[int(tid)] = float(r.get("used_minutes") or 0)
        except Exception as e:
            if "does not exist" not in str(e).lower():
                logger.debug("dashboard month vapi: %s", e)

    tenants = ctx["_get_tenant_list"](include_inactive=True)
    active_ids = [
        int(t["tenant_id"])
        for t in tenants or []
        if t.get("tenant_id") is not None and (t.get("status") or "active") == "active"
    ]

    voice_used_month = round(sum(used_by_tenant.get(int(tid), 0.0) for tid in active_ids), 1)
    included_sum = 0

    for tid in active_ids:
        try:
            d = ctx["_get_tenant_detail"](tid) or {}
            params = d.get("params") or {}
            plan_key = (params.get("plan_key") or "").strip()
            tb = get_tenant_billing(tid) if tid else {}
            if not plan_key and tb:
                plan_key = str((tb.get("plan_key") or "")).strip()
            plan_key = (plan_key or "free").lower()
            if plan_key == "custom":
                try:
                    cv = int(params.get("custom_included_minutes_month") or 0)
                    inc = cv if cv > 0 else get_plan_included_minutes("custom")
                except (TypeError, ValueError):
                    inc = get_plan_included_minutes("custom")
            else:
                inc = get_plan_included_minutes(plan_key)
            if inc and inc > 0:
                included_sum += int(inc)
        except Exception:
            continue

    usage_pct: Optional[float] = None
    if included_sum > 0:
        usage_pct = round(min(999.0, (voice_used_month / float(included_sum)) * 100.0), 1)

    # fallback plateau plateforme
    plat = os.environ.get("ADMIN_PLATFORM_INCLUDED_MINUTES")
    try:
        if included_sum <= 0 and plat and float(plat) > 0:
            fp = float(plat)
            included_sum = int(fp)
            usage_pct = round(min(999.0, (voice_used_month / fp) * 100.0), 1)
    except Exception:
        pass

    included_val: Optional[int] = included_sum if included_sum > 0 else None

    return (voice_used_month, included_val, usage_pct)


def dash_active_delta_month_pg() -> int:
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")
    if not url:
        return 0
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS c FROM tenants
                    WHERE COALESCE(status, 'active') = 'active'
                      AND created_at IS NOT NULL AND created_at >= %s
                    """,
                    (month_start,),
                )
                row = cur.fetchone()
        return int(row.get("c") or 0) if row else 0
    except Exception as e:
        if "does not exist" not in str(e).lower():
            logger.debug("dash_active_delta_month: %s", e)
        return 0


def dash_critical_count(ctx: Any, billing_snap: dict, ops_snap: dict, activation: List[dict], err_floor: int = 5) -> int:
    tids = set()
    for row in billing_snap.get("tenants_past_due") or []:
        if row.get("tenant_id") is not None:
            tids.add(int(row["tenant_id"]))
    for row in (ops_snap.get("quota") or {}).get("over_100") or []:
        if row.get("tenant_id") is not None:
            tids.add(int(row["tenant_id"]))
    for row in (ops_snap.get("errors") or {}).get("top_tenants") or []:
        if int(row.get("errors_total") or 0) >= err_floor and row.get("tenant_id") is not None:
            tids.add(int(row["tenant_id"]))
    for act in activation:
        pk = act.get("priority_key") or ""
        if pk in ("blocking_before_launch", "billing_risk") and act.get("tenant_id"):
            tids.add(int(act["tenant_id"]))
        if bool(act.get("call_lock_timeout_alert")) and act.get("tenant_id"):
            tids.add(int(act["tenant_id"]))
    return len(tids)


def dash_leads_block(ctx: Any, period: str = "7d") -> dict:
    from backend.leads_pg import count_new_leads, list_leads

    p = dash_normalize_period(period)
    leads_payload = list_leads(limit=400)
    leads: List[dict] = list(leads_payload.get("items") or [])
    window_cut = dash_leads_cutoff_utc(p)

    window_rows: List[dict] = []
    for row in leads:
        act = dash_lead_activity_utc(row)
        if act and act >= window_cut:
            window_rows.append(row)
    latest_sorted = sorted(
        window_rows,
        key=lambda r: dash_lead_activity_utc(r) or window_cut,
        reverse=True,
    )

    def _lead_row_compact(r: dict) -> dict:
        return {
            "id": r.get("id"),
            "name": (r.get("assistant_name") or r.get("email") or "").strip()[:120] or "Lead",
            "source": (r.get("source") or "landing_cta"),
            "status": str(r.get("status") or "new"),
            "note": str(r.get("primary_pain_point") or r.get("notes") or "")[:280],
            "created_at": str(r.get("created_at") or ""),
        }

    latest = [_lead_row_compact(r) for r in latest_sorted[:3]]
    if not latest and leads:
        latest = [
            _lead_row_compact(r)
            for r in sorted(leads, key=lambda rr: dash_lead_activity_utc(rr) or window_cut, reverse=True)[:3]
        ]

    return {
        "period": p,
        "new_leads_count": len(window_rows),
        "to_qualify_today_count": count_new_leads(),
        "latest": latest,
    }


def dash_watchlist_items(ctx: Any, period: str) -> List[dict]:
    wd = dash_window_days(period)
    out: List[dict] = []

    try:
        top_web = ctx["_get_stats_top_tenants"]("web_handoffs", wd, 8)["items"]
        for r in top_web[:4]:
            tid = r.get("tenant_id")
            if tid is None:
                continue
            out.append(
                {
                    "tenant_id": tid,
                    "tenant_name": r.get("name") or "",
                    "signal_type": "web_requests",
                    "label": "Demandes web",
                    "value": str(int(r.get("value") or 0)),
                    "trend": f"{wd}j",
                    "severity": "info",
                    "target_url": f"/admin/tenants/{tid}",
                }
            )
    except Exception:
        pass

    try:
        ops = ctx["_get_operations_snapshot"](window_days=min(wd, 30))
        for row in (ops.get("quota") or {}).get("over_100") or []:
            tid = row.get("tenant_id")
            if tid is None:
                continue
            pct = row.get("usage_pct")
            out.append(
                {
                    "tenant_id": tid,
                    "tenant_name": row.get("name") or f"Tenant #{tid}",
                    "signal_type": "minutes",
                    "label": "Minutes",
                    "value": str(int(float(row.get("used_minutes") or 0))),
                    "trend": f"{pct}% quota",
                    "severity": "critical",
                    "target_url": f"/admin/billing?tenant={tid}&sort=usage_desc",
                }
            )
    except Exception:
        pass

    try:
        quality = ctx["_get_quality_snapshot"](window_days=min(wd, 30))
        for row in (quality.get("top") or {}).get("anti_loop") or []:
            tid = row.get("tenant_id")
            if tid is None:
                continue
            out.append(
                {
                    "tenant_id": tid,
                    "tenant_name": row.get("name") or "",
                    "signal_type": "booking_errors",
                    "label": "Anti-loop",
                    "value": str(int(row.get("count") or 0)),
                    "trend": f"{quality.get('window_days')}j",
                    "severity": "warning",
                    "target_url": f"/admin/tenants/{tid}",
                }
            )
    except Exception:
        pass

    seen = set()
    uniq: List[dict] = []
    for item in out:
        key = (item.get("tenant_id"), item.get("label"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    return uniq[:24]


def dash_build_action_items(ctx: Any, period: str, severity_filter: Optional[str] = None) -> List[dict]:
    wd = max(7, min(90, dash_window_days(period)))
    billing = ctx["_get_billing_snapshot"]()
    ops = ctx["_get_operations_snapshot"](window_days=min(wd, 30))
    activation = ctx["_get_activation_queue"](40).get("items") or []

    items: List[dict] = []
    for row in (billing.get("tenants_past_due") or [])[:14]:
        tid = row.get("tenant_id")
        if tid is None:
            continue
        items.append(
            {
                "id": f"billing-{tid}",
                "severity": "critical",
                "type": "billing",
                "tenant_id": int(tid),
                "tenant_name": row.get("name") or f"Tenant #{tid}",
                "title": "Paiement en retard ou impayé",
                "description": f"Stripe·{row.get('billing_status') or 'past_due'}",
                "target_label": "Billing",
                "primary_action_label": "Voir fiche client",
                "primary_action_url": f"/admin/tenants/{tid}",
                "secondary_action_label": "Billing",
                "secondary_action_url": f"/admin/tenants/{tid}",
            }
        )

    for act in activation[:16]:
        tid = act.get("tenant_id")
        if tid is None:
            continue
        pk = act.get("priority_key") or ""
        critical = pk in ("blocking_before_launch", "billing_risk") or bool(act.get("call_lock_timeout_alert"))
        items.append(
            {
                "id": f"activation-{tid}",
                "severity": "critical" if critical else "warning",
                "type": "onboarding",
                "tenant_id": int(tid),
                "tenant_name": act.get("tenant_name") or f"Tenant #{tid}",
                "title": "Activation / dossier incomplet",
                "description": str(act.get("primary_reason") or "Étapes manquantes"),
                "target_label": "Cabinet",
                "primary_action_label": "Voir fiche",
                "primary_action_url": f"/admin/tenants/{tid}",
                "secondary_action_label": "Quality",
                "secondary_action_url": "/admin/quality",
            }
        )

    quota = ops.get("quota") or {}
    for row in quota.get("over_100") or []:
        tid = row.get("tenant_id")
        if tid is None:
            continue
        items.append(
            {
                "id": f"quota100-{tid}",
                "severity": "critical",
                "type": "usage",
                "tenant_id": int(tid),
                "tenant_name": row.get("name") or "",
                "title": "Quota minutes dépassé",
                "description": f'{float(row.get("used_minutes") or 0):.0f} / {row.get("included_minutes")} min ({row.get("usage_pct")}%)',
                "target_label": "Usage",
                "primary_action_label": "Voir billing",
                "primary_action_url": f"/admin/billing?tenant={tid}&sort=usage_desc",
                "secondary_action_label": "Voir fiche",
                "secondary_action_url": f"/admin/tenants/{tid}",
            }
        )

    errs = ops.get("errors") or {}
    for row in (errs.get("top_tenants") or [])[:6]:
        tid = row.get("tenant_id")
        if tid is None or int(row.get("errors_total") or 0) < 5:
            continue
        items.append(
            {
                "id": f"err-{tid}",
                "severity": "warning",
                "type": "vapi",
                "tenant_id": int(tid),
                "tenant_name": row.get("name") or "",
                "title": "Friction / anomalies vocales élevées",
                "description": f"{row.get('errors_total')} événements sur {errs.get('window_days')} j",
                "target_label": "Quality",
                "primary_action_label": "Voir tenant",
                "primary_action_url": f"/admin/tenants/{tid}",
                "secondary_action_label": "Operations",
                "secondary_action_url": "/admin/operations",
            }
        )

    for row in (quota.get("over_80") or [])[:8]:
        tid = row.get("tenant_id")
        if tid is None or float(row.get("usage_pct") or 0) < 85:
            continue
        items.append(
            {
                "id": f"quota85-{tid}",
                "severity": "warning",
                "type": "usage",
                "tenant_id": int(tid),
                "tenant_name": row.get("name") or "",
                "title": "Quota voix très utilisé",
                "description": f'{float(row.get("used_minutes") or 0):.0f} / {row.get("included_minutes")} min ({row.get("usage_pct")}%)',
                "target_label": "Usage",
                "primary_action_label": "Billing",
                "primary_action_url": f"/admin/billing?tenant={tid}&sort=usage_desc",
                "secondary_action_label": "Voir fiche",
                "secondary_action_url": f"/admin/tenants/{tid}",
            }
        )

    uniq: Dict[str, dict] = {}
    order = []
    for it in items:
        oid = str(it.get("id") or "")
        if oid and oid not in uniq:
            uniq[oid] = it
            order.append(oid)
    out_sorted = sorted([uniq[k] for k in order], key=lambda x: 0 if x.get("severity") == "critical" else 1)
    filt = (severity_filter or "").strip().lower()
    if filt in ("critical", "warning"):
        out_sorted = [x for x in out_sorted if (x.get("severity") or "") == filt]
    return out_sorted[:40]


def dash_build_summary(ctx: Any, period: str) -> dict:
    tenants = ctx["_get_tenant_list"](include_inactive=True)
    active_count = sum(1 for t in tenants or [] if (t.get("status") or "active") == "active")
    wd_ops = max(7, min(90, dash_window_days(period)))

    cur_start, cur_end, prev_start, prev_end = dash_paired_intervals_utc(period)
    ivr_cur = dash_ivr_between(ctx, cur_start, cur_end)
    ivr_prev = dash_ivr_between(ctx, prev_start, prev_end)

    ap_cur = dash_slots_appointment_between(ctx, cur_start, cur_end)
    ap_prev = dash_slots_appointment_between(ctx, prev_start, prev_end)

    bookings_cur = max(int(ivr_cur["appointments_created_count"]), ap_cur)
    bookings_prev = max(int(ivr_prev["appointments_created_count"]), ap_prev)

    web_cur = dash_web_requests_between(cur_start, cur_end)
    web_prev = dash_web_requests_between(prev_start, prev_end)

    mins_cur, cost_usd_cur = dash_voice_and_cost_between(ctx, cur_start, cur_end)

    voice_month_used, incl_sum, usage_pct = dash_month_voice_and_included(ctx)

    rate_eur_pm = os.environ.get("VAPI_COST_PER_MINUTE") or os.environ.get("VAPI_COST_PER_MINUTE_EUR") or ""
    cost_eur_est: float
    is_est = True
    if rate_eur_pm.strip():
        try:
            rp = float(str(rate_eur_pm).replace(",", "."))
            cost_eur_est = round(rp * float(mins_cur), 2)
        except Exception:
            cost_eur_est = round(float(cost_usd_cur) * float(os.environ.get("USD_TO_EUR", "0.92")), 2)
    else:
        cost_eur_est = round(float(cost_usd_cur) * float(os.environ.get("USD_TO_EUR", "0.92")), 2)

    billing_snap = ctx["_get_billing_snapshot"]()
    ops_snap = ctx["_get_operations_snapshot"](window_days=wd_ops)
    activation_slice = ctx["_get_activation_queue"](42).get("items") or []
    crit_cnt = dash_critical_count(ctx, billing_snap, ops_snap, activation_slice)

    calls_cur = float(ivr_cur.get("calls_handled_count") or 0)
    calls_prev = float(ivr_prev.get("calls_handled_count") or 0)

    kpis = {
        "active_tenants_count": active_count,
        "active_tenants_delta_month": dash_active_delta_month_pg(),
        "calls_handled_count": int(calls_cur),
        "calls_delta_percent": dash_pct_change(calls_cur, calls_prev),
        "web_requests_count": int(web_cur),
        "web_requests_delta_percent": dash_pct_change(float(web_cur), float(web_prev)),
        "appointments_created_count": int(bookings_cur),
        "appointments_created_delta_percent": dash_pct_change(float(bookings_cur), float(bookings_prev)),
        "voice_minutes_used": int(round(float(mins_cur))),
        # cumul mensuel inclus (parc) pour le même indicateur « % inclus » cockpit
        "included_minutes_total": incl_sum,
        "usage_percent": usage_pct,
        "vapi_cost_current_period": float(cost_eur_est),
        "vapi_cost_currency": "EUR",
        "vapi_cost_is_estimate": bool(is_est),
        "critical_alerts_count": int(crit_cnt),
    }

    return {
        "period": period,
        "tenant_totals_hint": len(tenants or []),
        "kpis": kpis,
        "leads": dash_leads_block(ctx, period),
        "hints": {
            "voice_minutes_calendar_month_total": voice_month_used,
        },
    }
