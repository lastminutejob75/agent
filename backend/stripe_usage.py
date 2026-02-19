"""
Push usage Vapi → Stripe (metered billing). Idempotence via stripe_usage_push_log.
Cron 01:00 UTC recommandé pour push_daily_usage_to_stripe(yesterday).
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Tuple

logger = logging.getLogger(__name__)


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
    """Marque le push comme réussi (status=sent). Optionnel : stocker stripe_usage_record_id si dispo."""
    url = _pg_url()
    if not url:
        return
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
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

        try:
            import stripe
            stripe.api_key = stripe_key
            end_of_day_ts = int(datetime(date_utc.year, date_utc.month, date_utc.day, 23, 59, 59).timestamp())
            stripe.UsageRecord.create(
                subscription_item=metered_item_id,
                quantity=minutes,
                timestamp=end_of_day_ts,
                action="set",
            )
            mark_usage_push_sent(tenant_id, date_utc)
            pushed += 1
            logger.info("STRIPE_USAGE_PUSHED tenant_id=%s date_utc=%s minutes=%s", tenant_id, date_utc, minutes)
        except Exception as e:
            mark_usage_push_failed(tenant_id, date_utc, str(e)[:255])
            err_msg = str(e)[:200]
            errors.append(f"tenant_id={tenant_id}: {err_msg}")
            logger.warning("STRIPE_USAGE_PUSH_FAILED tenant_id=%s date_utc=%s: %s", tenant_id, date_utc, err_msg)

    return {"pushed": pushed, "skipped": skipped, "errors": errors}


def push_daily_usage_with_retry_48h(reference_date: date | None = None) -> dict:
    """
    Cron quotidien : pousse yesterday_utc puis day_before_yesterday_utc si pas déjà sent.
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
    out = {"yesterday": push_daily_usage_to_stripe(yesterday), "day_before": push_daily_usage_to_stripe(day_before)}
    return out
