from __future__ import annotations

import logging
import os
import uuid
import json
import smtplib
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.pg_pool import pg_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public", tags=["public_pages"])
_public_events_schema_ready = False
_public_bookings_schema_ready = False


DEMO_PRACTITIONER: Dict[str, Any] = {
    "slug": "cabinet-dupond-demo",
    "tenantId": None,
    "name": "Cabinet Dupond",
    "initials": "CD",
    "specialty": "Medecine generale",
    "city": "Lille",
    "verified": True,
    "rating": 4.9,
    "reviewCount": 142,
    "reviewsVerified": True,
    "photoUrl": "",
    "address": {"street": "12 rue Gambetta", "postalCode": "59000", "city": "Lille", "country": "FR"},
    "access": "Metro Republique Beaux-Arts",
    "parking": "Parking Gambetta",
    "phone": "03 20 12 34 56",
    "phoneTel": "+33320123456",
    "languages": ["Francais", "Anglais"],
    "fee": "Secteur 1 - Tarifs conventionnes",
    "carteVitale": True,
    "pmr": True,
    "voiceEnabled": False,
    "vapiAssistantId": "",
    "newPatients": "Selon disponibilite",
    "documents": "Carte Vitale, piece d'identite, ordonnances et examens recents.",
    "whatsappEnabled": True,
    "whatsappUrl": "https://wa.me/33000000000?text=Bonjour%2C%20je%20souhaite%20prendre%20rendez-vous",
    "canonicalUrl": "https://www.uwiapp.com/p/cabinet-dupond-demo",
    "openingHours": [
        {"day": "Lundi", "opens": "08:30", "closes": "18:30", "schemaDay": "Monday"},
        {"day": "Mardi", "opens": "08:30", "closes": "18:30", "schemaDay": "Tuesday"},
        {"day": "Mercredi", "opens": "08:30", "closes": "18:30", "schemaDay": "Wednesday"},
        {"day": "Jeudi", "opens": "08:30", "closes": "18:30", "schemaDay": "Thursday"},
        {"day": "Vendredi", "opens": "08:30", "closes": "17:30", "schemaDay": "Friday"},
        {"day": "Samedi", "opens": None, "closes": None, "schemaDay": "Saturday"},
        {"day": "Dimanche", "opens": None, "closes": None, "schemaDay": "Sunday"},
    ],
}

DEMO_SLOTS: List[Dict[str, Any]] = [
    {"id": "s1", "label": "aujourd'hui a 14:00", "day": "Auj.", "time": "14:00", "motifs": ["Consultation", "Suivi", "Premiere consultation", "Renouvellement"]},
    {"id": "s2", "label": "aujourd'hui a 16:30", "day": "Auj.", "time": "16:30", "motifs": ["Consultation", "Suivi"]},
    {"id": "s3", "label": "mercredi a 09:15", "day": "Mer.", "time": "09:15", "motifs": ["Consultation", "Suivi", "Premiere consultation"]},
    {"id": "s4", "label": "mercredi a 11:00", "day": "Mer.", "time": "11:00", "motifs": ["Consultation", "Suivi"]},
    {"id": "s5", "label": "jeudi a 10:00", "day": "Jeu.", "time": "10:00", "motifs": ["Consultation", "Suivi", "Renouvellement"]},
    {"id": "s6", "label": "jeudi a 15:45", "day": "Jeu.", "time": "15:45", "motifs": ["Consultation", "Suivi"]},
]

DEMO_SEARCH = [
    {"id": "cabinet-dupond-demo", "name": "Cabinet Dupond", "specialty": "Medecine generale", "city": "Lille", "availability": "Disponible aujourd'hui", "acceptsNewPatients": True, "url": "/p/cabinet-dupond-demo"},
    {"id": "karim-benali", "name": "Dr Karim Benali", "specialty": "Medecin generaliste", "city": "Tourcoing", "availability": "Demain matin", "acceptsNewPatients": True, "url": "/p/dr-karim-benali"},
    {"id": "sophie-martin", "name": "Dr Sophie Martin", "specialty": "Dermatologue", "city": "Lille", "availability": "Cette semaine", "acceptsNewPatients": False, "url": "/p/dr-sophie-martin"},
    {"id": "amina-haddad", "name": "Dr Amina Haddad", "specialty": "Pediatre", "city": "Roubaix", "availability": "Sous 48h", "acceptsNewPatients": True, "url": "/p/dr-amina-haddad"},
]


class PublicBookingRequest(BaseModel):
    slug: str = Field(..., min_length=2, max_length=160)
    slotId: str = Field(..., min_length=1, max_length=80)
    slotLabel: str = Field(..., min_length=2, max_length=140)
    motif: str = Field(..., min_length=2, max_length=120)
    patientName: str = Field(..., min_length=2, max_length=200)
    patientPhone: str = Field(..., min_length=5, max_length=40)
    patientEmail: Optional[str] = Field(None, max_length=254)
    source: str = Field("page_publique", max_length=40)
    slotSource: Optional[str] = Field(None, max_length=20)
    startIso: Optional[str] = Field(None, max_length=64)
    endIso: Optional[str] = Field(None, max_length=64)


def _sanitize_public_booking_payload(payload: PublicBookingRequest) -> PublicBookingRequest:
    """Valide téléphone / email et normalise le numéro pour stockage et SMS."""
    from backend.db import normalize_phone_number
    from backend.guards import validate_email, validate_phone

    phone_raw = (payload.patientPhone or "").strip()
    if not validate_phone(phone_raw):
        raise HTTPException(status_code=422, detail="Numéro de téléphone invalide.")
    normalized_phone = normalize_phone_number(phone_raw) or phone_raw

    email_raw = (payload.patientEmail or "").strip()
    if email_raw and not validate_email(email_raw):
        raise HTTPException(status_code=422, detail="Adresse email invalide.")

    return payload.model_copy(
        update={
            "patientPhone": normalized_phone,
            "patientEmail": email_raw.lower() if email_raw else None,
        }
    )


class PublicAnalyticsEventRequest(BaseModel):
    slug: str = Field(..., min_length=2, max_length=160)
    event: str = Field(..., min_length=2, max_length=80)
    source: str = Field("direct", max_length=40)
    slotId: Optional[str] = Field(None, max_length=80)
    slotLabel: Optional[str] = Field(None, max_length=140)
    motif: Optional[str] = Field(None, max_length=120)
    question: Optional[str] = Field(None, max_length=180)
    query: Optional[str] = Field(None, max_length=180)
    resultsCount: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


def _norm(value: str) -> str:
    return (value or "").strip().lower()


def _demo_practitioner(slug: str) -> Dict[str, Any]:
    data = dict(DEMO_PRACTITIONER)
    data["slug"] = slug
    data["canonicalUrl"] = f"https://www.uwiapp.com/p/{slug}"
    return data


def _append_whatsapp_text(url: str, text: str) -> str:
    if not url:
        return ""
    separator = "&" if "?" in url else "?"
    if "text=" in url:
        return url
    return f"{url}{separator}text={quote(text)}"


def _build_whatsapp_followup(practitioner: Dict[str, Any], payload: PublicBookingRequest) -> Dict[str, Any]:
    if not practitioner.get("whatsappEnabled"):
        return {"enabled": False, "whatsappUrl": None}
    template = (
        f"Bonjour, je viens de faire une demande de RDV ({payload.slotLabel}) "
        f"pour {payload.motif}, au nom de {payload.patientName}."
    )
    whatsapp_url = str(practitioner.get("whatsappUrl") or "").strip()
    if whatsapp_url:
        return {"enabled": True, "whatsappUrl": _append_whatsapp_text(whatsapp_url, template)}
    phone = str(practitioner.get("phoneTel") or practitioner.get("phone") or "").strip()
    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits:
        if digits.startswith("00"):
            digits = digits[2:]
        return {"enabled": True, "whatsappUrl": f"https://wa.me/{digits}?text={quote(template)}"}
    return {"enabled": False, "whatsappUrl": None}


def _send_cabinet_email(
    practitioner: Dict[str, Any],
    payload: PublicBookingRequest,
    confirmation_id: str,
    booking_code: str = "",
) -> bool:
    to_email = (
        str(practitioner.get("email") or "").strip()
        or (os.environ.get("PUBLIC_BOOKING_CABINET_EMAIL_TO") or "").strip()
        or (os.environ.get("OWNER_EMAIL") or "").strip()
        or (os.environ.get("ADMIN_NOTIFICATION_EMAIL") or "").strip()
        or (os.environ.get("REPORT_EMAIL") or "").strip()
    )
    if not to_email:
        return False

    from backend.booking_code import format_booking_code

    code_label = format_booking_code(booking_code)
    subject = f"UWI - Nouvelle demande RDV ({practitioner.get('name')})"
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Nouvelle demande RDV</title></head>
<body style="font-family: Arial, sans-serif; max-width: 620px; margin: 0 auto; padding: 16px;">
  <h2 style="margin:0 0 12px;">Nouvelle demande de rendez-vous</h2>
  <p>Une demande a ete effectuee depuis la page publique UWI.</p>
  <ul>
    <li><strong>Confirmation ID:</strong> {confirmation_id}</li>
    {f"<li><strong>Code rendez-vous:</strong> {code_label}</li>" if code_label else ""}
    <li><strong>Praticien:</strong> {practitioner.get("name") or "Cabinet"}</li>
    <li><strong>Slug:</strong> {payload.slug}</li>
    <li><strong>Creneau:</strong> {payload.slotLabel}</li>
    <li><strong>Motif:</strong> {payload.motif}</li>
    <li><strong>Patient:</strong> {payload.patientName}</li>
    <li><strong>Telephone:</strong> {payload.patientPhone}</li>
    <li><strong>Email:</strong> {(payload.patientEmail or "").strip() or "—"}</li>
    <li><strong>Source:</strong> {payload.source}</li>
  </ul>
  <p style="color:#666;font-size:12px;">Envoye automatiquement par UWI.</p>
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
                return True
            logger.warning("public booking cabinet email postmark failed status=%s", response.status_code)
        except Exception as exc:
            logger.warning("public booking cabinet email postmark exception: %s", exc)

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
            return True
        except Exception as exc:
            logger.warning("public booking cabinet email smtp exception: %s", exc)
    return False


_DAY_SCHEMA = {
    "monday": "Monday",
    "tuesday": "Tuesday",
    "wednesday": "Wednesday",
    "thursday": "Thursday",
    "friday": "Friday",
    "saturday": "Saturday",
    "sunday": "Sunday",
}
_DAY_FR = {
    "monday": "Lundi",
    "tuesday": "Mardi",
    "wednesday": "Mercredi",
    "thursday": "Jeudi",
    "friday": "Vendredi",
    "saturday": "Samedi",
    "sunday": "Dimanche",
}


def _map_opening_hours(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        day_key = str(row.get("day") or "").lower()
        label = _DAY_FR.get(day_key, day_key.capitalize())
        schema = _DAY_SCHEMA.get(day_key, day_key.capitalize())
        if not row.get("is_open"):
            out.append({"day": label, "opens": None, "closes": None, "schemaDay": schema})
            continue
        opens = row.get("morning_start") or row.get("afternoon_start")
        closes = row.get("afternoon_end") or row.get("morning_end")
        if not opens and not closes:
            out.append({"day": label, "opens": None, "closes": None, "schemaDay": schema})
            continue
        out.append({"day": label, "opens": opens, "closes": closes, "schemaDay": schema})
    return out or list(DEMO_PRACTITIONER["openingHours"])


def _try_fetch_practitioner_from_cabinet_profile(slug: str) -> Optional[Dict[str, Any]]:
    """Résolution slug via cabinet_profile_pg (PG + SQLite local)."""
    try:
        from backend.cabinet_profile_pg import fetch_public_practitioner_bundle_by_slug
        from backend.public_slug_cache import remember_slug_tenant

        data = fetch_public_practitioner_bundle_by_slug(slug)
        if not data:
            return None

        tid = int(data["tenant_id"])
        remember_slug_tenant(slug, tid)
        profile = data.get("profile") or {}
        params = data.get("params") if isinstance(data.get("params"), dict) else {}
        assistant = data.get("assistant") or {}
        cabinet_name = str(profile.get("cabinet_name") or params.get("business_name") or "").strip()
        practitioner_name = str(profile.get("practitioner_name") or params.get("practitioner_name") or "").strip()
        name = practitioner_name or cabinet_name
        if not name:
            return None
        motives = [
            str(r.get("label") or "").strip()
            for r in (data.get("reasons") or [])
            if isinstance(r, dict) and r.get("enabled", True) and str(r.get("label") or "").strip()
        ]
        if not motives:
            motives = list(_DEFAULT_PUBLIC_MOTIFS)
        vapi_assistant_id = str(
            assistant.get("vapi_assistant_id")
            or params.get("vapi_assistant_id")
            or (params.get("public_page") or {}).get("vapiAssistantId")
            or ""
        ).strip()
        phone = str(profile.get("phone") or params.get("phone_number") or params.get("callback_phone") or "").strip()
        city = str(profile.get("city") or params.get("city") or DEMO_PRACTITIONER["city"]).strip()
        return {
            **_demo_practitioner(slug),
            "tenantId": str(tid),
            "name": name,
            "initials": "".join(part[:1] for part in name.split()[:2]).upper() or "UW",
            "specialty": str(profile.get("specialty") or params.get("specialty_label") or DEMO_PRACTITIONER["specialty"]),
            "city": city,
            "email": str(profile.get("email") or params.get("contact_email") or "").strip(),
            "phone": phone or DEMO_PRACTITIONER["phone"],
            "phoneTel": phone or DEMO_PRACTITIONER["phoneTel"],
            "photoUrl": str(profile.get("practitioner_photo_url") or "").strip(),
            "address": {
                "street": str(profile.get("address_line") or params.get("address_line1") or "").strip(),
                "postalCode": str(profile.get("postal_code") or params.get("postal_code") or "").strip(),
                "city": city,
                "country": "FR",
            },
            "access": str(assistant.get("access_instructions") or params.get("access_instructions") or "").strip(),
            "parking": str(assistant.get("parking_info") or params.get("parking_info") or "").strip(),
            "pmr": bool(assistant.get("pmr_access") or params.get("pmr_access")),
            "fee": str(assistant.get("payment_methods") or params.get("payment_methods") or DEMO_PRACTITIONER["fee"]),
            "voiceEnabled": bool(vapi_assistant_id),
            "vapiAssistantId": vapi_assistant_id,
            "openingHours": _map_opening_hours(data.get("opening_hours") or []),
            "newPatients": "Oui" if profile.get("accepts_new_patients", True) else "Selon disponibilite",
            "documents": str(assistant.get("documents_hint") or params.get("documents_hint") or DEMO_PRACTITIONER["documents"]),
        }
    except Exception as exc:
        logger.info("public practitioner cabinet_profile fallback slug=%s: %s", slug, exc)
        return None


def _try_fetch_practitioner(slug: str) -> Optional[Dict[str, Any]]:
    """
    Résout un practitioner via son slug public.
    `public_slug` est stocké dans tenant_config.params_json (pas de colonne dédiée).
    Schéma `tenants` : tenant_id, name, timezone, status, created_at.
    Le reste (contact_email, callback_phone, public_page) vit dans params_json.
    """
    cabinet = _try_fetch_practitioner_from_cabinet_profile(slug)
    if cabinet:
        return cabinet
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT t.tenant_id, t.name, c.params_json
                    FROM tenants t
                    LEFT JOIN tenant_config c ON c.tenant_id = t.tenant_id
                    WHERE c.params_json->>'public_slug' = %s
                       OR c.params_json->>'slug' = %s
                    LIMIT 1
                    """,
                    (slug, slug),
                )
                row = cur.fetchone()
    except Exception as exc:
        logger.info("public practitioner fallback slug=%s reason=%s", slug, exc)
        return None
    if not row:
        return None
    raw_params = row.get("params_json")
    if isinstance(raw_params, dict):
        params = raw_params
    elif isinstance(raw_params, str) and raw_params.strip():
        try:
            params = json.loads(raw_params)
        except Exception:
            params = {}
    else:
        params = {}
    public_page = params.get("public_page") if isinstance(params.get("public_page"), dict) else {}
    vapi_assistant_id = str(public_page.get("vapiAssistantId") or params.get("vapi_assistant_id") or "").strip()
    contact_email = (params.get("contact_email") or "").strip()
    callback_phone = (params.get("callback_phone") or params.get("phone") or "").strip()
    name = public_page.get("name") or row.get("name") or DEMO_PRACTITIONER["name"]
    city = public_page.get("city") or params.get("city") or DEMO_PRACTITIONER["city"]
    specialty = public_page.get("specialty") or params.get("specialty") or DEMO_PRACTITIONER["specialty"]
    return {
        **_demo_practitioner(slug),
        "tenantId": str(row["tenant_id"]),
        "name": name,
        "initials": "".join(part[:1] for part in str(name).split()[:2]).upper() or "UW",
        "specialty": specialty,
        "city": city,
        "email": contact_email,
        "phone": public_page.get("phone") or callback_phone or DEMO_PRACTITIONER["phone"],
        "phoneTel": public_page.get("phoneTel") or callback_phone or DEMO_PRACTITIONER["phoneTel"],
        "address": public_page.get("address") or DEMO_PRACTITIONER["address"],
        "fee": public_page.get("fee") or DEMO_PRACTITIONER["fee"],
        "voiceEnabled": bool(vapi_assistant_id),
        "vapiAssistantId": vapi_assistant_id,
        "openingHours": public_page.get("openingHours") or DEMO_PRACTITIONER["openingHours"],
    }


def _dispatch_booking_notifications(
    practitioner: Dict[str, Any],
    payload: PublicBookingRequest,
    booking_status: str,
    confirmation_id: str,
    booking_code: str,
) -> Tuple[bool, bool, bool]:
    """SMS patient + cabinet et email cabinet (hors requête HTTP pour réponse plus rapide)."""
    from backend.booking_code import format_booking_code

    code_label = format_booking_code(booking_code)
    code_suffix = f" Code rendez-vous : {code_label}." if code_label else ""
    if booking_status == "confirmed":
        patient_sms = (
            f"Bonjour {payload.patientName.split()[0]}, votre rendez-vous avec "
            f"{practitioner.get('name')} le {payload.slotLabel} pour {payload.motif} est confirme."
            f"{code_suffix} Conservez ce code pour modifier ou annuler. UWI"
        )
    else:
        patient_sms = (
            f"Bonjour {payload.patientName.split()[0]}, votre demande de RDV avec "
            f"{practitioner.get('name')} le {payload.slotLabel} pour {payload.motif} a bien ete recue."
            f"{code_suffix} Le cabinet vous confirmera dans les meilleurs delais. UWI"
        )
    patient_sms_sent = _send_sms(payload.patientPhone, patient_sms)

    cabinet_number = os.environ.get("PUBLIC_BOOKING_CABINET_SMS_TO") or os.environ.get("OWNER_PHONE_NUMBER") or ""
    cabinet_sms_sent = False
    if cabinet_number:
        cabinet_sms_sent = _send_sms(
            cabinet_number,
            f"UWI - Nouvelle demande RDV: {payload.patientName}, {payload.slotLabel}, {payload.motif}. "
            f"Tel: {payload.patientPhone}{f' Code: {code_label}' if code_label else ''}",
        )
    cabinet_email_sent = _send_cabinet_email(practitioner, payload, confirmation_id, booking_code)
    return patient_sms_sent, cabinet_sms_sent, cabinet_email_sent


def _send_sms(to_number: str, body: str) -> bool:
    sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
    token = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
    from_number = (os.environ.get("TWILIO_PHONE_NUMBER") or "").strip()
    if not (sid and token and from_number and to_number):
        return False
    try:
        from twilio.rest import Client

        Client(sid, token).messages.create(body=body[:1500], from_=from_number, to=to_number)
        return True
    except Exception as exc:
        logger.warning("public booking sms failed: %s", exc)
        return False


def _insert_booking(
    payload: PublicBookingRequest,
    tenant_id: Optional[str],
    *,
    status: str = "pending",
    booking_code: Optional[str] = None,
    google_event_id: Optional[str] = None,
) -> Dict[str, str]:
    from backend.public_bookings_pg import insert_public_booking

    tid: Optional[int] = None
    if tenant_id is not None and str(tenant_id).strip().isdigit():
        tid = int(tenant_id)
    booking_id = str(uuid.uuid4())
    return insert_public_booking(
        booking_id=booking_id,
        tenant_id=tid,
        slot_id=payload.slotId,
        slot_label=payload.slotLabel,
        patient_name=payload.patientName,
        patient_phone=payload.patientPhone,
        patient_email=payload.patientEmail,
        motif=payload.motif,
        source=payload.source,
        status=status,
        start_iso=(payload.startIso or "").strip() or None,
        booking_code=booking_code,
        google_event_id=google_event_id,
    )


def _ensure_public_events_schema() -> None:
    global _public_events_schema_ready
    if _public_events_schema_ready:
        return
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS public_page_events (
                      id UUID PRIMARY KEY,
                      tenant_id BIGINT REFERENCES tenants(tenant_id) ON DELETE SET NULL,
                      slug VARCHAR(160) NOT NULL,
                      event_name VARCHAR(80) NOT NULL,
                      source VARCHAR(40) DEFAULT 'direct',
                      slot_id VARCHAR(80),
                      slot_label VARCHAR(140),
                      motif VARCHAR(120),
                      question VARCHAR(180),
                      query VARCHAR(180),
                      results_count INT,
                      metadata JSONB DEFAULT '{}'::jsonb,
                      created_at TIMESTAMP DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_public_page_events_slug_created
                    ON public_page_events (slug, created_at DESC)
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_public_page_events_tenant_created
                    ON public_page_events (tenant_id, created_at DESC)
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_public_page_events_event_created
                    ON public_page_events (event_name, created_at DESC)
                    """
                )
                conn.commit()
        _public_events_schema_ready = True
    except Exception as exc:
        logger.warning("public events schema init failed: %s", exc)


def _coerce_tenant_id_for_db(tenant_id: Optional[str]) -> Optional[int]:
    if tenant_id is None:
        return None
    raw = str(tenant_id).strip()
    if raw.isdigit():
        return int(raw)
    return None


def _resolve_tenant_id(slug: str) -> Optional[str]:
    from backend.public_slug_cache import tenant_id_for_slug

    tid = tenant_id_for_slug(slug)
    return str(tid) if tid else None


def _insert_public_event(payload: PublicAnalyticsEventRequest, tenant_id: Optional[str]) -> None:
    _ensure_public_events_schema()
    event_name = _norm(payload.event).replace(" ", "_")
    if not event_name:
        return
    event_id = str(uuid.uuid4())
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public_page_events (
                      id, tenant_id, slug, event_name, source, slot_id, slot_label,
                      motif, question, query, results_count, metadata, created_at
                    )
                    VALUES (
                      %s, %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, %s::jsonb, NOW()
                    )
                    """,
                    (
                        event_id,
                        _coerce_tenant_id_for_db(str(tenant_id) if tenant_id is not None else None),
                        payload.slug,
                        event_name,
                        payload.source,
                        payload.slotId,
                        payload.slotLabel,
                        payload.motif,
                        payload.question,
                        payload.query,
                        payload.resultsCount,
                        json.dumps(payload.metadata or {}, ensure_ascii=False),
                    ),
                )
                conn.commit()
    except Exception as exc:
        logger.debug("public analytics insert skipped: %s", exc)


def _analytics_summary(slug: str, days: int) -> Dict[str, Any]:
    _ensure_public_events_schema()
    safe_days = max(1, min(int(days or 30), 365))
    base = {
        "slug": slug,
        "days": safe_days,
        "pageViews": 0,
        "slotClicks": 0,
        "bookingConfirmed": 0,
        "voiceStarted": 0,
        "voiceEnded": 0,
        "modalOpened": 0,
        "modalClosedWithoutConfirm": 0,
        "chatMessages": 0,
        "faqClicks": 0,
        "whatsappClicks": 0,
        "searchUsed": 0,
    }
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_name, COUNT(*)::int AS c
                    FROM public_page_events
                    WHERE slug = %s
                      AND created_at >= (NOW() - (%s || ' days')::interval)
                    GROUP BY event_name
                    """,
                    (slug, safe_days),
                )
                rows = cur.fetchall() or []
    except Exception as exc:
        logger.debug("public analytics summary fallback: %s", exc)
        return base
    mapping = {
        "page_view": "pageViews",
        "slot_clicked": "slotClicks",
        "booking_confirmed": "bookingConfirmed",
        "voice_started": "voiceStarted",
        "voice_ended": "voiceEnded",
        "modal_opened": "modalOpened",
        "modal_closed_without_confirm": "modalClosedWithoutConfirm",
        "chat_message_sent": "chatMessages",
        "faq_clicked": "faqClicks",
        "whatsapp_clicked": "whatsappClicks",
        "search_used": "searchUsed",
    }
    for row in rows:
        key = mapping.get(str(row.get("event_name") or ""))
        if key:
            base[key] = int(row.get("c") or 0)
    return base


def load_public_slugs() -> List[str]:
    """Liste les slugs publics actifs (alias public pour sitemap + prewarm)."""
    return _load_public_slugs()


def _load_public_slugs() -> List[str]:
    """
    Liste les slugs publics actifs (sitemap).
    `public_slug` est stocké dans tenant_config.params_json.
    """
    slugs: List[str] = []
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT params_json->>'public_slug' AS public_slug
                    FROM tenant_config c
                    JOIN tenants t ON t.tenant_id = c.tenant_id
                    WHERE COALESCE(params_json->>'public_slug', '') <> ''
                      AND COALESCE(t.status, 'active') = 'active'
                    ORDER BY public_slug
                    LIMIT 5000
                    """
                )
                rows = cur.fetchall() or []
                slugs = [str(row.get("public_slug", "")).strip() for row in rows if str(row.get("public_slug", "")).strip()]
    except Exception as exc:
        logger.info("public sitemap fallback reason=%s", exc)
    if not slugs:
        slugs = [DEMO_PRACTITIONER["slug"]]
    return slugs


_PRACTITIONER_HTTP_CACHE: Dict[str, tuple] = {}
_PRACTITIONER_CACHE_TTL = 300.0


@router.get("/practitioner/{slug}")
async def get_public_practitioner(slug: str, requireExists: bool = Query(False)) -> Dict[str, Any]:
    import time

    cache_key = f"{slug}:{bool(requireExists)}"
    hit = _PRACTITIONER_HTTP_CACHE.get(cache_key)
    if hit and (time.time() - hit[0]) < _PRACTITIONER_CACHE_TTL:
        return hit[1]

    practitioner = _try_fetch_practitioner(slug)
    if practitioner:
        out = {**practitioner, "source": "tenant"}
        _PRACTITIONER_HTTP_CACHE[cache_key] = (time.time(), out)
        return out
    if slug == DEMO_PRACTITIONER["slug"]:
        out = {**_demo_practitioner(slug), "source": "demo"}
        _PRACTITIONER_HTTP_CACHE[cache_key] = (time.time(), out)
        return out
    if requireExists:
        raise HTTPException(status_code=404, detail="public_practitioner_not_found")
    out = {**_demo_practitioner(slug), "source": "demo"}
    _PRACTITIONER_HTTP_CACHE[cache_key] = (time.time(), out)
    return out


_DEFAULT_PUBLIC_MOTIFS = ["Consultation", "Suivi", "Premiere consultation", "Renouvellement"]
_FR_WEEKDAYS_SHORT = ["Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam.", "Dim."]
_FR_WEEKDAYS_LONG = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def _upsert_public_patient_safe(tenant_id: int, payload: PublicBookingRequest) -> None:
    try:
        _upsert_public_patient(tenant_id, payload)
    except Exception as exc:
        logger.warning("public_book patient upsert skipped: %s", exc)


def _track_booking_confirmed_event(
    payload: PublicBookingRequest,
    tenant_id: Optional[int],
    confirmation_id: str,
    booking_status: str = "pending",
) -> None:
    try:
        _insert_public_event(
            PublicAnalyticsEventRequest(
                slug=payload.slug,
                event="booking_confirmed",
                source=payload.source,
                slotId=payload.slotId,
                slotLabel=payload.slotLabel,
                motif=payload.motif,
                metadata={"confirmationId": confirmation_id, "status": booking_status},
            ),
            str(tenant_id) if tenant_id is not None else None,
        )
    except Exception as exc:
        logger.debug("public booking analytics skipped: %s", exc)

    if not tenant_id:
        return
    try:
        from backend.db import create_ivr_event

        event_name = "booking_confirmed" if booking_status == "confirmed" else "booking_requested"
        create_ivr_event(
            int(tenant_id),
            f"public-{confirmation_id}",
            event_name,
            context=json.dumps(
                {
                    "source": payload.source,
                    "slot_label": payload.slotLabel,
                    "patient_name": payload.patientName,
                    "motif": payload.motif,
                },
                ensure_ascii=False,
            )[:500],
        )
    except Exception as exc:
        logger.debug("public booking ivr_event skipped: %s", exc)


def _upsert_public_patient(tenant_id: int, payload: PublicBookingRequest) -> None:
    """Met à jour la fiche patient *si et seulement si elle existe déjà*.

    Choix produit : un RDV pris depuis la page publique (ou via le chat) ne
    doit JAMAIS créer une fiche patient automatiquement. Seul le praticien
    crée des fiches depuis le dashboard. Le RDV public est stocké dans
    ``public_bookings`` (suffit pour l'agenda + notifications). Si la fiche
    cabinet existe déjà (patient connu via téléphone normalisé), on met
    simplement à jour ``last_booking_*`` pour avoir l'historique correct.
    """
    from backend.db import get_cabinet_client_by_phone, normalize_phone_number, upsert_cabinet_client

    phone_norm = normalize_phone_number(payload.patientPhone)
    if not phone_norm:
        return
    existing = get_cabinet_client_by_phone(int(tenant_id), phone_norm)
    if not existing:
        return
    upsert_cabinet_client(
        tenant_id,
        phone_norm,
        last_booking_motif=payload.motif.strip(),
        last_booking_start=(payload.startIso or "").strip() or None,
    )


def _public_session(
    tenant_id: int,
    payload: PublicBookingRequest,
    booking_code: Optional[str] = None,
) -> SimpleNamespace:
    """Session minimale pour réutiliser tools_booking (même logique que vocal)."""
    from backend.booking_origin import PUBLIC_PAGE

    return SimpleNamespace(
        tenant_id=int(tenant_id),
        conv_id=f"public-web-{uuid.uuid4()}",
        qualif_data=SimpleNamespace(
            name=payload.patientName.strip(),
            contact=payload.patientPhone.strip(),
            contact_type="phone",
            email=(payload.patientEmail or "").strip() or None,
            motif=payload.motif.strip(),
            pref=None,
        ),
        pending_slots=[],
        rejected_slot_starts=[],
        booking_origin=PUBLIC_PAGE,
        booking_code=(booking_code or "").strip().upper() or None,
    )


def _booking_duration_minutes(tenant_id: int) -> int:
    try:
        from backend.cabinet_profile_pg import get_booking_rules

        rules = get_booking_rules(int(tenant_id)) or {}
        return max(5, min(int(rules.get("duration_minutes") or 15), 180))
    except Exception:
        return 15


def _end_iso_from_start(start_iso: str, tenant_id: int) -> str:
    if not start_iso:
        return ""
    try:
        dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return (dt + timedelta(minutes=_booking_duration_minutes(tenant_id))).isoformat()
    except Exception:
        return ""


def _resolve_public_slot_id(tenant_id: int, payload: PublicBookingRequest) -> Tuple[Optional[int], str]:
    """Résout l'id créneau (numérique) depuis slotId, startIso ou libellé."""
    from backend import tools_booking

    src = (payload.slotSource or "sqlite").strip().lower()
    book_src = src if src in ("pg", "sqlite") else "sqlite"
    start_iso = (payload.startIso or "").strip()

    if start_iso and src in ("google", "gcal"):
        return None, book_src

    if start_iso:
        sid = tools_booking._resolve_slot_id_from_start_iso(start_iso, source=book_src, tenant_id=tenant_id)
        if sid is not None:
            return int(sid), book_src
        # startIso agenda Google : id 1..n côté front n'est pas un slot PG/SQLite.
        if src in ("sqlite", "google", "gcal"):
            return None, book_src

    try:
        return int(str(payload.slotId).strip()), book_src
    except (TypeError, ValueError):
        pass

    if start_iso:
        sid = tools_booking._resolve_slot_id_from_start_iso(start_iso, source=book_src, tenant_id=tenant_id)
        if sid is not None:
            return int(sid), book_src

    return None, book_src


def _book_google_iso_slot(
    session: SimpleNamespace,
    payload: PublicBookingRequest,
    tenant_id: int,
) -> tuple[bool, Optional[str], Optional[str]]:
    from backend import tools_booking

    start_iso = (payload.startIso or "").strip()
    if not start_iso:
        return False, "technical", None
    end_iso = (payload.endIso or "").strip() or _end_iso_from_start(start_iso, tenant_id)
    if not end_iso:
        logger.warning(
            "public_book google slot missing end_iso slug=%s start=%s",
            payload.slug,
            start_iso,
        )
        return False, "technical", None
    session.pending_slots = [
        {
            "id": payload.slotId,
            "source": "google",
            "start": start_iso,
            "start_iso": start_iso,
            "end": end_iso,
            "end_iso": end_iso,
            "label": payload.slotLabel,
            "label_vocal": payload.slotLabel,
        }
    ]
    ok, reason = tools_booking.book_slot_from_session(session, 1)
    ge = getattr(session, "google_event_id", None)
    return ok, reason, (str(ge).strip() if ge else None)


def _book_local_slot(
    session: SimpleNamespace,
    payload: PublicBookingRequest,
    slot_id: int,
    book_src: str,
) -> tuple[bool, Optional[str], Optional[str]]:
    from backend import tools_booking

    session.pending_slots = [
        {
            "id": slot_id,
            "slot_id": slot_id,
            "source": book_src,
            "start_iso": (payload.startIso or "").strip() or None,
            "label": payload.slotLabel,
            "label_vocal": payload.slotLabel,
        }
    ]
    ok, reason = tools_booking.book_slot_from_session(session, 1)
    ge = getattr(session, "google_event_id", None)
    return ok, reason, (str(ge).strip() if ge else None)


def _book_real_slot(
    tenant_id: int,
    payload: PublicBookingRequest,
    booking_code: Optional[str] = None,
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Réserve un créneau via tools_booking (Google / PG / SQLite) — même chemin que l'agent vocal.
    Returns (success, reason) avec reason in slot_taken, technical, permission, None.
    """
    session = _public_session(tenant_id, payload, booking_code=booking_code)
    src = (payload.slotSource or "sqlite").strip().lower()
    start_iso = (payload.startIso or "").strip()

    if src in ("google", "gcal") and start_iso:
        return _book_google_iso_slot(session, payload, tenant_id)

    slot_id, book_src = _resolve_public_slot_id(tenant_id, payload)
    if slot_id is not None and src in ("pg", "sqlite"):
        return _book_local_slot(session, payload, slot_id, book_src)

    # startIso sans source fiable (ex. slotSource sqlite par défaut côté front) → agenda Google.
    if start_iso:
        return _book_google_iso_slot(session, payload, tenant_id)

    if slot_id is not None:
        return _book_local_slot(session, payload, slot_id, book_src)

    logger.warning(
        "public_book unresolved slot slug=%s slotId=%r startIso=%r label=%r",
        payload.slug,
        payload.slotId,
        payload.startIso,
        payload.slotLabel[:60] if payload.slotLabel else "",
    )
    return False, "technical", None


def _format_public_slot(raw: Dict[str, Any], today: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """Transforme un slot DB (id/date/time) au format attendu par la page publique."""
    date_str = str(raw.get("date") or "")[:10]
    time_str = str(raw.get("time") or "")[:5]
    if not date_str or not time_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
    today = today or datetime.now()
    today_d = today.date()
    diff_days = (dt.date() - today_d).days
    weekday_index = dt.weekday()  # 0..6 Monday=0
    if diff_days == 0:
        day_short = "Auj."
        day_long = "aujourd'hui"
    elif diff_days == 1:
        day_short = "Dem."
        day_long = "demain"
    elif 0 < diff_days < 7:
        day_short = _FR_WEEKDAYS_SHORT[weekday_index]
        day_long = _FR_WEEKDAYS_LONG[weekday_index]
    else:
        day_short = dt.strftime("%d/%m")
        day_long = dt.strftime("%d/%m")
    label = f"{day_long} a {time_str}"
    return {
        "id": str(raw.get("id") or ""),
        "label": label,
        "day": day_short,
        "time": time_str,
        "date": date_str,
        "motifs": list(_DEFAULT_PUBLIC_MOTIFS),
        "source": str(raw.get("source") or "sqlite"),
        "startIso": raw.get("startIso") or raw.get("start_iso") or "",
        "endIso": raw.get("endIso") or raw.get("end_iso") or "",
    }


def _format_slot_from_display(
    slot: Any, today: Optional[datetime] = None, tenant_id: int = 1
) -> Optional[Dict[str, Any]]:
    """Convertit SlotDisplay (moteur vocal) → format page publique."""
    label = getattr(slot, "label", None) or (slot.get("label") if isinstance(slot, dict) else "")
    if not label:
        return None
    src = (getattr(slot, "source", None) or (slot.get("source") if isinstance(slot, dict) else "") or "sqlite").lower()
    start_iso = getattr(slot, "start", None) or (slot.get("start_iso") if isinstance(slot, dict) else "") or ""
    slot_id = getattr(slot, "slot_id", None)
    if slot_id is None and isinstance(slot, dict):
        slot_id = slot.get("slot_id") or slot.get("id")

    today = today or datetime.now()
    date_str, time_str = "", ""
    if start_iso:
        try:
            dt = datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
            if dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M")
        except Exception:
            pass
    if not date_str and src in ("sqlite", "pg") and slot_id is not None:
        return _format_public_slot({"id": slot_id, "date": "", "time": "", "source": src}, today=today)

    today_d = today.date()
    day_short, day_long = "", label
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            diff_days = (dt.date() - today_d).days
            weekday_index = dt.weekday()
            if diff_days == 0:
                day_short, day_long = "Auj.", "aujourd'hui"
            elif diff_days == 1:
                day_short, day_long = "Dem.", "demain"
            elif 0 < diff_days < 7:
                day_short = _FR_WEEKDAYS_SHORT[weekday_index]
                day_long = _FR_WEEKDAYS_LONG[weekday_index]
            else:
                day_short = dt.strftime("%d/%m")
                day_long = dt.strftime("%d/%m")
            if time_str:
                day_long = f"{day_long} a {time_str}"
        except Exception:
            pass

    end_iso = _end_iso_from_start(str(start_iso), tenant_id) if start_iso else ""

    public_id = str(slot_id) if src in ("sqlite", "pg") and slot_id is not None else str(getattr(slot, "idx", 1) or 1)
    return {
        "id": public_id,
        "label": label,
        "day": day_short or "—",
        "time": time_str or "—",
        "date": date_str,
        "motifs": list(_DEFAULT_PUBLIC_MOTIFS),
        "source": src,
        "startIso": str(start_iso),
        "endIso": end_iso,
    }


_SLOTS_HTTP_CACHE: Dict[str, tuple] = {}
_SLOTS_CACHE_TTL = 120.0
_SLOTS_FETCH_TIMEOUT = 8.0


def _slots_cache_key(slug: str, safe_count: int) -> str:
    return f"{slug}:{safe_count}"


def _get_cached_slots_response(slug: str, safe_count: int) -> Optional[Dict[str, Any]]:
    import time

    hit = _SLOTS_HTTP_CACHE.get(_slots_cache_key(slug, safe_count))
    if hit and (time.time() - hit[0]) < _SLOTS_CACHE_TTL:
        out = dict(hit[1])
        out["cached"] = True
        out["fetchedAt"] = int(hit[0])
        return out
    return None


def _store_slots_response(slug: str, safe_count: int, out: Dict[str, Any]) -> Dict[str, Any]:
    import time

    payload = {**out, "cached": False, "fetchedAt": int(time.time())}
    _SLOTS_HTTP_CACHE[_slots_cache_key(slug, safe_count)] = (payload["fetchedAt"], payload)
    return payload


def prewarm_slots_for_slug(slug: str, count: int = 12) -> Dict[str, Any]:
    """
    Force le remplissage du cache créneaux pour un slug (cron / startup).
    Retourne { ok, skipped, slug, slots, source }.
    """
    from backend.public_slug_cache import tenant_id_for_slug

    safe_count = max(1, min(int(count or 12), 24))
    slug = (slug or "").strip()
    if not slug:
        return {"ok": False, "skipped": True, "slug": slug}

    tenant_id = tenant_id_for_slug(slug)
    if not tenant_id:
        out = {"slug": slug, "slots": DEMO_SLOTS[:safe_count], "source": "demo"}
        _store_slots_response(slug, safe_count, out)
        return {"ok": True, "skipped": False, "slug": slug, "slots": len(out["slots"]), "source": "demo"}

    try:
        out = _fetch_public_slots_payload(int(tenant_id), slug, safe_count)
        if not out.get("slots"):
            out = {"slug": slug, "slots": DEMO_SLOTS[:safe_count], "source": "demo", "pending": True}
        _store_slots_response(slug, safe_count, out)
        return {
            "ok": True,
            "skipped": False,
            "slug": slug,
            "slots": len(out.get("slots") or []),
            "source": out.get("source"),
            "calendar": out.get("calendar"),
        }
    except Exception as exc:
        logger.warning("prewarm_slots_for_slug slug=%s failed: %s", slug, exc)
        return {"ok": False, "skipped": False, "slug": slug, "error": str(exc)}


def _fetch_public_slots_payload(tenant_id: int, slug: str, safe_count: int) -> Dict[str, Any]:
    """Récupère et formate les créneaux (Google/local) — exécuté dans un thread."""
    from backend import tools_booking

    session = SimpleNamespace(tenant_id=tenant_id, rejected_slot_starts=[])
    display_slots = tools_booking.get_slots_for_display(
        limit=safe_count,
        pref=None,
        session=session,
    ) or []
    now = datetime.now()
    formatted: List[Dict[str, Any]] = []
    for slot in display_slots:
        item = _format_slot_from_display(slot, today=now, tenant_id=tenant_id)
        if item:
            if item.get("startIso") and not item.get("endIso"):
                item["endIso"] = _end_iso_from_start(item["startIso"], tenant_id)
            formatted.append(item)
    if formatted:
        calendar_src = "google" if any(s.get("source") == "google" for s in formatted) else "local"
        return {
            "slug": slug,
            "slots": formatted[:safe_count],
            "source": "agenda",
            "calendar": calendar_src,
        }
    return {"slug": slug, "slots": [], "source": "agenda", "calendar": "none"}


@router.get("/slots/{slug}")
async def get_public_slots(slug: str, count: int = 6) -> Dict[str, Any]:
    import asyncio
    import time

    from backend.public_slug_cache import tenant_id_for_slug

    safe_count = max(1, min(int(count or 6), 24))
    cached = _get_cached_slots_response(slug, safe_count)
    if cached is not None:
        return cached

    tenant_id = tenant_id_for_slug(slug)
    if not tenant_id:
        out = {"slug": slug, "slots": DEMO_SLOTS[:safe_count], "source": "demo"}
        return _store_slots_response(slug, safe_count, out)

    cache_key = _slots_cache_key(slug, safe_count)
    stale_hit = _SLOTS_HTTP_CACHE.get(cache_key)

    try:
        out = await asyncio.wait_for(
            asyncio.to_thread(_fetch_public_slots_payload, int(tenant_id), slug, safe_count),
            timeout=_SLOTS_FETCH_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("public slots timeout slug=%s tenant=%s", slug, tenant_id)
        if stale_hit and stale_hit[1].get("slots"):
            stale = {**stale_hit[1], "stale": True, "cached": True, "fetchedAt": int(stale_hit[0])}
            return stale
        out = {"slug": slug, "slots": DEMO_SLOTS[:safe_count], "source": "demo", "pending": True}
    except Exception as exc:
        logger.warning("public slots failed slug=%s tenant=%s: %s", slug, tenant_id, exc)
        out = {"slug": slug, "slots": DEMO_SLOTS[:safe_count], "source": "demo"}

    return _store_slots_response(slug, safe_count, out)


@router.get("/search")
async def public_search(q: str = "") -> Dict[str, Any]:
    query = _norm(q)
    if not query:
        return {"results": DEMO_SEARCH}
    terms = [part for part in query.split() if part]
    results = []
    for item in DEMO_SEARCH:
        haystack = _norm(" ".join([item["name"], item["specialty"], item["city"]]))
        if all(term in haystack for term in terms):
            results.append(item)
    return {"results": results}


@router.post("/analytics/event")
async def public_analytics_event(
    payload: PublicAnalyticsEventRequest,
) -> Dict[str, Any]:
    from backend.public_slug_cache import tenant_id_for_slug

    tenant_id = tenant_id_for_slug(payload.slug)
    if not tenant_id:
        # Slug inconnu : on ne crée pas d'entrée orpheline pour éviter le spam.
        return {"ok": True, "ignored": True}
    _insert_public_event(payload, str(tenant_id))
    return {"ok": True}


def _is_admin_authenticated(request: Request) -> bool:
    """Auth admin = cookie session admin OU Bearer JWT session admin (même secret)."""
    try:
        from backend.routes.admin import _decode_admin_session_jwt, _get_admin_email_from_cookie
    except Exception:
        return False
    try:
        if _get_admin_email_from_cookie(request):
            return True
    except Exception:
        pass
    try:
        auth_header = request.headers.get("authorization") or ""
        if auth_header.lower().startswith("bearer "):
            tok = auth_header.split(" ", 1)[1].strip()
            if tok and _decode_admin_session_jwt(tok):
                return True
    except Exception:
        pass
    return False


def _tenant_owns_slug(request: Request, slug: str) -> bool:
    """Verifie que le tenant authentifie via cookie/Bearer client est bien
    proprietaire du slug demande.

    Le slug est rattache a un tenant_id via la table public_pages. On verifie
    que `tenant_id` du JWT correspond.
    """
    try:
        from backend.routes.tenant import require_tenant_auth
    except Exception:
        return False
    try:
        auth = require_tenant_auth(request)
    except Exception:
        return False
    if not auth:
        return False
    expected_tid = auth.get("tenant_id")
    if expected_tid is None:
        return False
    try:
        slug_tid = _resolve_tenant_id(slug)
    except Exception:
        return False
    if slug_tid is None:
        return False
    try:
        return int(slug_tid) == int(expected_tid)
    except Exception:
        return False


@router.get("/analytics/{slug}/summary")
async def public_analytics_summary(slug: str, request: Request, days: int = 30) -> Dict[str, Any]:
    """Resume des stats analytics publiques d'une page praticien.

    Audit securite 2026-05 : auth requise pour eviter l'enumeration concurrentielle.
    Acces autorise si :
      - le tenant authentifie possede ce slug, OU
      - admin authentifie (cookie/Bearer).
    """
    if not (_is_admin_authenticated(request) or _tenant_owns_slug(request, slug)):
        raise HTTPException(
            status_code=401,
            detail="Acces refuse : authentification tenant proprietaire ou admin requise.",
        )
    return _analytics_summary(slug, days)


@router.get("/sitemap.xml")
async def public_sitemap() -> Response:
    slugs = _load_public_slugs()
    now = datetime.utcnow().strftime("%Y-%m-%d")
    body = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for slug in slugs:
        body.extend(
            [
                "  <url>",
                f"    <loc>https://www.uwiapp.com/p/{slug}</loc>",
                f"    <lastmod>{now}</lastmod>",
                "    <changefreq>daily</changefreq>",
                "    <priority>0.8</priority>",
                "  </url>",
            ]
        )
    body.append("</urlset>")
    return Response("\n".join(body), media_type="application/xml")


@router.post("/book")
async def public_book(
    payload: PublicBookingRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> Dict[str, Any]:
    """Réservation patient publique. Rate-limit IP + slug pour limiter le spam de RDV."""
    from backend.rate_limit import check_sliding_window, client_ip

    ip = client_ip(request)
    slug = (payload.slug or "").strip().lower() or "unknown"
    try:
        check_sliding_window(f"public_book_ip:{ip}", limit=5, window_sec=60)
        check_sliding_window(f"public_book_ip:{ip}", limit=30, window_sec=3600)
        check_sliding_window(f"public_book_slug:{slug}", limit=20, window_sec=60)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    payload = _sanitize_public_booking_payload(payload)
    practitioner = _try_fetch_practitioner(payload.slug) or _demo_practitioner(payload.slug)
    tenant_id_raw = practitioner.get("tenantId")
    tenant_id: Optional[int] = None
    if tenant_id_raw is not None:
        try:
            tenant_id = int(tenant_id_raw)
        except (TypeError, ValueError):
            tenant_id = None

    booking_status = "pending"
    booking_reason: Optional[str] = None
    booking_code: Optional[str] = None
    try:
        from backend.booking_code import create_unique_booking_code_for_tenant

        booking_code = create_unique_booking_code_for_tenant(tenant_id)
    except Exception as exc:
        logger.warning("public_book booking_code generation skipped tenant=%s: %s", tenant_id, exc)

    google_event_id: Optional[str] = None
    if tenant_id:
        ok, booking_reason, google_event_id = _book_real_slot(tenant_id, payload, booking_code=booking_code)
        if ok:
            booking_status = "confirmed"
        elif booking_reason == "slot_taken":
            raise HTTPException(
                status_code=409,
                detail="Ce créneau n'est plus disponible. Choisissez un autre horaire.",
            )
        else:
            logger.warning(
                "public_book real booking failed slug=%s tenant=%s reason=%s",
                payload.slug,
                tenant_id,
                booking_reason,
            )
            raise HTTPException(
                status_code=502,
                detail="Impossible de confirmer ce creneau. Choisissez un autre horaire ou demandez a etre rappele par le cabinet.",
            )

    booking_record = _insert_booking(
        payload,
        str(tenant_id) if tenant_id else tenant_id_raw,
        status=booking_status,
        booking_code=booking_code,
        google_event_id=google_event_id,
    )
    confirmation_id = booking_record.get("id") or ""
    if not booking_code:
        booking_code = booking_record.get("booking_code") or ""

    # Décision produit stricte: aucune création / mise à jour automatique de fiche
    # patient depuis la prise de RDV publique. La reconnaissance "patient connu"
    # reste en lecture seule via /api/public/praticiens/{slug}/patient-hint.

    background_tasks.add_task(
        _dispatch_booking_notifications,
        practitioner,
        payload,
        booking_status,
        confirmation_id,
        booking_code,
    )

    logger.info(
        "public_booking_created",
        extra={
            "confirmation_id": confirmation_id,
            "booking_code": booking_code,
            "slug": payload.slug,
            "slot_id": payload.slotId,
            "source": payload.source,
            "status": booking_status,
            "notifications": "background",
            "created_at": datetime.utcnow().isoformat(),
        },
    )
    background_tasks.add_task(
        _track_booking_confirmed_event,
        payload,
        tenant_id,
        confirmation_id,
        booking_status,
    )
    followup = _build_whatsapp_followup(practitioner, payload)
    from backend.booking_code import format_booking_code

    return {
        "confirmationId": confirmation_id,
        "bookingCode": format_booking_code(booking_code),
        "slotLabel": payload.slotLabel,
        "status": booking_status,
        "confirmed": booking_status == "confirmed",
        "bookingReason": booking_reason,
        "patientSmsSent": None,
        "cabinetSmsSent": None,
        "cabinetEmailSent": None,
        "notificationsPending": True,
        "followup": followup,
    }
