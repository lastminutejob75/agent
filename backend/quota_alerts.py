"""
Alertes quota 80 % : email + event log, anti-spam 1 email/tenant/mois.
Job quotidien : run_quota_alerts_80() (cron daily).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import List, Tuple

logger = logging.getLogger(__name__)


def _pg_url() -> str | None:
    return os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL") or os.environ.get("PG_EVENTS_URL")


def _active_tenant_ids() -> List[int]:
    """Liste des tenant_id actifs (status=active)."""
    url = _pg_url()
    if not url:
        return []
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id FROM tenants WHERE COALESCE(status, 'active') = 'active' ORDER BY tenant_id"
                )
                return [int(r[0]) for r in cur.fetchall()]
    except Exception as e:
        if "does not exist" not in str(e).lower():
            logger.warning("_active_tenant_ids failed: %s", e)
        return []


def _quota_alert_80_already_sent(tenant_id: int, month_utc: str) -> bool:
    """True si une alerte 80 % a déjà été envoyée pour ce tenant ce mois."""
    url = _pg_url()
    if not url or not month_utc or len(month_utc) != 7:
        return True
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM quota_alert_log WHERE tenant_id = %s AND month_utc = %s AND alert_type = %s",
                    (tenant_id, month_utc, "80pct"),
                )
                return cur.fetchone() is not None
    except Exception as e:
        if "does not exist" not in str(e).lower():
            logger.warning("_quota_alert_80_already_sent failed: %s", e)
        return True


def _quota_alert_80_mark_sent(tenant_id: int, month_utc: str) -> None:
    """Enregistre l'envoi d'une alerte 80 % (anti-spam)."""
    url = _pg_url()
    if not url or not month_utc:
        return
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO quota_alert_log (tenant_id, month_utc, alert_type)
                    VALUES (%s, %s, '80pct')
                    ON CONFLICT (tenant_id, month_utc, alert_type) DO NOTHING
                    """,
                    (tenant_id, month_utc, "80pct"),
                )
                conn.commit()
    except Exception as e:
        logger.warning("_quota_alert_80_mark_sent failed: %s", e)


def _tenant_email_and_name(tenant_id: int) -> Tuple[str, str]:
    """(email, name) pour envoi alerte. email = contact_email ou billing_email."""
    from backend.billing_pg import _get_tenant_params_for_quota, get_tenant_billing

    params = _get_tenant_params_for_quota(tenant_id)
    billing = get_tenant_billing(tenant_id)
    email = (params.get("contact_email") or "").strip() or (params.get("billing_email") or "").strip()
    if not email and billing:
        email = (billing.get("billing_email") or "").strip() or ""
    name = (params.get("business_name") or "").strip()
    if not name:
        try:
            from backend.auth_pg import pg_get_tenant_name
            name = (pg_get_tenant_name(tenant_id) or "").strip() or f"Client #{tenant_id}"
        except Exception:
            name = f"Client #{tenant_id}"
    return (email.strip().lower() or "", name or f"Client #{tenant_id}")


def run_quota_alerts_80(month_utc: str | None = None) -> dict:
    """
    Envoie les alertes 80 % pour le mois UTC : tenants avec 80 <= usage_pct < 100.
    Anti-spam : 1 email par tenant par mois (quota_alert_log).
    Retourne {"sent": n, "skipped": m, "errors": [...]}.
    """
    from backend.billing_pg import get_quota_snapshot_month
    from backend.services.email_service import send_quota_alert_80_email

    now = datetime.utcnow()
    month_utc = month_utc or now.strftime("%Y-%m")
    sent = 0
    skipped = 0
    errors = []

    for tenant_id in _active_tenant_ids():
        included, used = get_quota_snapshot_month(tenant_id, month_utc)
        if included <= 0:
            continue
        usage_pct = (used / included) * 100
        if usage_pct < 80 or usage_pct >= 100:
            continue
        if _quota_alert_80_already_sent(tenant_id, month_utc):
            skipped += 1
            continue

        email, name = _tenant_email_and_name(tenant_id)
        if not email:
            logger.info("quota_alert_80_skip_no_email tenant_id=%s", tenant_id)
            skipped += 1
            continue

        ok, err = send_quota_alert_80_email(
            to_email=email,
            tenant_name=name,
            used_minutes=used,
            included_minutes=included,
            month_utc=month_utc,
        )
        if ok:
            _quota_alert_80_mark_sent(tenant_id, month_utc)
            try:
                from backend.auth_events_pg import log_auth_event
                log_auth_event(tenant_id, "", "quota_alert_80_sent", month_utc)
            except Exception:
                pass
            sent += 1
            logger.info("quota_alert_80_sent tenant_id=%s month=%s to=%s", tenant_id, month_utc, email[:50])
        else:
            errors.append(f"tenant_id={tenant_id}: {err or 'unknown'}")

    return {"sent": sent, "skipped": skipped, "errors": errors}
