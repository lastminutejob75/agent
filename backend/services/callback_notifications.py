"""Notifications cabinet pour demandes de rappel (page publique + vocal)."""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

from backend.public_bookings_pg import CALLBACK_REASON_LABELS
from backend.tenant_config import get_params

logger = logging.getLogger(__name__)


def _resolve_tenant_notification_email(tenant_id: int) -> str:
    params = get_params(int(tenant_id or 1)) or {}
    for key in ("contact_email", "notification_email", "email", "owner_email"):
        value = str(params.get(key) or "").strip()
        if value and "@" in value:
            return value
    for env_key in (
        "PUBLIC_BOOKING_CABINET_EMAIL_TO",
        "ADMIN_NOTIFICATION_EMAIL",
        "NOTIFICATION_EMAIL",
        "REPORT_EMAIL",
        "OWNER_EMAIL",
    ):
        value = (os.environ.get(env_key) or "").strip()
        if value and "@" in value:
            return value
    return ""


def _tenant_display_name(tenant_id: int) -> str:
    params = get_params(int(tenant_id or 1)) or {}
    for key in ("business_name", "practitioner_name", "cabinet_name", "name"):
        value = str(params.get(key) or "").strip()
        if value:
            return value
    return f"Cabinet #{tenant_id}"


def _source_label(source: str) -> str:
    clean = (source or "").strip().lower()
    if clean == "vocal_agent":
        return "Appel vocal (Clara)"
    if clean == "public_page":
        return "Page publique"
    return clean or "Inconnue"


def _is_urgent_request(reason: str, message: Optional[str]) -> bool:
    blob = f"{reason or ''} {message or ''}".lower()
    return "urgen" in blob


def _resolve_tenant_notification_phone(tenant_id: int) -> str:
    """Numéro SMS du praticien pour être alerté des nouvelles demandes."""
    params = get_params(int(tenant_id or 1)) or {}
    for key in (
        "notification_phone",
        "transfer_practitioner_phone",
        "responsible_phone",
        "practitioner_phone",
    ):
        value = str(params.get(key) or "").strip()
        if value:
            try:
                from backend.db import normalize_phone_number

                normalized = normalize_phone_number(value)
            except Exception:
                normalized = value
            if normalized:
                return normalized
    return ""


def _sms_alerts_enabled(tenant_id: int) -> bool:
    """Opt-out possible : notify_requests_sms = "false" désactive les SMS d'alerte."""
    params = get_params(int(tenant_id or 1)) or {}
    value = params.get("notify_requests_sms")
    if value is None:
        return True
    return str(value).strip().lower() not in ("0", "false", "no", "off", "non")


def _send_callback_sms(
    *,
    tenant_id: int,
    name: str,
    phone: str,
    reason: str,
    message: Optional[str],
) -> bool:
    if not _sms_alerts_enabled(tenant_id):
        return False
    to_number = _resolve_tenant_notification_phone(tenant_id)
    if not to_number:
        return False
    try:
        from backend.services.sms_service import send_sms_message, sms_is_configured

        if not sms_is_configured():
            return False
        reason_label = CALLBACK_REASON_LABELS.get(str(reason or "").lower(), str(reason or "Autre demande"))
        patient_name = (name or "Patient").strip() or "Patient"
        patient_phone = (phone or "").strip() or "—"
        urgent = _is_urgent_request(reason, message)
        prefix = "⚠️ URGENCE — " if urgent else ""
        detail = (message or "").strip()
        body = (
            f"{prefix}UWi — Nouvelle demande à traiter\n"
            f"{patient_name} ({patient_phone})\n"
            f"Motif : {reason_label}"
        )
        if detail:
            body += f"\n{detail[:200]}"
        body += "\n→ Section Demandes du dashboard."
        ok, _err = send_sms_message(to_number, body)
        return bool(ok)
    except Exception as exc:
        logger.warning("callback_notification_sms_exception tenant=%s: %s", tenant_id, exc)
        return False


def notify_cabinet_callback_request(
    *,
    tenant_id: int,
    request_id: str,
    name: str,
    phone: str,
    reason: str,
    message: Optional[str] = None,
    source: str = "public_page",
    email: Optional[str] = None,
    call_id: Optional[str] = None,
) -> bool:
    # SMS immédiat au praticien (best-effort), indépendant de l'e-mail.
    sms_ok = _send_callback_sms(
        tenant_id=tenant_id,
        name=name,
        phone=phone,
        reason=reason,
        message=message,
    )

    to_email = _resolve_tenant_notification_email(tenant_id)
    if not to_email:
        if not sms_ok:
            logger.warning("callback_notification_skipped tenant=%s reason=no_recipient", tenant_id)
        return sms_ok

    cabinet_name = _tenant_display_name(tenant_id)
    reason_label = CALLBACK_REASON_LABELS.get(str(reason or "").lower(), str(reason or "Autre demande"))
    source_label = _source_label(source)
    patient_name = (name or "Patient").strip() or "Patient"
    patient_phone = (phone or "").strip() or "—"
    patient_email = (email or "").strip() or "—"
    detail = (message or "").strip() or "—"
    subject = f"UWi — Demande de rappel ({patient_name})"

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Demande de rappel</title></head>
<body style="font-family: Arial, sans-serif; max-width: 620px; margin: 0 auto; padding: 16px;">
  <h2 style="margin:0 0 12px;">Nouvelle demande de rappel</h2>
  <p>Une demande de rappel vient d'être enregistrée pour <strong>{cabinet_name}</strong>.</p>
  <ul>
    <li><strong>ID demande :</strong> {request_id}</li>
    <li><strong>Source :</strong> {source_label}</li>
    <li><strong>Patient :</strong> {patient_name}</li>
    <li><strong>Téléphone :</strong> {patient_phone}</li>
    <li><strong>Email :</strong> {patient_email}</li>
    <li><strong>Motif :</strong> {reason_label}</li>
    <li><strong>Précision :</strong> {detail}</li>
    {f"<li><strong>Appel :</strong> {call_id}</li>" if call_id else ""}
  </ul>
  <p style="color:#666;font-size:12px;">Consultez la section Demandes de votre dashboard UWi.</p>
</body>
</html>
""".strip()

    token = (os.environ.get("POSTMARK_SERVER_TOKEN") or "").strip()
    from_addr = (
        (os.environ.get("POSTMARK_FROM_EMAIL") or "").strip()
        or (os.environ.get("EMAIL_FROM") or "").strip()
        or (os.environ.get("SMTP_EMAIL") or "").strip()
        or to_email
    )

    if token:
        try:
            import httpx

            response = httpx.post(
                "https://api.postmarkapp.com/email",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Postmark-Server-Token": token,
                },
                json={
                    "From": from_addr,
                    "To": to_email,
                    "Subject": subject,
                    "HtmlBody": html,
                    "MessageStream": "outbound",
                },
                timeout=20.0,
            )
            if response.status_code == 200:
                logger.info(
                    "callback_notification_sent tenant=%s request_id=%s source=%s",
                    tenant_id,
                    request_id[:8],
                    source,
                )
                return True
            logger.warning("callback_notification_postmark_failed status=%s", response.status_code)
        except Exception as exc:
            logger.warning("callback_notification_postmark_exception: %s", exc)

    smtp_user = (os.environ.get("SMTP_EMAIL") or "").strip()
    smtp_pass = (os.environ.get("SMTP_PASSWORD") or "").strip()
    if smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = smtp_user
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(html, "html", "utf-8"))
            host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
            port = int(os.environ.get("SMTP_PORT", "587"))
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to_email], msg.as_string())
            logger.info(
                "callback_notification_sent tenant=%s request_id=%s source=%s via=smtp",
                tenant_id,
                request_id[:8],
                source,
            )
            return True
        except Exception as exc:
            logger.warning("callback_notification_smtp_exception: %s", exc)
    return sms_ok
