# backend/billing_pg.py
"""
Tenant billing (Stripe) : lecture/écriture tenant_billing. Agnostique prix.
Sync via webhooks (subscription created/updated/deleted, invoice.*, checkout.session.completed).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _pg_url() -> Optional[str]:
    return os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL") or os.environ.get("PG_EVENTS_URL")


def get_tenant_billing(tenant_id: int) -> Optional[Dict[str, Any]]:
    """Charge une ligne tenant_billing. Retourne None si table absente ou pas de ligne."""
    url = _pg_url()
    if not url:
        return None
    try:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        SELECT tenant_id, stripe_customer_id, stripe_subscription_id, billing_status,
                               plan_key, current_period_start, current_period_end, trial_ends_at, updated_at,
                               is_suspended, suspension_reason, suspended_at, force_active_override, force_active_until,
                               suspension_mode
                        FROM tenant_billing WHERE tenant_id = %s
                        """,
                        (tenant_id,),
                    )
                except Exception:
                    cur.execute(
                        """
                        SELECT tenant_id, stripe_customer_id, stripe_subscription_id, billing_status,
                               plan_key, current_period_start, current_period_end, trial_ends_at, updated_at
                        FROM tenant_billing WHERE tenant_id = %s
                        """,
                        (tenant_id,),
                    )
                row = cur.fetchone()
                if not row:
                    return None
                d = dict(row)
                d.setdefault("is_suspended", False)
                d.setdefault("suspension_reason", None)
                d.setdefault("suspended_at", None)
                d.setdefault("force_active_override", False)
                d.setdefault("force_active_until", None)
                d.setdefault("suspension_mode", "hard")
                for k in ("current_period_start", "current_period_end", "trial_ends_at", "updated_at", "suspended_at", "force_active_until"):
                    if d.get(k) and hasattr(d[k], "isoformat"):
                        d[k] = d[k].isoformat()
                return d
    except Exception as e:
        if "does not exist" not in str(e).lower() and "tenant_billing" not in str(e).lower():
            logger.warning("get_tenant_billing failed: %s", e)
        return None


def set_stripe_customer_id(tenant_id: int, stripe_customer_id: str) -> bool:
    """Enregistre ou met à jour stripe_customer_id pour le tenant."""
    url = _pg_url()
    if not url or not (stripe_customer_id or "").strip():
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tenant_billing (tenant_id, stripe_customer_id, updated_at)
                    VALUES (%s, %s, now())
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        stripe_customer_id = EXCLUDED.stripe_customer_id,
                        updated_at = now()
                    """,
                    (tenant_id, stripe_customer_id.strip()),
                )
                conn.commit()
        return True
    except Exception as e:
        logger.warning("set_stripe_customer_id failed: %s", e)
        return False


def upsert_billing_from_subscription(
    tenant_id: int,
    stripe_subscription_id: str,
    billing_status: str,
    plan_key: Optional[str] = None,
    current_period_start: Optional[datetime] = None,
    current_period_end: Optional[datetime] = None,
    trial_ends_at: Optional[datetime] = None,
    stripe_customer_id: Optional[str] = None,
) -> bool:
    """Met à jour tenant_billing à partir d’une subscription Stripe (webhook)."""
    url = _pg_url()
    if not url:
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cid = (stripe_customer_id or "").strip() or None
                sub_id_val = (stripe_subscription_id or "").strip() or None
                cur.execute(
                    """
                    INSERT INTO tenant_billing (tenant_id, stripe_customer_id, stripe_subscription_id, billing_status, plan_key,
                                               current_period_start, current_period_end, trial_ends_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        stripe_customer_id = COALESCE(EXCLUDED.stripe_customer_id, tenant_billing.stripe_customer_id),
                        stripe_subscription_id = COALESCE(NULLIF(EXCLUDED.stripe_subscription_id, ''), tenant_billing.stripe_subscription_id),
                        billing_status = COALESCE(EXCLUDED.billing_status, tenant_billing.billing_status),
                        plan_key = COALESCE(EXCLUDED.plan_key, tenant_billing.plan_key),
                        current_period_start = COALESCE(EXCLUDED.current_period_start, tenant_billing.current_period_start),
                        current_period_end = COALESCE(EXCLUDED.current_period_end, tenant_billing.current_period_end),
                        trial_ends_at = EXCLUDED.trial_ends_at,
                        updated_at = now()
                    """,
                    (
                        tenant_id,
                        cid,
                        sub_id_val,
                        billing_status,
                        plan_key or None,
                        current_period_start,
                        current_period_end,
                        trial_ends_at,
                    ),
                )
                conn.commit()
        return True
    except Exception as e:
        logger.warning("upsert_billing_from_subscription failed: %s", e)
        return False


def clear_subscription(tenant_id: int, set_status_canceled: bool = True) -> bool:
    """Met à zéro subscription et optionnellement billing_status = canceled (webhook subscription.deleted)."""
    url = _pg_url()
    if not url:
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tenant_billing SET
                        stripe_subscription_id = NULL,
                        billing_status = CASE WHEN %s THEN 'canceled' ELSE billing_status END,
                        updated_at = now()
                    WHERE tenant_id = %s
                    """,
                    (set_status_canceled, tenant_id),
                )
                conn.commit()
        return True
    except Exception as e:
        logger.warning("clear_subscription failed: %s", e)
        return False


def update_billing_status(tenant_id: int, billing_status: str) -> bool:
    """Met à jour uniquement billing_status (ex. invoice.payment_failed -> past_due)."""
    url = _pg_url()
    if not url or not (billing_status or "").strip():
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tenant_billing SET billing_status = %s, updated_at = now()
                    WHERE tenant_id = %s
                    """,
                    (billing_status.strip(), tenant_id),
                )
                conn.commit()
        return True
    except Exception as e:
        logger.warning("update_billing_status failed: %s", e)
        return False


def try_acquire_stripe_event(event_id: str) -> bool:
    """
    Verrou léger pour idempotence + concurrence : INSERT event_id en premier.
    Retourne True si on a "gagné" (premier à insérer), False si conflit (déjà traité ou autre worker).
    Évite la course entre deux workers sur le même event.
    """
    url = _pg_url()
    if not url or not (event_id or "").strip():
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO stripe_webhook_events (event_id) VALUES (%s) ON CONFLICT (event_id) DO NOTHING RETURNING 1",
                    (event_id.strip(),),
                )
                row = cur.fetchone()
                conn.commit()
                return row is not None
    except Exception as e:
        if "does not exist" not in str(e).lower():
            logger.warning("try_acquire_stripe_event: %s", e)
        return False


def tenant_id_by_stripe_customer_id(stripe_customer_id: str) -> Optional[int]:
    """Résout tenant_id à partir de stripe_customer_id (pour webhooks)."""
    url = _pg_url()
    if not url or not (stripe_customer_id or "").strip():
        return None
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id FROM tenant_billing WHERE stripe_customer_id = %s",
                    (stripe_customer_id.strip(),),
                )
                row = cur.fetchone()
                return int(row[0]) if row else None
    except Exception as e:
        logger.warning("tenant_id_by_stripe_customer_id failed: %s", e)
        return None


# --- Suspension past_due (V1) ---

def get_tenant_suspension(tenant_id: int) -> tuple[bool, Optional[str], str]:
    """
    Retourne (is_suspended, suspension_reason, suspension_mode) pour le tenant.
    mode = "hard" | "soft". Si force_active_override et force_active_until > now(), on considère non suspendu.
    """
    url = _pg_url()
    if not url:
        return (False, None, "hard")
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        SELECT is_suspended, suspension_reason, force_active_override, force_active_until, suspension_mode
                        FROM tenant_billing WHERE tenant_id = %s
                        """,
                        (tenant_id,),
                    )
                except Exception:
                    cur.execute(
                        """
                        SELECT is_suspended, suspension_reason, force_active_override, force_active_until
                        FROM tenant_billing WHERE tenant_id = %s
                        """,
                        (tenant_id,),
                    )
                row = cur.fetchone()
                if not row:
                    return (False, None, "hard")
                is_suspended = bool(row[0])
                reason = (row[1] or "").strip() or None
                force_active = bool(row[2]) if len(row) > 2 else False
                force_until = row[3] if len(row) > 3 else None
                mode = (row[4] or "hard").strip().lower() if len(row) > 4 else "hard"
                if mode not in ("soft", "hard"):
                    mode = "hard"
                if force_active and force_until:
                    from datetime import datetime, timezone
                    if force_until.tzinfo is None:
                        force_until = force_until.replace(tzinfo=timezone.utc)
                    if force_until > datetime.now(timezone.utc):
                        return (False, None, "hard")
                return (is_suspended, reason, mode)
    except Exception as e:
        if "does not exist" not in str(e).lower() and "column" not in str(e).lower():
            logger.warning("get_tenant_suspension failed: %s", e)
        return (False, None, "hard")


def set_tenant_suspended(tenant_id: int, reason: str = "past_due", mode: str = "hard") -> bool:
    """Marque le tenant comme suspendu (manuelle ou job). past_due => toujours hard; manual => mode peut etre soft."""
    url = _pg_url()
    if not url:
        return False
    reason = (reason or "past_due").strip()[:200]
    if reason == "past_due":
        mode = "hard"
    mode = "soft" if (mode or "hard").strip().lower() == "soft" else "hard"
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        INSERT INTO tenant_billing (tenant_id, is_suspended, suspension_reason, suspended_at, suspension_mode, updated_at)
                        VALUES (%s, TRUE, %s, now(), %s, now())
                        ON CONFLICT (tenant_id) DO UPDATE SET
                            is_suspended = TRUE, suspension_reason = EXCLUDED.suspension_reason,
                            suspended_at = now(), suspension_mode = EXCLUDED.suspension_mode, updated_at = now()
                        """,
                        (tenant_id, reason, mode),
                    )
                except Exception:
                    cur.execute(
                        """
                        INSERT INTO tenant_billing (tenant_id, is_suspended, suspension_reason, suspended_at, updated_at)
                        VALUES (%s, TRUE, %s, now(), now())
                        ON CONFLICT (tenant_id) DO UPDATE SET
                            is_suspended = TRUE, suspension_reason = EXCLUDED.suspension_reason,
                            suspended_at = now(), updated_at = now()
                        """,
                        (tenant_id, reason),
                    )
                conn.commit()
        from backend.log_events import (
            TENANT_SUSPENDED_MANUAL_HARD,
            TENANT_SUSPENDED_MANUAL_SOFT,
            TENANT_SUSPENDED_PAST_DUE,
        )
        event = TENANT_SUSPENDED_PAST_DUE if reason == "past_due" else (TENANT_SUSPENDED_MANUAL_SOFT if mode == "soft" else TENANT_SUSPENDED_MANUAL_HARD)
        logger.info("TENANT_SUSPENDED tenant_id=%s reason=%s mode=%s", tenant_id, reason, mode, extra={"event": event})
        return True
    except Exception as e:
        logger.warning("set_tenant_suspended failed: %s", e)
        return False


def set_tenant_unsuspended(tenant_id: int) -> bool:
    """Lève la suspension (admin)."""
    url = _pg_url()
    if not url:
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        UPDATE tenant_billing SET is_suspended = FALSE, suspension_reason = NULL, suspended_at = NULL, suspension_mode = NULL, updated_at = now()
                        WHERE tenant_id = %s
                        """,
                        (tenant_id,),
                    )
                except Exception:
                    cur.execute(
                        """
                        UPDATE tenant_billing SET is_suspended = FALSE, suspension_reason = NULL, suspended_at = NULL, updated_at = now()
                        WHERE tenant_id = %s
                        """,
                        (tenant_id,),
                    )
                conn.commit()
        logger.info("TENANT_UNSUSPENDED_ADMIN tenant_id=%s", tenant_id)
        return True
    except Exception as e:
        logger.warning("set_tenant_unsuspended failed: %s", e)
        return False


def set_force_active(tenant_id: int, days: int) -> bool:
    """Override admin : forcer actif pendant X jours (pas de suspension même si past_due)."""
    url = _pg_url()
    if not url:
        return False
    try:
        from datetime import datetime, timezone, timedelta
        until = (datetime.now(timezone.utc) + timedelta(days=max(1, min(days, 90)))).replace(microsecond=0)
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tenant_billing (tenant_id, force_active_override, force_active_until, updated_at)
                    VALUES (%s, TRUE, %s, now())
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        force_active_override = TRUE, force_active_until = EXCLUDED.force_active_until, updated_at = now()
                    """,
                    (tenant_id, until),
                )
                conn.commit()
        logger.info("TENANT_FORCE_ACTIVE_ENABLED tenant_id=%s days=%s until=%s", tenant_id, days, until.isoformat())
        return True
    except Exception as e:
        logger.warning("set_force_active failed: %s", e)
        return False


def run_suspension_past_due_job(days_after_period_end: int = 7) -> int:
    """
    Job quotidien : suspend les tenants past_due/unpaid dont current_period_end + X jours < now(),
    sauf si force_active_override et force_active_until > now().
    Retourne le nombre de tenants suspendus.
    """
    url = _pg_url()
    if not url:
        return 0
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        UPDATE tenant_billing SET is_suspended = TRUE, suspension_reason = 'past_due', suspended_at = now(), suspension_mode = 'hard', updated_at = now()
                        WHERE billing_status IN ('past_due', 'unpaid')
                          AND current_period_end IS NOT NULL
                          AND current_period_end + (%s || ' days')::interval < %s
                          AND (force_active_override = FALSE OR force_active_until IS NULL OR force_active_until < %s)
                          AND (is_suspended = FALSE OR is_suspended IS NULL)
                        RETURNING tenant_id
                        """,
                        (days_after_period_end, now, now),
                    )
                except Exception:
                    cur.execute(
                        """
                        UPDATE tenant_billing SET is_suspended = TRUE, suspension_reason = 'past_due', suspended_at = now(), updated_at = now()
                        WHERE billing_status IN ('past_due', 'unpaid')
                          AND current_period_end IS NOT NULL
                          AND current_period_end + (%s || ' days')::interval < %s
                          AND (force_active_override = FALSE OR force_active_until IS NULL OR force_active_until < %s)
                          AND (is_suspended = FALSE OR is_suspended IS NULL)
                        RETURNING tenant_id
                        """,
                        (days_after_period_end, now, now),
                    )
                rows = cur.fetchall()
                conn.commit()
                from backend.log_events import TENANT_SUSPENDED_PAST_DUE
                for r in rows:
                    logger.info("TENANT_SUSPENDED_PAST_DUE tenant_id=%s (job)", r[0], extra={"event": TENANT_SUSPENDED_PAST_DUE})
                return len(rows)
    except Exception as e:
        if "does not exist" not in str(e).lower() and "column" not in str(e).lower():
            logger.warning("run_suspension_past_due_job failed: %s", e)
        return 0
