"""
Envoi du rapport quotidien IVR par email (HTML).
Supporte Postmark (API HTTPS) ou SMTP. Ne jamais logger tokens / mots de passe.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

POSTMARK_API_URL = "https://api.postmarkapp.com/email"

CONTEXT_LABELS_FR = {
    "name": "Nom non compris",
    "slot_choice": "Choix de créneau ambigu",
    "preference": "Préférence horaire floue",
    "phone": "Téléphone non compris",
    "unknown": "Autres",
}

RECOMMENDATIONS = {
    "slot_choice": "Améliorer reconnaissance jour/heure",
    "name": "Rejeter fillers + exemples",
    "phone": "Demander chiffre par chiffre",
    "preference": "Reformulation avant/après midi + heures",
}


def _date_fr(date_str: str) -> str:
    """YYYY-MM-DD → 'lundi 15 janvier 2025'."""
    try:
        from datetime import datetime
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        mois = ["janvier", "février", "mars", "avril", "mai", "juin",
                "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        return f"{jours[dt.weekday()]} {dt.day} {mois[dt.month - 1]} {dt.year}"
    except Exception:
        return date_str


def _build_html(client_name: str, date_str: str, data: Dict[str, Any]) -> str:
    date_fr = _date_fr(date_str)
    ct = data.get("calls_total") or 0
    booked = data.get("booked") or 0
    transfers = data.get("transfers") or 0
    abandons = data.get("abandons") or 0
    pct_booked = (booked / ct * 100) if ct else 0
    pct_transfers = (transfers / ct * 100) if ct else 0
    pct_abandons = (abandons / ct * 100) if ct else 0

    intent_router_count = data.get("intent_router_count") or 0
    recovery_count = data.get("recovery_count") or 0
    anti_loop_count = data.get("anti_loop_count") or 0

    top_contexts = data.get("top_contexts") or []
    top3_html = ""
    for item in top_contexts[:3]:
        ctx = item.get("context", "")
        cnt = item.get("count", 0)
        label = CONTEXT_LABELS_FR.get(ctx, CONTEXT_LABELS_FR.get("unknown", "Autres"))
        top3_html += f"<li>{label}: {cnt}</li>"
    if not top3_html:
        top3_html = "<li>—</li>"

    direct = data.get("direct_booking") or 0
    after_recovery = data.get("booking_after_recovery") or 0
    after_router = data.get("booking_after_intent_router") or 0

    empty_silence = data.get("empty_silence_calls") or 0
    alertes_html = ""
    if anti_loop_count > 0:
        alertes_html += f"<li>Appels ayant déclenché anti-loop: {anti_loop_count}</li>"
    if empty_silence > 0:
        alertes_html += f"<li>Appels avec silence répété (≥2): {empty_silence}</li>"
    if not alertes_html:
        alertes_html = "<li>Aucune alerte.</li>"

    top1_context = top_contexts[0].get("context") if top_contexts else None
    reco = RECOMMENDATIONS.get(top1_context or "", "—")
    events_count = data.get("events_count", 0)
    report_day = date_str[:10] if date_str else ""
    db_name = "agent.db"

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Rapport appels – {client_name}</title></head>
<body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 1rem;">
  <h1 style="font-size: 1.2rem;">📊 Rapport des appels – {client_name} – {date_fr}</h1>
  <p style="color: #555; font-size: 0.9rem;">Ce rapport recense les appels de la journée pour vous aider à améliorer le système (feedback : menés à bien, raccrochés, transferts).</p>

  <h2 style="font-size: 1rem;">A) Résumé des appels</h2>
  <ul>
    <li>Appels reçus: <strong>{ct}</strong></li>
    <li>Menés à bien (RDV confirmé): <strong>{booked}</strong> ({pct_booked:.0f}%)</li>
    <li>Transferts vers un humain: <strong>{transfers}</strong> ({pct_transfers:.0f}%)</li>
    <li>Raccrochés / abandons: <strong>{abandons}</strong> ({pct_abandons:.0f}%)</li>
  </ul>

  <h2 style="font-size: 1rem;">B) Santé de l'agent</h2>
  <ul>
    <li>INTENT_ROUTER déclenché: <strong>{intent_router_count}</strong></li>
    <li>Recovery total: <strong>{recovery_count}</strong></li>
    <li>Anti-loop: <strong>{anti_loop_count}</strong></li>
  </ul>

  <h2 style="font-size: 1rem;">C) Principales incompréhensions (TOP 3)</h2>
  <ul>{top3_html}</ul>

  <h2 style="font-size: 1rem;">D) Qualité des bookings</h2>
  <ul>
    <li>Booking direct (sans friction): <strong>{direct}</strong></li>
    <li>Booking après recovery: <strong>{after_recovery}</strong></li>
    <li>Booking après intent_router: <strong>{after_router}</strong></li>
  </ul>

  <h2 style="font-size: 1rem;">E) Alertes</h2>
  <ul>{alertes_html}</ul>

  <h2 style="font-size: 1rem;">F) Recommandation du jour</h2>
  <p><strong>{reco}</strong></p>

  <p style="color: #666; font-size: 0.85rem;">Rapport généré automatiquement. Utilisez ces chiffres pour ajuster prompts, réglages ou formation.</p>
  <p style="color: #999; font-size: 0.75rem; margin-top: 1rem;">report_day={report_day} | calls={ct} | events={events_count} | db={db_name}</p>
</body>
</html>
"""


def _send_via_postmark(from_addr: str, to: str, subject: str, html: str, token: str) -> Tuple[bool, Optional[str]]:
    """Envoi via API Postmark (HTTPS). Returns (success, error_message)."""
    import httpx
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": token,
    }
    payload = {
        "From": from_addr,
        "To": to,
        "Subject": subject,
        "HtmlBody": html,
        "MessageStream": "outbound",
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(POSTMARK_API_URL, json=payload, headers=headers)
        if r.status_code == 200:
            return True, None
        try:
            body = r.json()
            msg = body.get("Message", r.text) or r.text
        except Exception:
            msg = r.text or str(r.status_code)
        logger.warning("postmark_failed status=%s message=%s", r.status_code, msg[:200])
        return False, f"Postmark {r.status_code}: {msg}"
    except Exception as e:
        logger.exception("_send_via_postmark failed")
        return False, str(e)


def send_daily_report_email(to: str, client_name: str, date_str: str, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Envoie l'email du rapport quotidien IVR (HTML).
    Si EMAIL_PROVIDER=postmark (ou POSTMARK_SERVER_TOKEN défini) : envoi via Postmark (EMAIL_FROM).
    Sinon : SMTP (SMTP_HOST, SMTP_PORT, SMTP_EMAIL, SMTP_PASSWORD).
    Returns (success, error_message). error_message is None on success.
    """
    if not to or not to.strip():
        logger.warning("send_daily_report_email: to empty, skip")
        return False, "Destinataire vide"
    subject = f"📊 Rapport des appels – {client_name} – {_date_fr(date_str)}"
    html = _build_html(client_name, date_str, data)

    use_postmark = (os.getenv("EMAIL_PROVIDER") or "").strip().lower() == "postmark" or bool(
        (os.getenv("POSTMARK_SERVER_TOKEN") or "").strip()
    )
    if use_postmark:
        token = (os.getenv("POSTMARK_SERVER_TOKEN") or "").strip()
        from_addr = (os.getenv("EMAIL_FROM") or os.getenv("SMTP_EMAIL") or os.getenv("REPORT_EMAIL") or "").strip()
        if not token:
            logger.warning("Postmark demandé mais POSTMARK_SERVER_TOKEN manquant")
            return False, "POSTMARK_SERVER_TOKEN non défini"
        if not from_addr:
            logger.warning("Postmark: EMAIL_FROM (ou SMTP_EMAIL/REPORT_EMAIL) manquant")
            return False, "EMAIL_FROM non défini"
        logger.info("report_daily: sending via Postmark to %s", to[:50])
        ok, err = _send_via_postmark(from_addr, to, subject, html, token)
        if ok:
            logger.info("email_sent via postmark", extra={"to": to[:50], "client_name": client_name, "date": date_str})
        return ok, err

    from_addr = os.getenv("SMTP_EMAIL")
    password = os.getenv("SMTP_PASSWORD")
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    if not from_addr or not password:
        logger.warning("Email not configured (SMTP_EMAIL/SMTP_PASSWORD)")
        return False, "SMTP non configuré (SMTP_EMAIL / SMTP_PASSWORD sur Railway)"
    try:
        logger.info("report_daily: connecting SMTP %s:%s", host, port)
        msg = MIMEMultipart("alternative")
        msg["From"] = from_addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(from_addr, password)
            server.sendmail(from_addr, [to], msg.as_string())
        logger.info("report_sent", extra={"to": to[:50], "client_name": client_name, "date": date_str})
        return True, None
    except Exception as e:
        err = str(e)
        logger.info("report_failed", extra={"to": to[:50], "error": err})
        logger.exception("send_daily_report_email failed")
        return False, err


def send_test_email(to: str) -> Tuple[bool, Optional[str]]:
    """
    Envoie un email de test "Test UWi" (vérifier Postmark/SMTP sans passer par /login).
    Postmark puis SMTP.
    Returns (success, error_message).
    """
    if not to or not to.strip():
        return False, "Destinataire vide"
    subject = "Test UWi – Email auth"
    html = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Test UWi</title></head>
<body style="font-family: sans-serif; max-width: 560px; margin: 0 auto; padding: 1rem;">
  <h1 style="font-size: 1.2rem;">Test UWi</h1>
  <p>Si vous recevez cet email, l'envoi (Postmark ou SMTP) est opérationnel.</p>
  <p style="color:#888;font-size:0.85rem;">Envoyé depuis l'endpoint admin /api/admin/email/test.</p>
</body>
</html>
"""
    token = (os.getenv("POSTMARK_SERVER_TOKEN") or "").strip()
    from_addr = (
        os.getenv("POSTMARK_FROM_EMAIL") or os.getenv("EMAIL_FROM") or os.getenv("SMTP_EMAIL") or ""
    ).strip()
    if token and from_addr:
        try:
            ok, err = _send_via_postmark(from_addr, to.strip(), subject, html, token)
            if ok:
                logger.info("test_email_sent via postmark", extra={"to": to[:50]})
            return ok, err
        except Exception as e:
            logger.exception("send_test_email postmark failed")
            return False, str(e)
    smtp_user = (os.getenv("SMTP_EMAIL") or "").strip()
    smtp_pass = (os.getenv("SMTP_PASSWORD") or "").strip()
    if smtp_user and smtp_pass:
        host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        port = int(os.getenv("SMTP_PORT", "587"))
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = smtp_user
            msg["To"] = to.strip()
            msg["Subject"] = subject
            msg.attach(MIMEText(html, "html", "utf-8"))
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to.strip()], msg.as_string())
            logger.info("test_email_sent via smtp", extra={"to": to[:50]})
            return True, None
        except Exception as e:
            logger.exception("send_test_email smtp failed")
            return False, str(e)
    return False, "Email non configuré (POSTMARK_SERVER_TOKEN + EMAIL_FROM ou SMTP_EMAIL + SMTP_PASSWORD)"


def send_password_reset_email(to: str, reset_url: str, ttl_minutes: int = 60) -> Tuple[bool, Optional[str]]:
    """
    Envoie l'email « Réinitialiser mon mot de passe » (lien UWi).
    Postmark puis SMTP. Returns (success, error_message).
    """
    if not to or not to.strip():
        return False, "Destinataire vide"
    if not reset_url:
        return False, "URL vide"
    subject = "UWi – Réinitialisation de votre mot de passe"
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Réinitialisation mot de passe UWi</title></head>
<body style="font-family: sans-serif; max-width: 560px; margin: 0 auto; padding: 1rem;">
  <h1 style="font-size: 1.2rem;">Réinitialisation de votre mot de passe</h1>
  <p>Bonjour,</p>
  <p>Vous avez demandé à réinitialiser votre mot de passe. Cliquez sur le bouton ci-dessous :</p>
  <p style="margin: 1.5rem 0;">
    <a href="{reset_url}" style="background:#2563eb;color:white;padding:0.75rem 1.5rem;text-decoration:none;border-radius:0.5rem;display:inline-block;">
      Définir un nouveau mot de passe
    </a>
  </p>
  <p style="color:#666;font-size:0.9rem;">Ou copiez ce lien : <a href="{reset_url}">{reset_url}</a></p>
  <p style="color:#888;font-size:0.85rem;">Ce lien expire dans {ttl_minutes} minutes.</p>
  <p style="color:#888;font-size:0.85rem;">Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.</p>
</body>
</html>
"""
    from_addr = (
        os.getenv("POSTMARK_FROM_EMAIL") or os.getenv("EMAIL_FROM") or os.getenv("SMTP_EMAIL") or ""
    ).strip()
    token = (os.getenv("POSTMARK_SERVER_TOKEN") or "").strip()
    if token and from_addr:
        try:
            ok, err = _send_via_postmark(from_addr, to.strip(), subject, html, token)
            if ok:
                logger.info("password_reset_email_sent via postmark", extra={"to": to[:50]})
            return ok, err
        except Exception as e:
            logger.exception("send_password_reset_email postmark failed")
            return False, str(e)
    smtp_user = (os.getenv("SMTP_EMAIL") or "").strip()
    smtp_pass = (os.getenv("SMTP_PASSWORD") or "").strip()
    if smtp_user and smtp_pass:
        host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        port = int(os.getenv("SMTP_PORT", "587"))
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = smtp_user
            msg["To"] = to.strip()
            msg["Subject"] = subject
            msg.attach(MIMEText(html, "html", "utf-8"))
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to.strip()], msg.as_string())
            logger.info("password_reset_email_sent via smtp", extra={"to": to[:50]})
            return True, None
        except Exception as e:
            logger.exception("send_password_reset_email smtp failed")
            return False, str(e)
    return False, "Email non configuré (Postmark ou SMTP)"


def send_quota_alert_80_email(
    to_email: str,
    tenant_name: str,
    used_minutes: float,
    included_minutes: int,
    month_utc: str,
) -> Tuple[bool, Optional[str]]:
    """
    Alerte quota 80 % : « Vous avez utilisé X % de vos minutes ce mois. »
    Returns (success, error_message).
    """
    if not to_email or not to_email.strip():
        return False, "Destinataire vide"
    usage_pct = round((used_minutes / included_minutes) * 100, 1) if included_minutes else 0
    subject = f"UWi – Alerte quota ({usage_pct:.0f} % utilisés ce mois)"
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Alerte quota</title></head>
<body style="font-family: sans-serif; max-width: 560px; margin: 0 auto; padding: 1rem;">
  <h1 style="font-size: 1.2rem;">Alerte utilisation des minutes</h1>
  <p>Bonjour,</p>
  <p>Pour <strong>{tenant_name}</strong>, vous avez utilisé <strong>{usage_pct:.1f} %</strong> de vos minutes incluses pour le mois {month_utc} ({used_minutes:.0f} / {included_minutes} minutes).</p>
  <p>À 100 %, les appels seront temporairement suspendus jusqu'au mois suivant. Pensez à souscrire à un forfait supérieur ou à gérer votre consommation.</p>
  <p style="color:#666;font-size:0.9rem;">Cet email est envoyé une fois par mois par client lorsque le seuil de 80 % est atteint.</p>
</body>
</html>
"""
    from_addr = (
        os.getenv("POSTMARK_FROM_EMAIL") or os.getenv("EMAIL_FROM") or os.getenv("SMTP_EMAIL") or ""
    ).strip()
    token = (os.getenv("POSTMARK_SERVER_TOKEN") or "").strip()
    if token and from_addr:
        try:
            ok, err = _send_via_postmark(from_addr, to_email, subject, html, token)
            return ok, err
        except Exception as e:
            logger.exception("send_quota_alert_80_email postmark failed")
            return False, str(e)
    smtp_user = (os.getenv("SMTP_EMAIL") or "").strip()
    smtp_pass = (os.getenv("SMTP_PASSWORD") or "").strip()
    if smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = smtp_user
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(html, "html", "utf-8"))
            with smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", "587"))) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to_email], msg.as_string())
            return True, None
        except Exception as e:
            logger.exception("send_quota_alert_80_email smtp failed")
            return False, str(e)
    return False, "Email non configuré (Postmark ou SMTP)"


def send_ordonnance_notification(request: Dict[str, Any]) -> bool:
    """
    Envoie une notification au cabinet pour demande d'ordonnance (patient veut qu'on transmette un message).
    request: {'type': 'ordonnance', 'name': str, 'phone': str, 'timestamp': str}
    """
    to = os.getenv("NOTIFICATION_EMAIL") or os.getenv("REPORT_EMAIL") or os.getenv("OWNER_EMAIL")
    if not to or not to.strip():
        logger.warning("send_ordonnance_notification: no NOTIFICATION_EMAIL/REPORT_EMAIL/OWNER_EMAIL, skip")
        return False
    name = request.get("name", "?")
    phone = request.get("phone", "?")
    ts = request.get("timestamp", "")
    subject = f"Demande ordonnance – {name}"
    body = f"""Nouvelle demande d'ordonnance :

Patient : {name}
Téléphone : {phone}
Date/Heure : {ts}

À rappeler pour ordonnance.
"""
    from_addr = os.getenv("SMTP_EMAIL")
    password = os.getenv("SMTP_PASSWORD")
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    if not from_addr or not password:
        logger.warning("Email not configured (SMTP_EMAIL/SMTP_PASSWORD)")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(from_addr, password)
            server.sendmail(from_addr, [to], msg.as_string())
        logger.info("ordonnance_notification_sent", extra={"patient_name": name[:50], "phone": phone[:20]})
        return True
    except Exception as e:
        logger.exception("send_ordonnance_notification failed: %s", e)
        return False
