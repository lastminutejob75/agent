#!/usr/bin/env python3
"""
Configure un cabinet client (prod ou local) après création admin.

Usage:
  python3 scripts/link_client_tenant.py --tenant-id 3 \\
    --did +33123456789 \\
    --slug dr-dupont-paris \\
    --cabinet-name "Dr Dupont" \\
    --contact-email contact@dupont.fr \\
    --vapi-assistant-id UUID \\
    --calendar-id CALENDAR_ID@group.calendar.google.com

  python3 scripts/link_client_tenant.py --prod --tenant-id 3 ... (charge .env.railway)

Ne pas utiliser pour le cabinet démo (+33939240575) : voir link_demo_tenant.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_OPENING_HOURS = [
    {"day": "monday", "is_open": True, "morning_start": "09:00", "morning_end": "12:30", "afternoon_start": "14:00", "afternoon_end": "18:00"},
    {"day": "tuesday", "is_open": True, "morning_start": "09:00", "morning_end": "12:30", "afternoon_start": "14:00", "afternoon_end": "18:00"},
    {"day": "wednesday", "is_open": True, "morning_start": "09:00", "morning_end": "12:30", "afternoon_start": "14:00", "afternoon_end": "18:00"},
    {"day": "thursday", "is_open": True, "morning_start": "09:00", "morning_end": "12:30", "afternoon_start": "14:00", "afternoon_end": "18:00"},
    {"day": "friday", "is_open": True, "morning_start": "09:00", "morning_end": "12:30", "afternoon_start": "14:00", "afternoon_end": "17:00"},
    {"day": "saturday", "is_open": False},
    {"day": "sunday", "is_open": False},
]


def _load_env_railway() -> None:
    env_path = ROOT / ".env.railway"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()
    pub = (os.environ.get("DATABASE_PUBLIC_URL") or "").strip()
    if pub:
        os.environ["DATABASE_URL"] = pub
        os.environ["PG_TENANTS_URL"] = pub


def _normalize_did(raw: str) -> str:
    digits = "".join(c for c in (raw or "") if c.isdigit() or c == "+")
    if digits.startswith("+"):
        return digits
    if digits.startswith("0") and len(digits) == 10:
        return "+33" + digits[1:]
    return raw.strip()


def _public_page_block(args: argparse.Namespace) -> dict:
    did = _normalize_did(args.did)
    display_phone = args.phone_display or did
    return {
        "name": args.cabinet_name,
        "specialty": args.specialty or "Médecine générale",
        "city": args.city or "",
        "verified": True,
        "phone": display_phone,
        "phoneTel": did,
        "address": {
            "street": args.address_line or "",
            "postalCode": args.postal_code or "",
            "city": args.city or "",
            "country": "FR",
        },
        "voiceEnabled": bool(args.vapi_assistant_id),
        "vapiAssistantId": args.vapi_assistant_id or "",
        "canonicalUrl": f"https://www.uwiapp.com/p/{args.slug}",
    }


def _merge_params(existing: dict, args: argparse.Namespace) -> dict:
    params = dict(existing or {})
    did = _normalize_did(args.did)
    public_page = dict(params.get("public_page") or {})
    public_page.update(_public_page_block(args))

    params.update(
        {
            "business_name": args.cabinet_name,
            "practitioner_name": args.practitioner_name or args.cabinet_name,
            "contact_email": args.contact_email,
            "phone_number": did,
            "public_slug": args.slug,
            "public_page": public_page,
            "specialty_label": args.specialty or params.get("specialty_label") or "Médecine générale",
            "city": args.city or params.get("city") or "",
            "postal_code": args.postal_code or params.get("postal_code") or "",
            "address_line1": args.address_line or params.get("address_line1") or "",
        }
    )
    if args.vapi_assistant_id:
        params["vapi_assistant_id"] = args.vapi_assistant_id.strip()
    if args.calendar_id:
        params["calendar_provider"] = "google"
        params["calendar_id"] = args.calendar_id.strip()
    if args.assistant_name:
        params["assistant_name"] = args.assistant_name.strip()
    return params


def link_postgres(args: argparse.Namespace) -> None:
    url = (os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise SystemExit("DATABASE_URL ou DATABASE_PUBLIC_URL requis pour --prod")

    import psycopg2

    did = _normalize_did(args.did)
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute("SELECT params_json FROM tenant_config WHERE tenant_id = %s", (args.tenant_id,))
    row = cur.fetchone()
    existing = row[0] if row and row[0] else {}
    if isinstance(existing, str):
        existing = json.loads(existing)
    params = _merge_params(existing if isinstance(existing, dict) else {}, args)

    cur.execute(
        "UPDATE tenant_config SET params_json = %s::jsonb, updated_at = now() WHERE tenant_id = %s",
        (json.dumps(params, ensure_ascii=False), args.tenant_id),
    )
    if cur.rowcount == 0:
        cur.execute(
            "INSERT INTO tenant_config (tenant_id, flags_json, params_json) VALUES (%s, '{}'::jsonb, %s::jsonb)",
            (args.tenant_id, json.dumps(params, ensure_ascii=False)),
        )

    cur.execute(
        """
        INSERT INTO tenant_routing (channel, key, tenant_id, is_active, updated_at)
        VALUES ('vocal', %s, %s, TRUE, now())
        ON CONFLICT (channel, key) DO UPDATE
        SET tenant_id = EXCLUDED.tenant_id, is_active = TRUE, updated_at = now()
        """,
        (did, args.tenant_id),
    )
    conn.commit()
    conn.close()
    print(f"[postgres] tenant_id={args.tenant_id} params + route {did} OK")

    os.environ.setdefault("DATABASE_URL", url)
    from backend.cabinet_profile_pg import replace_opening_hours, upsert_profile

    profile = {
        "practitioner_name": args.practitioner_name or args.cabinet_name,
        "cabinet_name": args.cabinet_name,
        "specialty": args.specialty or "Médecine générale",
        "phone": did,
        "email": args.contact_email,
        "address_line": args.address_line or "",
        "postal_code": args.postal_code or "",
        "city": args.city or "",
        "public_slug": args.slug,
    }
    if upsert_profile(args.tenant_id, profile):
        print(f"[postgres] tenant_profiles slug={args.slug} OK")
    if replace_opening_hours(args.tenant_id, DEFAULT_OPENING_HOURS):
        print("[postgres] horaires OK")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lie un cabinet client (routing + page publique + profil)")
    parser.add_argument("--prod", action="store_true")
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--did", required=True, help="Numéro vocal E.164 ex. +33123456789")
    parser.add_argument("--slug", required=True, help="Slug page publique ex. dr-dupont-paris")
    parser.add_argument("--cabinet-name", required=True)
    parser.add_argument("--contact-email", required=True)
    parser.add_argument("--vapi-assistant-id", default=os.getenv("VAPI_ASSISTANT_ID", "").strip())
    parser.add_argument("--calendar-id", default=os.getenv("GOOGLE_CALENDAR_ID", "").strip())
    parser.add_argument("--practitioner-name", default="")
    parser.add_argument("--assistant-name", default="Clara")
    parser.add_argument("--specialty", default="Médecine générale")
    parser.add_argument("--city", default="")
    parser.add_argument("--postal-code", default="")
    parser.add_argument("--address-line", default="")
    parser.add_argument("--phone-display", default="", help="Affichage FR ex. 01 23 45 67 89")
    args = parser.parse_args()

    if args.prod:
        _load_env_railway()

    link_postgres(args)
    print("")
    print(f"Page publique : https://www.uwiapp.com/p/{args.slug}")
    print(f"API praticien : GET /api/public/practitioner/{args.slug}")
    print(f"Numéro vocal  : {_normalize_did(args.did)} → tenant_id={args.tenant_id}")
    print("Étapes restantes : client connecte Google Calendar dans /app/agenda, puis test appel + RDV public.")


if __name__ == "__main__":
    main()
