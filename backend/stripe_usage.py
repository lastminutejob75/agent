"""
Push usage Vapi → Stripe (metered billing). Idempotence via stripe_usage_push_log.
Cron 01:00 UTC recommandé pour push_daily_usage_to_stripe(yesterday).

Deux chemins possibles (env STRIPE_USE_METER_EVENTS) :
- false (default) : UsageRecord.create (legacy, subscription item metered).
- true : billing.MeterEvent.create (event_name=STRIPE_METER_EVENT_NAME, payload value + stripe_customer_id).
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Tuple

logger = logging.getLogger(__name__)

# --- Env optionnelles pour Stripe Meters (nouvelle UI) ---
def _stripe_meter_event_name() -> str:
    return (os.environ.get("STRIPE_METER_EVENT_NAME") or "uwi.minutes").strip() or "uwi.minutes"


def _stripe_use_meter_events() -> bool:
    v = (os.environ.get("STRIPE_USE_METER_EVENTS") or "false").strip().lower()
    return v in ("true", "1", "yes")


def _pg_url() -> str | None:
    return os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL") or os.environ.get("PG_EVENTS_URL")


def _pg_events_url() -> str | None:
    return os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")


def try_acquire_usage_push(tenant_id: int, date_utc: date, quantity_minutes: int) -> bool:
    """
    Réserve le droit de pousser l'usage pour (tenant_id, date_utc).
    INSERT pending, ou UPDATE en pending uniquement si status = 'failed' (retry).
    Retourne True si acquis (nouvelle ligne ou retry failed), False si déjà sent/pending.
    """
    url = _pg_url()
    if not url:
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                # sent = immuable : on ne met à jour que si status = 'failed' (retry). Jamais de downgrade sent → pending.
                cur.execute(
                    """
                    INSERT INTO stripe_usage_push_log (tenant_id, date_utc, quantity_minutes, status)
                    VALUES (%s, %s, %s, 'pending')
                    ON CONFLICT (tenant_id, date_utc) DO UPDATE SET
                        quantity_minutes = EXCLUDED.quantity_minutes,
                        status = 'pending',
                        error_short = NULL
                    WHERE stripe_usage_push_log.status = 'failed'
                    RETURNING 1
                    """,
                    (tenant_id, date_utc, quantity_minutes),
                )
                row = cur.fetchone()
                conn.commit()
                return row is not None
    except Exception as e:
        if "does not exist" not in str(e).lower() and "stripe_usage_push_log" not in str(e).lower():
            logger.warning("try_acquire_usage_push failed: %s", e)
        return False


def mark_usage_push_sent(tenant_id: int, date_utc: date, stripe_usage_record_id: str | None = None) -> None:
    """Marque le push comme réussi (status=sent). Stocke stripe_usage_record_id si fourni (debug Stripe)."""
    url = _pg_url()
    if not url:
        return
    record_id = (stripe_usage_record_id or "").strip() or None
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                if record_id:
                    cur.execute(
                        """
                        UPDATE stripe_usage_push_log
                        SET status = 'sent', error_short = NULL, stripe_usage_record_id = %s
                        WHERE tenant_id = %s AND date_utc = %s
                        """,
                        (record_id, tenant_id, date_utc),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE stripe_usage_push_log
                        SET status = 'sent', error_short = NULL
                        WHERE tenant_id = %s AND date_utc = %s
                        """,
                        (tenant_id, date_utc),
                    )
                conn.commit()
        logger.debug("STRIPE_USAGE_PUSH_SENT tenant_id=%s date_utc=%s", tenant_id, date_utc)
    except Exception as e:
        logger.warning("mark_usage_push_sent failed: %s", e)


def mark_usage_push_failed(tenant_id: int, date_utc: date, error_short: str) -> None:
    """Marque le push en échec (status=failed, error_short 255 car) pour diagnostic et retry."""
    url = _pg_url()
    if not url:
        return
    err = (error_short or "")[:255]
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE stripe_usage_push_log
                    SET status = 'failed', error_short = %s
                    WHERE tenant_id = %s AND date_utc = %s
                    """,
                    (err, tenant_id, date_utc),
                )
                conn.commit()
        logger.info("STRIPE_USAGE_PUSH_FAILED tenant_id=%s date_utc=%s error_short=%s", tenant_id, date_utc, err[:80])
    except Exception as e:
        logger.warning("mark_usage_push_failed failed: %s", e)


def push_usage_via_meter_events(
    tenant_id: int,
    minutes: int,
    timestamp_utc: date | datetime,
    stripe_customer_id: str | None = None,
) -> bool:
    """
    Envoie un billing meter event Stripe (event_name=STRIPE_METER_EVENT_NAME, payload value + stripe_customer_id).
    Utilisé quand STRIPE_USE_METER_EVENTS=true. Safe : try/except, log clair.
    Retourne True si succès, False sinon (fallback legacy possible).
    """
    if stripe_customer_id is None:
        from backend.billing_pg import get_tenant_billing
        billing = get_tenant_billing(tenant_id)
        stripe_customer_id = (billing or {}).get("stripe_customer_id") or ""
        stripe_customer_id = (stripe_customer_id or "").strip() or None
    if not stripe_customer_id:
        logger.warning("STRIPE_METER_EVENT_PUSH_SKIP_NO_CUSTOMER tenant_id=%s", tenant_id)
        return False
    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        logger.warning("STRIPE_METER_EVENT_PUSH_SKIP_NO_KEY tenant_id=%s", tenant_id)
        return False
    event_name = _stripe_meter_event_name()
    # Unix timestamp (int), UTC. End-of-day en UTC pour une date.
    if isinstance(timestamp_utc, date) and not isinstance(timestamp_utc, datetime):
        end_of_day_utc = datetime(timestamp_utc.year, timestamp_utc.month, timestamp_utc.day, 23, 59, 59, tzinfo=timezone.utc)
        ts_unix = int(end_of_day_utc.timestamp())
    else:
        ts_unix = int(timestamp_utc.timestamp()) if hasattr(timestamp_utc, "timestamp") else int(datetime.now(timezone.utc).timestamp())
    # Idempotence côté Stripe : même identifier sur 24h = dédupliqué
    d = timestamp_utc.date() if isinstance(timestamp_utc, datetime) else timestamp_utc
    identifier = f"uwi_{tenant_id}_{d.isoformat()}"
    try:
        import stripe
        stripe.api_key = stripe_key
        stripe.billing.MeterEvent.create(
            event_name=event_name,
            payload={
                "stripe_customer_id": stripe_customer_id,
                "value": minutes,  # int requis par l'API Stripe (pas string)
            },
            timestamp=ts_unix,
            identifier=identifier,
        )
        logger.info("STRIPE_METER_EVENT_PUSH_OK tenant_id=%s minutes=%s event_name=%s", tenant_id, minutes, event_name)
        return True
    except Exception as e:
        logger.warning(
            "STRIPE_METER_EVENT_PUSH_FAIL_FALLBACK_LEGACY tenant_id=%s minutes=%s event_name=%s err=%s",
            tenant_id, minutes, event_name, str(e)[:200],
        )
        return False


def _aggregate_usage_by_tenant_for_day(date_utc: date) -> List[Tuple[int, int]]:
    """Retourne [(tenant_id, minutes), ...] pour la journée UTC. minutes = ceil(somme_sec/60)."""
    url = _pg_events_url()
    if not url:
        return []
    start = datetime(date_utc.year, date_utc.month, date_utc.day, 0, 0, 0)
    end = start + timedelta(days=1)
    start_str = start.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end.strftime("%Y-%m-%d %H:%M:%S")
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_id, CEIL(COALESCE(SUM(duration_sec), 0)::numeric / 60.0)::int AS minutes
                    FROM vapi_call_usage
                    WHERE ended_at >= %s AND ended_at < %s
                    GROUP BY tenant_id
                    HAVING SUM(duration_sec) > 0
                    """,
                    (start_str, end_str),
                )
                return [(int(r[0]), int(r[1])) for r in cur.fetchall()]
    except Exception as e:
        if "does not exist" not in str(e).lower():
            logger.warning("_aggregate_usage_by_tenant_for_day failed: %s", e)
        return []


def push_daily_usage_to_stripe(date_utc: date) -> dict:
    """
    Pousse l'usage du jour (date_utc) vers Stripe pour chaque tenant ayant une subscription metered.
    Idempotent : si déjà poussé pour (tenant_id, date_utc), skip.
    Si l'appel Stripe échoue, release la ligne pour permettre retry.
    Retourne {"pushed": n, "skipped": m, "errors": [...]}.
    """
    from backend.billing_pg import get_tenant_billing

    rows = _aggregate_usage_by_tenant_for_day(date_utc)
    pushed = 0
    skipped = 0
    errors = []
    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        logger.warning("STRIPE_USAGE_SKIP STRIPE_SECRET_KEY not set")
        return {"pushed": 0, "skipped": len(rows), "errors": ["STRIPE_SECRET_KEY not set"]}

    for tenant_id, minutes in rows:
        if minutes <= 0:
            continue
        billing = get_tenant_billing(tenant_id)
        if not billing or not (billing.get("stripe_subscription_id") or "").strip():
            logger.debug("STRIPE_USAGE_SKIP_NO_SUB tenant_id=%s", tenant_id)
            skipped += 1
            continue
        metered_item_id = (billing.get("stripe_metered_item_id") or "").strip()
        if not metered_item_id:
            logger.info("STRIPE_USAGE_SKIP_NO_METERED_ITEM tenant_id=%s", tenant_id)
            skipped += 1
            continue

        acquired = try_acquire_usage_push(tenant_id, date_utc, minutes)
        if not acquired:
            skipped += 1
            continue

        use_meter_events = _stripe_use_meter_events()
        customer_id = (billing.get("stripe_customer_id") or "").strip() or None

        if use_meter_events:
            ok = push_usage_via_meter_events(tenant_id, minutes, date_utc, stripe_customer_id=customer_id)
            if ok:
                mark_usage_push_sent(tenant_id, date_utc, stripe_usage_record_id=None)
                pushed += 1
                logger.info("STRIPE_USAGE_PUSHED tenant_id=%s date_utc=%s minutes=%s (meter_events)", tenant_id, date_utc, minutes)
                # Pas de fallback : on ne pousse jamais meter_event + UsageRecord pour le même (tenant_id, date_utc)
                continue
            # Fallback legacy UsageRecord uniquement si meter_event a échoué
            try:
                import stripe
                stripe.api_key = stripe_key
                end_of_day_ts = int(datetime(date_utc.year, date_utc.month, date_utc.day, 23, 59, 59, tzinfo=timezone.utc).timestamp())
                record = stripe.UsageRecord.create(
                    subscription_item=metered_item_id,
                    quantity=minutes,
                    timestamp=end_of_day_ts,
                    action="set",
                )
                usage_record_id = getattr(record, "id", None) if record else None
                mark_usage_push_sent(tenant_id, date_utc, stripe_usage_record_id=usage_record_id)
                pushed += 1
                logger.info("STRIPE_USAGE_PUSHED tenant_id=%s date_utc=%s minutes=%s (fallback UsageRecord)", tenant_id, date_utc, minutes)
            except Exception as e:
                mark_usage_push_failed(tenant_id, date_utc, str(e)[:255])
                err_msg = str(e)[:200]
                errors.append(f"tenant_id={tenant_id}: {err_msg}")
                logger.warning("STRIPE_USAGE_PUSH_FAILED tenant_id=%s date_utc=%s: %s", tenant_id, date_utc, err_msg)
        else:
            try:
                import stripe
                stripe.api_key = stripe_key
                end_of_day_ts = int(datetime(date_utc.year, date_utc.month, date_utc.day, 23, 59, 59, tzinfo=timezone.utc).timestamp())
                record = stripe.UsageRecord.create(
                    subscription_item=metered_item_id,
                    quantity=minutes,
                    timestamp=end_of_day_ts,
                    action="set",
                )
                usage_record_id = getattr(record, "id", None) if record else None
                mark_usage_push_sent(tenant_id, date_utc, stripe_usage_record_id=usage_record_id)
                pushed += 1
                logger.info("STRIPE_USAGE_PUSHED tenant_id=%s date_utc=%s minutes=%s", tenant_id, date_utc, minutes)
            except Exception as e:
                mark_usage_push_failed(tenant_id, date_utc, str(e)[:255])
                err_msg = str(e)[:200]
                errors.append(f"tenant_id={tenant_id}: {err_msg}")
                logger.warning("STRIPE_USAGE_PUSH_FAILED tenant_id=%s date_utc=%s: %s", tenant_id, date_utc, err_msg)

    return {"pushed": pushed, "skipped": skipped, "errors": errors}


def run_upgrade_suggestions() -> dict:
    """
    Parcourt les tenants avec abo actif, calcule minutes en période, appelle maybe_upgrade_plan.
    V1 : log uniquement (pas d'appel Stripe). Une seule ligne de log par tenant suggéré (idempotent).
    Retourne {"checked": n, "suggestions": [(tenant_id, suggested_plan, current_cost, suggested_cost), ...]}.
    """
    from backend.billing_pg import get_tenant_billing, get_tenant_ids_with_active_subscription, get_tenant_minutes_in_current_period
    from backend.billing_upgrade import maybe_upgrade_plan

    tenant_ids = get_tenant_ids_with_active_subscription()
    suggestions = []
    for tenant_id in tenant_ids:
        minutes_used, _start, _end = get_tenant_minutes_in_current_period(tenant_id)
        suggested, current_cost, suggested_cost = maybe_upgrade_plan(tenant_id, minutes_used, current_plan_key=None)
        if suggested:
            current_plan = (get_tenant_billing(tenant_id) or {}).get("plan_key") or "unknown"
            delta_eur = round((current_cost or 0) - (suggested_cost or 0), 2) if (current_cost is not None and suggested_cost is not None) else None
            suggestions.append((tenant_id, suggested, current_cost, suggested_cost))
            logger.info(
                "UPGRADE_SUGGESTED tenant_id=%s current_plan=%s suggested_plan=%s minutes_used=%s current_cost_eur=%s suggested_cost_eur=%s delta_eur=%s",
                tenant_id, current_plan, suggested, minutes_used, current_cost, suggested_cost, delta_eur,
            )
    return {"checked": len(tenant_ids), "suggestions": suggestions}


def push_daily_usage_with_retry_48h(reference_date: date | None = None) -> dict:
    """
    Cron quotidien : pousse yesterday_utc puis day_before_yesterday_utc si pas déjà sent.
    Puis exécute run_upgrade_suggestions (log des upgrades suggérés, pas d'action Stripe en V1).
    Stripe down 1 jour = pas de trou de CA (retry J+2).
    reference_date = date du jour UTC (default: date.today() UTC).
    """
    today = reference_date
    if today is None:
        try:
            today = datetime.now(timezone.utc).date()
        except Exception:
            today = date.today()
    yesterday = today - timedelta(days=1)
    day_before = today - timedelta(days=2)
    r1 = push_daily_usage_to_stripe(yesterday)
    r2 = push_daily_usage_to_stripe(day_before)
    sent = r1.get("pushed", 0) + r2.get("pushed", 0)
    skipped = r1.get("skipped", 0) + r2.get("skipped", 0)
    failed = len(r1.get("errors", [])) + len(r2.get("errors", []))
    upgrade_result = run_upgrade_suggestions()
    return {
        "dates": [yesterday.isoformat(), day_before.isoformat()],
        "sent": sent,
        "skipped": skipped,
        "failed": failed,
        "upgrade_checked": upgrade_result.get("checked", 0),
        "upgrade_suggestions": upgrade_result.get("suggestions", []),
    }
