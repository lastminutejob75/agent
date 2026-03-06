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
from urllib.parse import quote

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


def send_lead_founder_email(
    lead_id: str,
    email: str,
    daily_call_volume: str,
    medical_specialty: str = "",
    medical_specialty_label: str = "",
    specialty_other: str = "",
    primary_pain_point: str = "",
    assistant_name: str = "",
    voice_gender: str = "",
    opening_hours: Optional[Dict[str, Any]] = None,
    wants_callback: bool = False,
    callback_phone: str = "",
    is_enterprise: bool = False,
    dashboard_base_url: str = "",
    source: str = "landing_cta",
    callback_booking_date: Optional[str] = None,
    callback_booking_slot: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Email interne au fondateur : résumé nouveau lead pré-onboarding.
    Destinataire: FOUNDER_EMAIL ou ADMIN_EMAIL ou SMTP_EMAIL.
    Returns (success, error_message).
    """
    from datetime import datetime

    def _compute_lead_score(vol: str, spec: str, pain: str, oh: Optional[Dict[str, Any]] = None):
        from backend.leads_pg import compute_amplitude_score
        score = 0
        if vol == "100+":
            score += 50
        elif vol == "50-100":
            score += 30
        elif vol == "25-50":
            score += 20
        spec_lower = (spec or "").lower()
        if spec_lower in ("centre_medical", "clinique_privee"):
            score += 30
        if "secrétariat" in (pain or "") and ("n'arrive pas" in (pain or "") or "débordé" in (pain or "")):
            score += 20
        score += compute_amplitude_score(oh or {})
        if score >= 70:
            return score, "Haute priorité"
        if score >= 40:
            return score, "Moyenne"
        return score, "Standard"

    def _slot_value(slot: Any) -> str:
        if not slot or not isinstance(slot, dict) or slot.get("closed"):
            return "Fermé"
        start = (slot.get("start") or "").strip()
        end = (slot.get("end") or "").strip()
        if start or end:
            return f"{start or '?'}–{end or '?'}"
        return "Fermé"

    def _opening_hours_pretty(oh: Optional[Dict[str, Any]]) -> str:
        if not oh or not isinstance(oh, dict):
            return "—"
        days_short = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        day_keys_alt = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        values = []
        for i in range(7):
            key = str(i)
            slot = oh.get(key) or oh.get(days_short[i].lower()[:3])
            if not slot and i < len(day_keys_alt):
                slot = oh.get(day_keys_alt[i]) or oh.get(day_keys_alt[i][:3])
            values.append(_slot_value(slot))
        lines = []
        i = 0
        while i < 7:
            v = values[i]
            j = i + 1
            while j < 7 and values[j] == v:
                j += 1
            label = days_short[i] if j == i + 1 else f"{days_short[i]}–{days_short[j - 1]}"
            lines.append(f"{label} : {v}")
            i = j
        return "\n".join(lines)

    to = (
        os.getenv("FOUNDER_EMAIL")
        or os.getenv("ADMIN_EMAIL")
        or os.getenv("ADMIN_ALERT_EMAIL")
        or os.getenv("REPORT_EMAIL")
        or os.getenv("SMTP_EMAIL")
        or ""
    ).strip()
    if not to:
        logger.warning(
            "send_lead_founder_email: aucun destinataire (définir FOUNDER_EMAIL, ADMIN_EMAIL, ADMIN_ALERT_EMAIL, REPORT_EMAIL ou SMTP_EMAIL)"
        )
        return False, "Destinataire email non configuré (FOUNDER_EMAIL / ADMIN_EMAIL / ADMIN_ALERT_EMAIL / REPORT_EMAIL / SMTP_EMAIL)"

    dashboard_base_url = (dashboard_base_url or "").strip()
    if not dashboard_base_url:
        logger.warning("send_lead_founder_email: ADMIN_BASE_URL non défini — lien admin dans le mail sera absent")
    voice_label = "Féminine" if voice_gender == "female" else "Masculine"
    link = f"{dashboard_base_url.rstrip('/')}/admin/leads/{lead_id}" if dashboard_base_url else f"(configurer ADMIN_BASE_URL pour le lien) — lead_id: {lead_id}"
    specialty_display = (medical_specialty_label or "").strip() or medical_specialty or "—"
    specialty_full = specialty_display + ((" – " + (specialty_other or "").strip()) if (specialty_other or "").strip() else "")
    if is_enterprise:
        subject = f"[URGENT] Nouveau lead UWi — 100+ appels/jour — {specialty_display}"
    else:
        subject = f"Nouveau lead UWi — {daily_call_volume} appels/jour — {specialty_display}"

    # Si un créneau de rappel est réservé (callback-booking), l'ajouter explicitement dans l'objet du mail
    if callback_booking_date and callback_booking_slot:
        try:
            from datetime import datetime as dt

            d_cb = dt.strptime((callback_booking_date or "")[:10], "%Y-%m-%d")
            days_fr_cb = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
            months_fr_cb = ["janv", "fév", "mars", "avr", "mai", "juin", "juil", "août", "sept", "oct", "nov", "déc"]
            cb_date_display = f"{days_fr_cb[d_cb.weekday()]} {d_cb.day} {months_fr_cb[d_cb.month - 1]}"
        except Exception:
            cb_date_display = (callback_booking_date or "")[:10]
        subject = f"{subject} — RDV rappel {cb_date_display} à {callback_booking_slot}"

    from backend.leads_pg import compute_max_daily_amplitude
    max_amp = compute_max_daily_amplitude(opening_hours)
    amplitude_h_display = f"{max_amp:.1f} h".replace(".", ",") if max_amp is not None else "—"
    lead_score, priority_label = _compute_lead_score(daily_call_volume, medical_specialty or "", primary_pain_point or "", opening_hours)
    grand_compte = "OUI" if is_enterprise else "NON"
    rappel_txt = "OUI" if wants_callback else "NON"
    if wants_callback and (callback_phone or "").strip():
        rappel_txt += " – " + (callback_phone or "").strip()
    elif wants_callback:
        rappel_txt += " (pas de numéro)"
    hours_pretty = _opening_hours_pretty(opening_hours)
    date_local = datetime.now().strftime("%d/%m/%Y %H:%M")

    def _callback_booking_display(cb_date: Optional[str], cb_slot: Optional[str], cb_phone: str) -> str:
        if not cb_date or not cb_slot:
            return "—"
        try:
            from datetime import datetime as dt
            d = dt.strptime((cb_date or "")[:10], "%Y-%m-%d")
            days_fr = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
            months_fr = ["janv", "fév", "mars", "avr", "mai", "juin", "juil", "août", "sept", "oct", "nov", "déc"]
            date_display = f"{days_fr[d.weekday()]} {d.day} {months_fr[d.month - 1]}"
        except Exception:
            date_display = (cb_date or "")[:10]
        part = f"{date_display} à {cb_slot}"
        if (cb_phone or "").strip():
            part += f", au {(cb_phone or '').strip()}"
        return part

    rappel_reserve_html = ""
    if callback_booking_date and callback_booking_slot:
        rappel_reserve_html = f"<li><strong>Créneau de rappel réservé :</strong> {_callback_booking_display(callback_booking_date, callback_booking_slot, callback_phone)}</li>"

    rdv_block_html = ""
    if callback_booking_date and callback_booking_slot:
        rdv_display = _callback_booking_display(callback_booking_date, callback_booking_slot, callback_phone)
        rdv_block_html = f"""
  <div style="background: #e8f5e9; border: 2px solid #00e5a0; border-radius: 12px; padding: 16px; margin: 1rem 0;">
    <h2 style="font-size: 1rem; color: #1b5e20; margin: 0 0 8px 0;">📅 RDV de rappel confirmé</h2>
    <p style="font-size: 1.1rem; font-weight: 700; color: #333; margin: 0;">{rdv_display}</p>
  </div>"""

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Nouveau lead UWi</title></head>
<body style="font-family: sans-serif; max-width: 560px; margin: 0 auto; padding: 1rem;">
  <h1 style="font-size: 1.25rem;">Nouveau lead UWi (pré-onboarding)</h1>
{rdv_block_html}

  <h2 style="font-size: 0.95rem; color: #333; margin-top: 1.25rem;">📌 Priorité</h2>
  <ul style="color: #333; margin: 0.25rem 0 1rem 0;">
    <li>Appels / jour : <strong>{daily_call_volume}</strong></li>
    <li>Grand compte potentiel : <strong>{grand_compte}</strong></li>
    <li>Score : <strong>{lead_score}</strong> ({priority_label})</li>
    <li>Amplitude maximale / jour : <strong>{amplitude_h_display}</strong></li>
  </ul>

  <h2 style="font-size: 0.95rem; color: #333;">🏥 Cabinet</h2>
  <ul style="color: #333; margin: 0.25rem 0 1rem 0;">
    <li>Spécialité : {specialty_full}</li>
    <li>Douleur principale : {primary_pain_point or '—'}</li>
    <li>Souhaite être rappelé : {rappel_txt}</li>
    {rappel_reserve_html}
  </ul>

  <h2 style="font-size: 0.95rem; color: #333;">🤖 Assistante</h2>
  <ul style="color: #333; margin: 0.25rem 0 1rem 0;">
    <li>Prénom : {assistant_name or '—'}</li>
    <li>Voix : {voice_label}</li>
  </ul>
  <p style="font-size: 0.95rem; color: #333; margin: 0.5rem 0 1rem 0;">
    <strong>Horaires cabinet :</strong><br/>
    {hours_pretty.replace(chr(10), '<br/>')}
  </p>

  <h2 style="font-size: 0.95rem; color: #333;">🔗 Traiter ce lead</h2>
  <p style="margin: 0.25rem 0 1rem 0;">
    <a href="{link}" style="color:#2563eb;word-break:break-all;">{link}</a>
  </p>

  <p style="color: #666; font-size: 0.85rem; margin-top: 1.5rem;">
    —<br/>
    Source : {source or 'landing_cta'}<br/>
    Date : {date_local}
  </p>
</body>
</html>
"""
    from_addr = (
        os.getenv("POSTMARK_FROM_EMAIL") or os.getenv("EMAIL_FROM") or os.getenv("SMTP_EMAIL") or ""
    ).strip()
    token = (os.getenv("POSTMARK_SERVER_TOKEN") or "").strip()
    if token and from_addr:
        try:
            ok, err = _send_via_postmark(from_addr, to, subject, html, token)
            if ok:
                logger.info("lead_founder_email_sent via postmark", extra={"lead_id": lead_id[:24]})
            return ok, err
        except Exception as e:
            logger.exception("send_lead_founder_email postmark failed")
            return False, str(e)
    smtp_user = (os.getenv("SMTP_EMAIL") or "").strip()
    smtp_pass = (os.getenv("SMTP_PASSWORD") or "").strip()
    if smtp_user and smtp_pass:
        host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        port = int(os.getenv("SMTP_PORT", "587"))
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = smtp_user
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(html, "html", "utf-8"))
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to], msg.as_string())
            logger.info("lead_founder_email_sent via smtp", extra={"lead_id": lead_id[:24]})
            return True, None
        except Exception as e:
            logger.exception("send_lead_founder_email smtp failed")
            return False, str(e)
    return False, "Email non configuré (Postmark ou SMTP)"


def send_lead_callback_booking_email(
    lead_id: str,
    assistant_name: str,
    callback_date_iso: str,
    callback_slot: str,
    callback_phone: str,
    dashboard_base_url: str = "",
) -> Tuple[bool, Optional[str]]:
    """
    Email recap au fondateur : créneau de rappel réservé pour un lead.
    Même destinataire que send_lead_founder_email (FOUNDER_EMAIL / ADMIN_EMAIL).
    callback_date_iso au format YYYY-MM-DD.
    """
    to = (
        os.getenv("FOUNDER_EMAIL")
        or os.getenv("ADMIN_EMAIL")
        or os.getenv("ADMIN_ALERT_EMAIL")
        or os.getenv("REPORT_EMAIL")
        or os.getenv("SMTP_EMAIL")
        or ""
    ).strip()
    if not to:
        logger.warning("send_lead_callback_booking_email: aucun destinataire (FOUNDER_EMAIL/ADMIN_EMAIL/etc), skip")
        return False, "Destinataire email non configuré"
    if not (dashboard_base_url or "").strip():
        logger.warning("send_lead_callback_booking_email: ADMIN_BASE_URL manquant")
        return False, "ADMIN_BASE_URL manquant"

    try:
        from datetime import datetime as dt
        d = dt.strptime(callback_date_iso[:10], "%Y-%m-%d")
        days_fr = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        months_fr = ["janv", "fév", "mars", "avr", "mai", "juin", "juil", "août", "sept", "oct", "nov", "déc"]
        date_display = f"{days_fr[d.weekday()]} {d.day} {months_fr[d.month - 1]}"
    except Exception:
        date_display = callback_date_iso[:10]

    link = f"{dashboard_base_url.rstrip('/')}/admin/leads/{lead_id}"
    phone_display = (callback_phone or "").strip() or "—"
    subject = f"📅 Rappel réservé – {assistant_name} – {date_display} à {callback_slot}"
    date_local = datetime.now().strftime("%d/%m/%Y %H:%M")
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Rappel réservé</title></head>
<body style="font-family: sans-serif; max-width: 560px; margin: 0 auto; padding: 1rem;">
  <h1 style="font-size: 1.25rem;">Créneau de rappel réservé (lead pré-onboarding)</h1>
  <p style="font-size: 1rem; color: #333; margin: 1rem 0;">
    Le lead a choisi un créneau pour finaliser la configuration de <strong>{assistant_name}</strong>.
  </p>
  <ul style="color: #333; margin: 0.25rem 0 1rem 0;">
    <li><strong>Date :</strong> {date_display} à {callback_slot}</li>
    <li><strong>Rappel au :</strong> {phone_display}</li>
    <li><strong>Assistante :</strong> {assistant_name}</li>
  </ul>
  <p style="margin: 1rem 0;">
    <a href="{link}" style="color:#2563eb;word-break:break-all;">Voir le lead → {link}</a>
  </p>
  <p style="color: #666; font-size: 0.85rem; margin-top: 1.5rem;">
    —<br/>
    Date envoi : {date_local}
  </p>
</body>
</html>
"""
    from_addr = (
        os.getenv("POSTMARK_FROM_EMAIL") or os.getenv("EMAIL_FROM") or os.getenv("SMTP_EMAIL") or ""
    ).strip()
    token = (os.getenv("POSTMARK_SERVER_TOKEN") or "").strip()
    if token and from_addr:
        try:
            ok, err = _send_via_postmark(from_addr, to, subject, html, token)
            if ok:
                logger.info("lead_callback_booking_email_sent via postmark", extra={"lead_id": lead_id[:24]})
            return ok, err
        except Exception as e:
            logger.exception("send_lead_callback_booking_email postmark failed")
            return False, str(e)
    smtp_user = (os.getenv("SMTP_EMAIL") or "").strip()
    smtp_pass = (os.getenv("SMTP_PASSWORD") or "").strip()
    if smtp_user and smtp_pass:
        host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        port = int(os.getenv("SMTP_PORT", "587"))
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = smtp_user
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(html, "html", "utf-8"))
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to], msg.as_string())
            logger.info("lead_callback_booking_email_sent via smtp", extra={"lead_id": lead_id[:24]})
            return True, None
        except Exception as e:
            logger.exception("send_lead_callback_booking_email smtp failed")
            return False, str(e)
    return False, "Email non configuré (Postmark ou SMTP)"


def send_welcome_email(
    email: str,
    client_name: str,
    assistant_id: str,
    plan_key: str,
    phone_number: str,
    app_url: str = "",
    temp_password: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Email de bienvenue au client après création tenant (Vapi + Stripe + Twilio).
    Destinataire : email du client.
    Lien direct : /login?email={email}&welcome=1 pour accès dashboard.
    Returns (success, error_message).
    """
    to = (email or "").strip().lower()
    if not to:
        logger.warning("send_welcome_email: email vide, skip")
        return False, "Email vide"

    assistant_display = (assistant_id or "Sophie").capitalize()
    plan_display = {"starter": "Starter (99€/mois)", "growth": "Growth (149€/mois)", "pro": "Pro (199€/mois)"}.get(
        (plan_key or "").lower(), plan_key or "—"
    )
    phone_display = (phone_number or "").strip() or "À configurer"
    base_url = (
        app_url or os.getenv("CLIENT_APP_ORIGIN") or os.getenv("VITE_UWI_APP_URL") or os.getenv("VITE_SITE_URL") or "https://www.uwiapp.com"
    ).strip().rstrip("/")
    login_url = f"{base_url}/login?email={quote(to)}&welcome=1"
    password_block = ""
    if temp_password:
        password_block = f"""
  <div style="margin: 1rem 0; padding: 1rem; border: 1px solid #f59e0b; border-radius: 12px; background: #fff7ed;">
    <p style="margin: 0 0 0.5rem 0; font-weight: 700; color: #9a3412;">Mot de passe temporaire</p>
    <p style="margin: 0; color: #7c2d12;">
      <strong style="font-family: monospace; font-size: 1rem;">{temp_password}</strong>
    </p>
    <p style="margin: 0.75rem 0 0 0; color: #7c2d12; font-size: 0.92rem;">
      Pour votre sécurité, changez ce mot de passe dès votre première connexion.
    </p>
  </div>
"""

    subject = f"Bienvenue sur UWi — {client_name}"
    from datetime import datetime
    date_local = datetime.now().strftime("%d/%m/%Y %H:%M")
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Bienvenue UWi</title></head>
<body style="font-family: sans-serif; max-width: 560px; margin: 0 auto; padding: 1rem;">
  <h1 style="font-size: 1.25rem;">Bienvenue sur UWi — {client_name}</h1>
  <p style="font-size: 1rem; color: #333; margin: 1rem 0;">
    Votre compte a été créé avec succès. Voici vos informations :
  </p>
  <ul style="color: #333; margin: 0.25rem 0 1rem 0;">
    <li><strong>Assistante vocale :</strong> {assistant_display}</li>
    <li><strong>Plan :</strong> {plan_display}</li>
    <li><strong>Numéro que les patients appellent :</strong> {phone_display}</li>
  </ul>
  {password_block}
  <p style="margin: 1.5rem 0;">
    <a href="{login_url}" style="display:inline-block;background:linear-gradient(135deg,#14b8a6,#0d9488);color:#fff;padding:12px 24px;text-decoration:none;border-radius:8px;font-weight:700;font-size:1rem;">
      Accéder à mon espace
    </a>
  </p>
  <p style="color: #666; font-size: 0.9rem; margin-top: 1.5rem;">
    Connectez-vous avec cet email pour gérer votre cabinet et consulter les rapports d'appels.
  </p>
  <p style="color: #666; font-size: 0.85rem; margin-top: 1.5rem;">
    —<br/>
    Date d'envoi : {date_local}
  </p>
</body>
</html>
"""
    from_addr = (
        os.getenv("POSTMARK_FROM_EMAIL") or os.getenv("EMAIL_FROM") or os.getenv("SMTP_EMAIL") or ""
    ).strip()
    token = (os.getenv("POSTMARK_SERVER_TOKEN") or "").strip()
    if token and from_addr:
        try:
            ok, err = _send_via_postmark(from_addr, to, subject, html, token)
            if ok:
                logger.info("welcome_email_sent via postmark", extra={"to": to[:50]})
            return ok, err
        except Exception as e:
            logger.exception("send_welcome_email postmark failed")
            return False, str(e)
    smtp_user = (os.getenv("SMTP_EMAIL") or "").strip()
    smtp_pass = (os.getenv("SMTP_PASSWORD") or "").strip()
    if smtp_user and smtp_pass:
        host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        port = int(os.getenv("SMTP_PORT", "587"))
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = smtp_user
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(html, "html", "utf-8"))
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to], msg.as_string())
            logger.info("welcome_email_sent via smtp", extra={"to": to[:50]})
            return True, None
        except Exception as e:
            logger.exception("send_welcome_email smtp failed")
            return False, str(e)
    return False, "Email non configuré (Postmark ou SMTP)"


def send_agenda_contact_request_email(
    tenant_name: str,
    tenant_email: str,
    software: str,
    software_other: str = "",
) -> Tuple[bool, Optional[str]]:
    """
    Email interne : demande de connexion agenda (logiciel métier Pabau/Maiia/Doctolib).
    Destinataire : ADMIN_ALERT_EMAIL ou REPORT_EMAIL.
    Returns (success, error_message).
    """
    to = (
        os.getenv("ADMIN_ALERT_EMAIL")
        or os.getenv("REPORT_EMAIL")
        or os.getenv("OWNER_EMAIL")
        or ""
    ).strip()
    if not to:
        logger.warning("send_agenda_contact_request: no ADMIN_ALERT_EMAIL/REPORT_EMAIL, skip")
        return False, "ADMIN_ALERT_EMAIL ou REPORT_EMAIL non défini"
    software_display = (software_other or software or "—").strip()
    if software == "autre" and software_other:
        software_display = software_other.strip()
    subject = f"📋 Demande connexion agenda – {tenant_name}"
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Demande agenda</title></head>
<body style="font-family: sans-serif; max-width: 560px; margin: 0 auto; padding: 1rem;">
  <h1 style="font-size: 1.2rem;">Demande de connexion agenda</h1>
  <p><strong>Client :</strong> {tenant_name}</p>
  <p><strong>Email :</strong> {tenant_email}</p>
  <p><strong>Logiciel :</strong> {software_display}</p>
  <p style="color: #666; font-size: 0.9rem;">Contacter le client sous 24h pour finaliser la connexion.</p>
</body>
</html>
"""
    use_postmark = (os.getenv("EMAIL_PROVIDER") or "").strip().lower() == "postmark" or bool(
        (os.getenv("POSTMARK_SERVER_TOKEN") or "").strip()
    )
    from_addr = (os.getenv("EMAIL_FROM") or os.getenv("SMTP_EMAIL") or os.getenv("REPORT_EMAIL") or "").strip()
    if use_postmark and (os.getenv("POSTMARK_SERVER_TOKEN") or "").strip():
        ok, err = _send_via_postmark(
            from_addr or to,
            to,
            subject,
            html,
            (os.getenv("POSTMARK_SERVER_TOKEN") or "").strip(),
        )
        return ok, err
    smtp_user = (os.getenv("SMTP_EMAIL") or "").strip()
    smtp_pass = (os.getenv("SMTP_PASSWORD") or "").strip()
    if smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = smtp_user
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(html, "html", "utf-8"))
            with smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", "587"))) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to], msg.as_string())
            return True, None
        except Exception as e:
            return False, str(e)
    return False, "Email non configuré"
