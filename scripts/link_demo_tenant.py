#!/usr/bin/env python3
"""
Lie le cabinet démo UWi :
- Numéro 09 39 24 05 75 (+33939240575) → tenant
- Email affiché demo@uwi.app, connexion Google henigoutal@gmail.com
- Page publique /p/cabinet-demo-uwi (SEO + créneaux + chat Clara)

Usage (racine du projet) :
  python3 scripts/link_demo_tenant.py
  python3 scripts/link_demo_tenant.py --prod   # DATABASE_URL ou DATABASE_PUBLIC_URL

Variables utiles :
  DEMO_TENANT_ID (défaut 1 en local, 2 en prod)
  DEMO_EMAIL (défaut demo@uwi.app)
  DEMO_OWNER_GOOGLE_EMAIL (défaut henigoutal@gmail.com)
  VAPI_ASSISTANT_ID
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEMO_DID = "+33939240575"
DEMO_PHONE_DISPLAY = "09 39 24 05 75"
DEFAULT_VAPI_ASSISTANT_ID = "78dd0e14-337e-40ab-96d9-7dbbe92cdf95"
DEFAULT_EMAIL = "demo@uwi.app"
PUBLIC_SLUG = "cabinet-demo-uwi"
OWNER_GOOGLE_EMAIL = os.getenv("DEMO_OWNER_GOOGLE_EMAIL", "henigoutal@gmail.com").strip().lower()

OPENING_HOURS = [
    {"day": "monday", "is_open": True, "morning_start": "08:30", "morning_end": "12:30", "afternoon_start": "14:00", "afternoon_end": "18:30"},
    {"day": "tuesday", "is_open": True, "morning_start": "08:30", "morning_end": "12:30", "afternoon_start": "14:00", "afternoon_end": "18:30"},
    {"day": "wednesday", "is_open": True, "morning_start": "08:30", "morning_end": "12:30", "afternoon_start": "14:00", "afternoon_end": "18:30"},
    {"day": "thursday", "is_open": True, "morning_start": "08:30", "morning_end": "12:30", "afternoon_start": "14:00", "afternoon_end": "18:30"},
    {"day": "friday", "is_open": True, "morning_start": "08:30", "morning_end": "12:30", "afternoon_start": "14:00", "afternoon_end": "17:30"},
    {"day": "saturday", "is_open": False},
    {"day": "sunday", "is_open": False},
]


def _vapi_id() -> str:
    return os.getenv("VAPI_ASSISTANT_ID", DEFAULT_VAPI_ASSISTANT_ID).strip()


def _public_page_block() -> dict:
    return {
        "name": "Cabinet Démo UWi",
        "specialty": "Médecine générale",
        "city": "Paris",
        "verified": True,
        "rating": 4.9,
        "reviewCount": 142,
        "reviewsVerified": True,
        "phone": DEMO_PHONE_DISPLAY,
        "phoneTel": DEMO_DID,
        "address": {
            "street": "12 rue de la Démo",
            "postalCode": "75002",
            "city": "Paris",
            "country": "FR",
        },
        "access": "Métro Grands Boulevards — ligne 8, 9",
        "parking": "Parking Saemes Grands Boulevards",
        "languages": ["Français", "Anglais"],
        "fee": "Secteur 1 — Tarifs conventionnés",
        "carteVitale": True,
        "pmr": True,
        "voiceEnabled": True,
        "vapiAssistantId": _vapi_id(),
        "newPatients": "Oui, sur disponibilité",
        "documents": "Carte Vitale, pièce d'identité, ordonnances et examens récents.",
        "whatsappEnabled": False,
        "whatsappUrl": "",
        "canonicalUrl": f"https://www.uwiapp.com/p/{PUBLIC_SLUG}",
    }


def _merge_params(existing: dict) -> dict:
    params = dict(existing or {})
    vapi_id = _vapi_id()
    public_page = dict(params.get("public_page") or {})
    public_page.update(_public_page_block())

    params.update(
        {
            "vapi_assistant_id": vapi_id,
            "assistant_name": params.get("assistant_name") or "Clara",
            "phone_number": DEMO_DID,
            "callback_phone": DEMO_DID,
            "contact_email": params.get("contact_email") or DEFAULT_EMAIL,
            "business_name": "Cabinet Démo UWi",
            "practitioner_name": "Dr Démo UWi",
            "specialty_label": params.get("specialty_label") or "Médecine générale",
            "profession": params.get("profession") or "medecin_generaliste",
            "city": params.get("city") or "Paris",
            "postal_code": params.get("postal_code") or "75002",
            "address_line1": params.get("address_line1") or "12 rue de la Démo",
            "public_slug": PUBLIC_SLUG,
            "public_page": public_page,
            "client_onboarding_completed": "true",
            "accepts_new_patients": True,
            "languages": params.get("languages") or ["Français", "Anglais"],
            "access_instructions": params.get("access_instructions") or public_page["access"],
            "parking_info": params.get("parking_info") or public_page["parking"],
            "pmr_access": True,
            "payment_methods": params.get("payment_methods") or public_page["fee"],
        }
    )
    calendar_id = (
        (params.get("calendar_id") or "").strip()
        or os.getenv("GOOGLE_CALENDAR_ID", "").strip()
    )
    if calendar_id:
        params["calendar_provider"] = "google"
        params["calendar_id"] = calendar_id
    return params


def _profile_payload() -> dict:
    return {
        "practitioner_name": "Dr Démo UWi",
        "cabinet_name": "Cabinet Démo UWi",
        "specialty": "Médecine générale",
        "phone": DEMO_DID,
        "email": DEFAULT_EMAIL,
        "address_line": "12 rue de la Démo",
        "postal_code": "75002",
        "city": "Paris",
        "website_url": "https://www.uwiapp.com",
        "languages": ["Français", "Anglais"],
        "accepts_new_patients": True,
        "practitioner_photo_url": "",
        "public_slug": PUBLIC_SLUG,
    }


def link_sqlite(tenant_id: int) -> None:
    db_path = ROOT / "agent.db"
    if not db_path.exists():
        raise SystemExit(f"Base SQLite introuvable : {db_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO tenants (tenant_id, name) VALUES (?, ?)", (tenant_id, "Cabinet Démo UWi"))
    cur.execute("UPDATE tenants SET name = ? WHERE tenant_id = ?", ("Cabinet Démo UWi", tenant_id))

    row = cur.execute("SELECT params_json FROM tenant_config WHERE tenant_id = ?", (tenant_id,)).fetchone()
    existing = {}
    if row and row[0]:
        try:
            existing = json.loads(row[0])
        except Exception:
            existing = {}
    params_json = json.dumps(_merge_params(existing), ensure_ascii=False)

    if cur.execute("SELECT 1 FROM tenant_config WHERE tenant_id = ?", (tenant_id,)).fetchone():
        cur.execute("UPDATE tenant_config SET params_json = ? WHERE tenant_id = ?", (params_json, tenant_id))
    else:
        cur.execute(
            "INSERT INTO tenant_config (tenant_id, flags_json, params_json) VALUES (?, '{}', ?)",
            (tenant_id, params_json),
        )

    cur.execute(
        """
        INSERT INTO tenant_routing (channel, did_key, tenant_id, created_at)
        VALUES ('vocal', ?, ?, datetime('now'))
        ON CONFLICT(channel, did_key) DO UPDATE SET tenant_id = excluded.tenant_id
        """,
        (DEMO_DID, tenant_id),
    )
    cur.execute(
        "DELETE FROM tenant_routing WHERE tenant_id = ? AND did_key != ?",
        (tenant_id, DEMO_DID),
    )
    conn.commit()
    conn.close()
    print(f"[sqlite] tenant_id={tenant_id} params + route {DEMO_DID} OK ({db_path})")


def _link_owner_users_pg(cur, tenant_id: int) -> None:
    """Associe henigoutal@gmail.com (Google) et demo@uwi.app au tenant démo."""
    demo_email = os.getenv("DEMO_EMAIL", DEFAULT_EMAIL).strip().lower()
    for email in (OWNER_GOOGLE_EMAIL, demo_email):
        if not email:
            continue
        cur.execute(
            """
            UPDATE tenant_users
            SET tenant_id = %s, role = COALESCE(role, 'owner')
            WHERE lower(email) = lower(%s)
               OR lower(coalesce(google_email, '')) = lower(%s)
            """,
            (tenant_id, email, email),
        )
        if cur.rowcount:
            print(f"[postgres] compte {email} → tenant_id={tenant_id} ({cur.rowcount} ligne(s))")


def _sync_profile_pg(tenant_id: int) -> None:
    from backend.cabinet_profile_pg import replace_opening_hours, upsert_profile

    if upsert_profile(tenant_id, _profile_payload()):
        print(f"[postgres] tenant_profiles tenant_id={tenant_id} OK (slug={PUBLIC_SLUG})")
    if replace_opening_hours(tenant_id, OPENING_HOURS):
        print(f"[postgres] horaires tenant_id={tenant_id} OK")


def link_postgres(tenant_id: int, create_demo_user: bool) -> None:
    url = (os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise SystemExit("DATABASE_URL ou DATABASE_PUBLIC_URL requis pour --prod")

    import psycopg2

    conn = psycopg2.connect(url)
    cur = conn.cursor()

    cur.execute("SELECT params_json FROM tenant_config WHERE tenant_id = %s", (tenant_id,))
    row = cur.fetchone()
    existing = row[0] if row and row[0] else {}
    if isinstance(existing, str):
        existing = json.loads(existing)
    params = _merge_params(existing if isinstance(existing, dict) else {})

    cur.execute(
        "UPDATE tenant_config SET params_json = %s::jsonb, updated_at = now() WHERE tenant_id = %s",
        (json.dumps(params, ensure_ascii=False), tenant_id),
    )
    if cur.rowcount == 0:
        cur.execute(
            "INSERT INTO tenant_config (tenant_id, flags_json, params_json) VALUES (%s, '{}'::jsonb, %s::jsonb)",
            (tenant_id, json.dumps(params, ensure_ascii=False)),
        )

    cur.execute(
        """
        INSERT INTO tenant_routing (channel, key, tenant_id, is_active, updated_at)
        VALUES ('vocal', %s, %s, TRUE, now())
        ON CONFLICT (channel, key) DO UPDATE
        SET tenant_id = EXCLUDED.tenant_id, is_active = TRUE, updated_at = now()
        """,
        (DEMO_DID, tenant_id),
    )

    if create_demo_user:
        import bcrypt

        email = os.getenv("DEMO_EMAIL", DEFAULT_EMAIL).strip().lower()
        password = os.getenv("DEMO_PASSWORD", "demo1234")
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cur.execute(
            """
            INSERT INTO tenant_users (tenant_id, email, role, password_hash, email_verified)
            VALUES (%s, %s, 'owner', %s, TRUE)
            ON CONFLICT (email) DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                role = EXCLUDED.role,
                password_hash = EXCLUDED.password_hash
            """,
            (tenant_id, email, password_hash),
        )
        print(f"[postgres] utilisateur {email} → tenant_id={tenant_id}")

    _link_owner_users_pg(cur, tenant_id)

    conn.commit()
    conn.close()
    print(f"[postgres] tenant_id={tenant_id} params + route {DEMO_DID} OK")

    os.environ.setdefault("DATABASE_URL", url)
    _sync_profile_pg(tenant_id)


def _print_public_urls() -> None:
    print("")
    print("Page publique démo :")
    print(f"  Local  : http://localhost:5173/p/{PUBLIC_SLUG}")
    print(f"  Prod   : https://www.uwiapp.com/p/{PUBLIC_SLUG}")
    print(f"  API    : GET /api/public/practitioner/{PUBLIC_SLUG}")
    print(f"  Chat   : POST /chat/public/{PUBLIC_SLUG}")
    print(f"  Vocal  : {DEMO_PHONE_DISPLAY} ({DEMO_DID})")
    print(f"  Login  : {OWNER_GOOGLE_EMAIL} (Google) — profil affiché {DEFAULT_EMAIL}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prod", action="store_true", help="Met à jour Postgres (prod/staging)")
    parser.add_argument("--tenant-id", type=int, default=None)
    parser.add_argument("--create-demo-user", action="store_true", help="Crée/met à jour demo@uwi.app (prod)")
    args = parser.parse_args()

    default_tid = 2 if args.prod else 1
    tenant_id = args.tenant_id or int(os.getenv("DEMO_TENANT_ID") or os.getenv("TEST_TENANT_ID") or default_tid)

    if args.prod:
        link_postgres(tenant_id, create_demo_user=args.create_demo_user)
    else:
        link_sqlite(tenant_id)

    _print_public_urls()
    print("Terminé. Redémarrez uvicorn + npm run dev si besoin.")


if __name__ == "__main__":
    main()
