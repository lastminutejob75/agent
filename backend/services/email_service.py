"""
Envoi du rapport quotidien IVR par email (HTML).
Ne jamais logger le contenu complet de GOOGLE_SERVICE_ACCOUNT_BASE64.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict

logger = logging.getLogger(__name__)

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


def send_daily_report_email(to: str, client_name: str, date_str: str, data: Dict[str, Any]) -> bool:
    """
    Envoie l'email du rapport quotidien IVR (HTML).
    Utilise SMTP (SMTP_HOST, SMTP_PORT, SMTP_EMAIL, SMTP_PASSWORD).
    """
    if not to or not to.strip():
        logger.warning("send_daily_report_email: to empty, skip")
        return False
    subject = f"📊 Rapport des appels – {client_name} – {_date_fr(date_str)}"
    html = _build_html(client_name, date_str, data)
    from_addr = os.getenv("SMTP_EMAIL")
    password = os.getenv("SMTP_PASSWORD")
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    if not from_addr or not password:
        logger.warning("Email not configured (SMTP_EMAIL/SMTP_PASSWORD)")
        return False
    try:
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
        return True
    except Exception as e:
        logger.info("report_failed", extra={"to": to[:50], "error": str(e)})
        logger.exception("send_daily_report_email failed")
        return False


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
        logger.info("ordonnance_notification_sent", extra={"name": name[:50], "phone": phone[:20]})
        return True
    except Exception as e:
        logger.exception("send_ordonnance_notification failed: %s", e)
        return False
