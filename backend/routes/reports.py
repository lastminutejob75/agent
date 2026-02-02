"""
Endpoint rapport quotidien IVR (email).
Protégé par X-Report-Secret.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

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


@router.post("/reports/daily")
def post_daily_report(
    x_report_secret: Optional[str] = Header(None, alias="X-Report-Secret"),
):
    """
    Génère et envoie le rapport quotidien IVR (un rapport par client, stats isolées par client_id).
    Phase 1 : tous les rapports sont envoyés à l'admin uniquement (OWNER_EMAIL / REPORT_EMAIL).
    Les clients finaux ne reçoivent rien — rapport = outil interne.
    Retourne: {"status": "ok", "clients_notified": N}
    """
    _check_report_secret(x_report_secret)
    today = date.today().isoformat()
    admin_email = os.getenv("REPORT_EMAIL") or os.getenv("OWNER_EMAIL")
    if not admin_email:
        logger.warning("REPORT_EMAIL and OWNER_EMAIL not set, cannot send report")
        return {"status": "ok", "clients_notified": 0}

    memory = get_client_memory()
    clients = memory.get_clients_with_email()
    notified = 0
    if not clients:
        data = get_daily_report_data(1, today)
        if send_daily_report_email(admin_email, "Cabinet", today, data):
            notified = 1
            logger.info("report_sent admin only (no clients)", extra={"date": today})
        return {"status": "ok", "clients_notified": notified}

    for client_id, client_name, _ in clients:
        try:
            data = get_daily_report_data(client_id, today)
            if send_daily_report_email(admin_email, client_name or f"Client {client_id}", today, data):
                notified += 1
        except Exception as e:
            logger.info("report_failed", extra={"client_id": client_id, "error": str(e)})
    return {"status": "ok", "clients_notified": notified}
