"""SMS / email patient + cabinet après annulation ou déplacement depuis la page publique."""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

from backend.booking_code import format_booking_code

logger = logging.getLogger(__name__)


def _first_name(full_name: str) -> str:
    parts = str(full_name or "Patient").strip().split()
    return parts[0] if parts else "Patient"


def _patient_from_record(record: Dict[str, Any]) -> Dict[str, str]:
    source_type = str(record.get("source_type") or "").strip()
    if source_type == "public_booking":
        return {
            "name": str(record.get("patient_name") or "Patient").strip(),
            "phone": str(record.get("patient_phone") or "").strip(),
            "email": str(record.get("patient_email") or "").strip().lower(),
            "slot_label": str(record.get("slot_label") or "").strip(),
            "motif": str(record.get("motif") or "Consultation").strip(),
        }
    contact_type = str(record.get("contact_type") or "").strip().lower()
    contact = str(record.get("contact") or "").strip()
    phone = contact if contact_type == "phone" else ""
    email = contact.lower() if contact_type == "email" else ""
    if not phone and not email and contact:
        phone = contact
    return {
        "name": str(record.get("name") or "Patient").strip(),
        "phone": phone,
        "email": email,
        "slot_label": str(record.get("slot_label") or "").strip(),
        "motif": str(record.get("motif") or "Consultation").strip(),
    }


def _cabinet_email_to(practitioner: Dict[str, Any]) -> str:
    return (
        str(practitioner.get("email") or "").strip()
        or (os.environ.get("PUBLIC_BOOKING_CABINET_EMAIL_TO") or "").strip()
        or (os.environ.get("OWNER_EMAIL") or "").strip()
        or (os.environ.get("ADMIN_NOTIFICATION_EMAIL") or "").strip()
        or (os.environ.get("REPORT_EMAIL") or "").strip()
    )


def _send_html_email(to_email: str, subject: str, html: str) -> bool:
    to_addr = (to_email or "").strip()
    if not to_addr:
        return False

    token = (os.environ.get("POSTMARK_SERVER_TOKEN") or "").strip()
    from_addr = (
        (os.environ.get("POSTMARK_FROM_EMAIL") or "").strip()
        or (os.environ.get("EMAIL_FROM") or "").strip()
        or (os.environ.get("SMTP_EMAIL") or "").strip()
        or to_addr
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
                    "To": to_addr,
                    "Subject": subject,
                    "HtmlBody": html,
                    "MessageStream": "outbound",
                },
                timeout=20.0,
            )
            if response.status_code == 200:
                return True
            logger.warning("public action email postmark failed status=%s", response.status_code)
        except Exception as exc:
            logger.warning("public action email postmark exception: %s", exc)

    smtp_user = (os.environ.get("SMTP_EMAIL") or "").strip()
    smtp_pass = (os.environ.get("SMTP_PASSWORD") or "").strip()
    if smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = smtp_user
            msg["To"] = to_addr
            msg["Subject"] = subject
            msg.attach(MIMEText(html, "html", "utf-8"))
            host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
            port = int(os.environ.get("SMTP_PORT", "587"))
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to_addr], msg.as_string())
            return True
        except Exception as exc:
            logger.warning("public action email smtp exception: %s", exc)
    return False


def _practitioner_for_slug(slug: str) -> Dict[str, Any]:
    from backend.routes.public_pages import _try_fetch_practitioner

    practitioner = _try_fetch_practitioner(slug)
    if practitioner:
        return practitioner
    return {"name": "Cabinet", "email": "", "slug": slug}


def dispatch_public_cancel_notifications(
    *,
    slug: str,
    tenant_id: int,
    record: Dict[str, Any],
    booking_code: str,
    slot_label: Optional[str] = None,
    reason: Optional[str] = None,
) -> Dict[str, bool]:
    from backend.routes.public_pages import _send_sms

    practitioner = _practitioner_for_slug(slug)
    patient = _patient_from_record(record)
    cabinet_name = str(practitioner.get("name") or "votre cabinet").strip()
    code_label = format_booking_code(booking_code)
    when = (slot_label or patient.get("slot_label") or "").strip() or "votre rendez-vous"
    reason_text = (reason or "").strip()

    patient_sms = (
        f"Bonjour {_first_name(patient['name'])}, votre rendez-vous avec {cabinet_name} "
        f"({when}) a bien ete annule."
    )
    if code_label:
        patient_sms += f" Code concerne : {code_label}."
    patient_sms += " UWI"

    patient_email_html = f"""
<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;padding:16px;">
  <h2 style="margin:0 0 12px;">Annulation de rendez-vous</h2>
  <p>Bonjour {_first_name(patient['name'])},</p>
  <p>Votre rendez-vous avec <strong>{cabinet_name}</strong> ({when}) a bien ete annule.</p>
  {f"<p><strong>Code rendez-vous :</strong> {code_label}</p>" if code_label else ""}
  {f"<p><strong>Motif :</strong> {reason_text}</p>" if reason_text else ""}
  <p style="color:#666;font-size:12px;">Message automatique UWI.</p>
</body></html>
""".strip()

    cabinet_sms = (
        f"UWI - RDV annule: {patient['name']}, {when}."
        f"{f' Code: {code_label}.' if code_label else ''}"
        f"{f' Motif: {reason_text[:80]}.' if reason_text else ''}"
        f" Tel: {patient['phone'] or '—'}"
    )

    cabinet_email_html = f"""
<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;padding:16px;">
  <h2 style="margin:0 0 12px;">Annulation de rendez-vous (page publique)</h2>
  <ul>
    <li><strong>Cabinet :</strong> {cabinet_name}</li>
    <li><strong>Patient :</strong> {patient['name']}</li>
    <li><strong>Creneau :</strong> {when}</li>
    {f"<li><strong>Code :</strong> {code_label}</li>" if code_label else ""}
    <li><strong>Telephone :</strong> {patient['phone'] or '—'}</li>
    <li><strong>Email :</strong> {patient['email'] or '—'}</li>
    {f"<li><strong>Motif :</strong> {reason_text}</li>" if reason_text else ""}
  </ul>
</body></html>
""".strip()

    out = {
        "patient_sms": False,
        "patient_email": False,
        "cabinet_sms": False,
        "cabinet_email": False,
    }
    if patient.get("phone"):
        out["patient_sms"] = bool(_send_sms(patient["phone"], patient_sms))
    if patient.get("email"):
        out["patient_email"] = _send_html_email(
            patient["email"],
            f"Annulation de rendez-vous — {cabinet_name}",
            patient_email_html,
        )

    cabinet_number = (
        os.environ.get("PUBLIC_BOOKING_CABINET_SMS_TO") or os.environ.get("OWNER_PHONE_NUMBER") or ""
    ).strip()
    if cabinet_number:
        out["cabinet_sms"] = bool(_send_sms(cabinet_number, cabinet_sms))

    cabinet_email = _cabinet_email_to(practitioner)
    if cabinet_email:
        out["cabinet_email"] = _send_html_email(
            cabinet_email,
            f"UWI - RDV annule ({cabinet_name})",
            cabinet_email_html,
        )

    logger.info(
        "public_cancel_notifications tenant=%s slug=%s out=%s",
        tenant_id,
        slug,
        out,
    )
    return out


def dispatch_public_reschedule_notifications(
    *,
    slug: str,
    tenant_id: int,
    record: Dict[str, Any],
    old_booking_code: str,
    new_booking_code: str,
    slot_label: str,
    confirmation_id: Optional[str] = None,
) -> Dict[str, bool]:
    from backend.routes.public_pages import _send_sms

    practitioner = _practitioner_for_slug(slug)
    patient = _patient_from_record(record)
    cabinet_name = str(practitioner.get("name") or "votre cabinet").strip()
    old_code_label = format_booking_code(old_booking_code)
    new_code_label = format_booking_code(new_booking_code)
    when = (slot_label or "").strip() or "le nouveau creneau choisi"

    patient_sms = (
        f"Bonjour {_first_name(patient['name'])}, votre rendez-vous avec {cabinet_name} "
        f"a ete deplace au creneau {when}."
    )
    if new_code_label:
        patient_sms += f" Nouveau code : {new_code_label}. Conservez-le pour modifier ou annuler."
    patient_sms += " UWI"

    patient_email_html = f"""
<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;padding:16px;">
  <h2 style="margin:0 0 12px;">Rendez-vous deplace</h2>
  <p>Bonjour {_first_name(patient['name'])},</p>
  <p>Votre rendez-vous avec <strong>{cabinet_name}</strong> a ete deplace au creneau <strong>{when}</strong>.</p>
  {f"<p><strong>Nouveau code rendez-vous :</strong> {new_code_label}</p>" if new_code_label else ""}
  {f"<p style='color:#666;'><s>Ancien code : {old_code_label}</s> (plus valide)</p>" if old_code_label and old_code_label != new_code_label else ""}
  <p>Conservez ce code pour modifier ou annuler votre rendez-vous en ligne.</p>
  <p style="color:#666;font-size:12px;">Message automatique UWI.</p>
</body></html>
""".strip()

    cabinet_sms = (
        f"UWI - RDV deplace: {patient['name']}, nouveau creneau {when}."
        f"{f' Nouveau code: {new_code_label}.' if new_code_label else ''}"
        f" Tel: {patient['phone'] or '—'}"
    )

    cabinet_email_html = f"""
<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;padding:16px;">
  <h2 style="margin:0 0 12px;">Deplacement de rendez-vous (page publique)</h2>
  <ul>
    {f"<li><strong>Confirmation ID :</strong> {confirmation_id}</li>" if confirmation_id else ""}
    <li><strong>Cabinet :</strong> {cabinet_name}</li>
    <li><strong>Patient :</strong> {patient['name']}</li>
    <li><strong>Nouveau creneau :</strong> {when}</li>
    {f"<li><strong>Nouveau code :</strong> {new_code_label}</li>" if new_code_label else ""}
    {f"<li><strong>Ancien code :</strong> {old_code_label}</li>" if old_code_label else ""}
    <li><strong>Telephone :</strong> {patient['phone'] or '—'}</li>
    <li><strong>Email :</strong> {patient['email'] or '—'}</li>
  </ul>
</body></html>
""".strip()

    out = {
        "patient_sms": False,
        "patient_email": False,
        "cabinet_sms": False,
        "cabinet_email": False,
    }
    if patient.get("phone"):
        out["patient_sms"] = bool(_send_sms(patient["phone"], patient_sms))
    if patient.get("email"):
        out["patient_email"] = _send_html_email(
            patient["email"],
            f"Rendez-vous deplace — {cabinet_name}",
            patient_email_html,
        )

    cabinet_number = (
        os.environ.get("PUBLIC_BOOKING_CABINET_SMS_TO") or os.environ.get("OWNER_PHONE_NUMBER") or ""
    ).strip()
    if cabinet_number:
        out["cabinet_sms"] = bool(_send_sms(cabinet_number, cabinet_sms))

    cabinet_email = _cabinet_email_to(practitioner)
    if cabinet_email:
        out["cabinet_email"] = _send_html_email(
            cabinet_email,
            f"UWI - RDV deplace ({cabinet_name})",
            cabinet_email_html,
        )

    logger.info(
        "public_reschedule_notifications tenant=%s slug=%s out=%s",
        tenant_id,
        slug,
        out,
    )
    return out
