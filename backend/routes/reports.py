"""
Endpoint rapport quotidien IVR (email).
Protégé par X-Report-Secret. Répond en 202 et traite le rapport en arrière-plan (évite HTTP 000).
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.db import get_daily_report_data
from backend.client_memory import get_client_memory
from backend.services.email_service import send_daily_report_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["reports"])


def _check_report_secret(x_report_secret: Optional[str] = Header(None, alias="X-Report-Secret")) -> None:
    secret = os.getenv("REPORT_SECRET")
    if not secret:
        logger.warning("REPORT_SECRET not set")
        raise HTTPException(status_code=503, detail="Reports not configured")
    if x_report_secret != secret:
        raise HTTPException(status_code=403, detail="Invalid secret")


def _run_daily_report(tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Logique rapport (exécutée dans un thread pour timeout). tenant_id optionnel pour multi-tenant."""
    today = date.today().isoformat()
    admin_email = os.getenv("REPORT_EMAIL") or os.getenv("OWNER_EMAIL")
    if not admin_email:
        return {
            "status": "ok",
            "clients_notified": 0,
            "email_skipped": "REPORT_EMAIL ou OWNER_EMAIL non défini sur Railway",
        }

    try:
        memory = get_client_memory()
        clients = memory.get_clients_with_email(tenant_id=tenant_id)
    except Exception as e:
        logger.exception("report_daily: get_client_memory failed")
        return {"status": "error", "clients_notified": 0, "error": str(e)}

    notified = 0
    email_skipped = None
    email_error = None
    if not clients:
        try:
            data = get_daily_report_data(1, today)
            ok, err = send_daily_report_email(admin_email, "Cabinet", today, data)
            if ok:
                notified = 1
                logger.info("report_sent admin only (no clients)", extra={"date": today})
            else:
                email_error = err
                email_ok = (
                    (os.getenv("EMAIL_PROVIDER") or "").strip().lower() == "postmark"
                    and (os.getenv("POSTMARK_SERVER_TOKEN") or "").strip()
                    and (os.getenv("EMAIL_FROM") or "").strip()
                ) or (os.getenv("SMTP_EMAIL") and os.getenv("SMTP_PASSWORD"))
                if not email_ok:
                    email_skipped = "Email non configuré (Postmark: EMAIL_PROVIDER, POSTMARK_SERVER_TOKEN, EMAIL_FROM — ou SMTP)"
        except Exception as e:
            logger.exception("report_daily: get_daily_report_data or send_daily_report_email failed")
            return {"status": "error", "clients_notified": 0, "error": str(e)}
        out = {"status": "ok", "clients_notified": notified}
        if email_skipped:
            out["email_skipped"] = email_skipped
        if email_error:
            out["email_error"] = email_error
        return out

    for client_id, client_name, _ in clients:
        try:
            data = get_daily_report_data(client_id, today)
            ok, err = send_daily_report_email(admin_email, client_name or f"Client {client_id}", today, data)
            if ok:
                notified += 1
            else:
                email_ok = (
                    (os.getenv("EMAIL_PROVIDER") or "").strip().lower() == "postmark"
                    and (os.getenv("POSTMARK_SERVER_TOKEN") or "").strip()
                    and (os.getenv("EMAIL_FROM") or "").strip()
                ) or (os.getenv("SMTP_EMAIL") and os.getenv("SMTP_PASSWORD"))
                if not email_ok:
                    email_skipped = email_skipped or err
                email_error = email_error or err
        except Exception as e:
            logger.warning("report_failed client_id=%s: %s", client_id, e)
            email_error = email_error or str(e)
    out = {"status": "ok", "clients_notified": notified}
    if email_skipped:
        out["email_skipped"] = email_skipped
    if email_error:
        out["email_error"] = email_error
    return out


def _run_report_background(tenant_id: Optional[int] = None) -> None:
    """Exécute le rapport en arrière-plan et log le résultat."""
    try:
        out = _run_daily_report(tenant_id=tenant_id)
        logger.info("report_daily background result: %s", out)
    except Exception as e:
        logger.exception("report_daily background failed: %s", e)


@router.post("/reports/daily")
def post_daily_report(
    x_report_secret: Optional[str] = Header(None, alias="X-Report-Secret"),
    tenant_id: Optional[int] = Query(None, description="Multi-tenant: ID du tenant pour le rapport"),
):
    """
    Déclenche le rapport quotidien. Répond immédiatement en 202, génération et envoi en arrière-plan.
    Évite HTTP 000 quand le proxy Railway ou SMTP est lent.
    """
    try:
        _check_report_secret(x_report_secret)
    except HTTPException:
        raise

    logger.info("report_daily accepted, running in background", extra={"tenant_id": tenant_id})
    thread = threading.Thread(target=_run_report_background, args=(tenant_id,), daemon=True)
    thread.start()
    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "message": "Rapport en cours de génération et envoi. Consulter les logs Railway pour le résultat.",
        },
    )
