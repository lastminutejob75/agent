#!/usr/bin/env python3
"""
Backfill des tables normalisées "Mon cabinet" depuis tenant_config.params_json.

Usage:
  python scripts/backfill_cabinet_profile.py
  python scripts/backfill_cabinet_profile.py --dry-run
  python scripts/backfill_cabinet_profile.py --tenant-id 12
  railway run python scripts/backfill_cabinet_profile.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from uuid import NAMESPACE_DNS, uuid5

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
if ENV.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(ENV)
    except ImportError:
        pass

DAY_KEYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def slugify(value: str) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return ""
    raw = re.sub(r"[^\w\s-]", "", raw, flags=re.UNICODE)
    return re.sub(r"[-\s]+", "-", raw).strip("-")


def parse_json(value, default):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        val = value.strip()
        if not val:
            return default
        try:
            out = json.loads(val)
            return out
        except Exception:
            return default
    return default


def parse_languages(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        parsed = parse_json(value, None)
        if isinstance(parsed, list):
            return [str(v).strip() for v in parsed if str(v).strip()]
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def is_truthy(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "oui"}


def opening_hours_from_params(params):
    raw = parse_json(params.get("opening_hours_json"), {})
    opening = raw.get("opening_hours") if isinstance(raw, dict) else None
    if isinstance(opening, list) and opening:
        by_day = {str(row.get("day") or "").strip().lower(): row for row in opening if isinstance(row, dict)}
        rows = []
        for day in DAY_KEYS:
            row = by_day.get(day, {})
            rows.append(
                {
                    "day": day,
                    "is_open": is_truthy(row.get("is_open")),
                    "morning_start": str(row.get("morning_start") or ""),
                    "morning_end": str(row.get("morning_end") or ""),
                    "afternoon_start": str(row.get("afternoon_start") or ""),
                    "afternoon_end": str(row.get("afternoon_end") or ""),
                }
            )
        return rows

    booking_days = params.get("booking_days")
    if isinstance(booking_days, str):
        booking_days = parse_json(booking_days, [])
    if not isinstance(booking_days, list):
        booking_days = [0, 1, 2, 3, 4]
    day_index = {int(v) for v in booking_days if str(v).strip().isdigit()}
    start = int(params.get("booking_start_hour") or 9)
    end = int(params.get("booking_end_hour") or 18)
    rows = []
    for idx, day in enumerate(DAY_KEYS):
        open_day = idx in day_index
        rows.append(
            {
                "day": day,
                "is_open": open_day,
                "morning_start": f"{start:02d}:00" if open_day else "",
                "morning_end": "12:30" if open_day else "",
                "afternoon_start": "14:00" if open_day else "",
                "afternoon_end": f"{end:02d}:00" if open_day else "",
            }
        )
    return rows


def normalize_reasons(value, tenant_id):
    reasons = parse_json(value, [])
    if not isinstance(reasons, list):
        return []
    out = []
    for row in reasons:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip()
        if not label:
            continue
        rid = str(row.get("id") or uuid5(NAMESPACE_DNS, f"uwi-tenant-{tenant_id}-reason-{label.lower()}"))
        out.append(
            {
                "id": rid,
                "label": label,
                "duration_minutes": int(row.get("duration_minutes") or 30),
                "description": str(row.get("description") or "").strip(),
                "enabled": is_truthy(row.get("enabled", True)),
                "allowed_for_new_patients": is_truthy(row.get("allowed_for_new_patients", True)),
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill tables Mon cabinet depuis tenant_config.params_json")
    parser.add_argument(
        "--pg-url",
        default=os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL"),
        help="Postgres URL (DATABASE_URL par défaut)",
    )
    parser.add_argument("--tenant-id", type=int, default=0, help="Limiter à un tenant_id")
    parser.add_argument("--dry-run", action="store_true", help="Affiche uniquement le plan d'action")
    args = parser.parse_args()

    if not args.pg_url:
        print("Error: --pg-url ou DATABASE_URL/PG_TENANTS_URL requis")
        return 1

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("Error: psycopg requis. pip install psycopg[binary]")
        return 1

    where = "WHERE t.tenant_id = %s" if args.tenant_id else ""
    q_params = (args.tenant_id,) if args.tenant_id else tuple()

    try:
        with psycopg.connect(args.pg_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT t.tenant_id, t.name, tc.params_json
                    FROM tenants t
                    LEFT JOIN tenant_config tc ON tc.tenant_id = t.tenant_id
                    {where}
                    ORDER BY t.tenant_id
                    """,
                    q_params,
                )
                tenants = cur.fetchall() or []

            print(f"Tenants trouvés: {len(tenants)}")
            if not tenants:
                return 0

            profiles = 0
            openings = 0
            availability = 0
            rules = 0
            reasons = 0
            assistant = 0

            for row in tenants:
                tenant_id = int(row["tenant_id"])
                name = str(row.get("name") or f"Tenant #{tenant_id}")
                params = parse_json(row.get("params_json"), {})
                if not isinstance(params, dict):
                    params = {}

                profile_payload = {
                    "practitioner_name": params.get("practitioner_name") or params.get("business_name") or name,
                    "cabinet_name": params.get("business_name") or name,
                    "specialty": params.get("specialty_label") or "",
                    "phone": params.get("phone_number") or "",
                    "email": params.get("contact_email") or "",
                    "address_line": params.get("address_line1") or "",
                    "postal_code": params.get("postal_code") or "",
                    "city": params.get("city") or "",
                    "website_url": params.get("website_url") or "",
                    "languages": parse_languages(params.get("languages")),
                    "accepts_new_patients": is_truthy(params.get("accepts_new_patients", True)),
                    "practitioner_photo_url": params.get("practitioner_photo_url") or "",
                    "public_slug": params.get("public_slug") or slugify(params.get("business_name") or name),
                }

                opening = opening_hours_from_params(params)
                availability_payload = {
                    "temporary_closure_enabled": is_truthy(params.get("temporary_closure_enabled")),
                    "temporary_closure_start": params.get("temporary_closure_start") or "",
                    "temporary_closure_end": params.get("temporary_closure_end") or "",
                    "temporary_closure_message": params.get("temporary_closure_message") or "",
                }
                booking_payload = {
                    "default_appointment_duration_minutes": int(params.get("default_appointment_duration_minutes") or params.get("booking_duration_minutes") or 30),
                    "minimum_booking_notice_hours": int(params.get("minimum_booking_notice_hours") or 24),
                    "accepts_new_patients": is_truthy(params.get("accepts_new_patients", True)),
                    "appointment_reschedule_allowed": is_truthy(params.get("appointment_reschedule_allowed", True)),
                    "appointment_reschedule_notice_hours": int(params.get("appointment_reschedule_notice_hours") or 24),
                    "appointment_cancel_allowed": is_truthy(params.get("appointment_cancel_allowed", True)),
                    "appointment_cancel_notice_hours": int(params.get("appointment_cancel_notice_hours") or 24),
                    "emergency_instruction": params.get("emergency_instruction") or "",
                    "new_patient_instruction": params.get("new_patient_instruction") or "",
                    "booking_notes": params.get("booking_notes") or "",
                }
                assistant_payload = {
                    "assistant_name": params.get("assistant_name") or "Clara",
                    "welcome_message": params.get("welcome_message") or "",
                    "documents_to_bring": params.get("documents_to_bring") or "",
                    "access_instructions": params.get("access_instructions") or "",
                    "payment_methods": params.get("payment_methods") or "",
                    "parking_info": params.get("parking_info") or "",
                    "pmr_access": params.get("pmr_access") or "",
                    "sensitive_medical_instruction": params.get("sensitive_medical_instruction") or "Clara ne donne jamais d'avis medical.",
                    "escalation_instruction": params.get("escalation_instruction") or "",
                    "human_handoff_instruction": params.get("human_handoff_instruction") or "",
                    "faq_items": parse_json(params.get("faq_items_json"), []),
                }
                reasons_payload = normalize_reasons(params.get("appointment_reasons_json"), tenant_id)

                print(f"- tenant_id={tenant_id} name={name} reasons={len(reasons_payload)}")

                if args.dry_run:
                    continue

                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO tenant_profiles (
                            tenant_id, practitioner_name, cabinet_name, specialty, phone, email, address_line, postal_code, city,
                            website_url, languages_json, accepts_new_patients, practitioner_photo_url, public_slug, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, now())
                        ON CONFLICT (tenant_id) DO UPDATE SET
                            practitioner_name = EXCLUDED.practitioner_name,
                            cabinet_name = EXCLUDED.cabinet_name,
                            specialty = EXCLUDED.specialty,
                            phone = EXCLUDED.phone,
                            email = EXCLUDED.email,
                            address_line = EXCLUDED.address_line,
                            postal_code = EXCLUDED.postal_code,
                            city = EXCLUDED.city,
                            website_url = EXCLUDED.website_url,
                            languages_json = EXCLUDED.languages_json,
                            accepts_new_patients = EXCLUDED.accepts_new_patients,
                            practitioner_photo_url = EXCLUDED.practitioner_photo_url,
                            public_slug = EXCLUDED.public_slug,
                            updated_at = now()
                        """,
                        (
                            tenant_id,
                            profile_payload["practitioner_name"],
                            profile_payload["cabinet_name"],
                            profile_payload["specialty"],
                            profile_payload["phone"],
                            profile_payload["email"],
                            profile_payload["address_line"],
                            profile_payload["postal_code"],
                            profile_payload["city"],
                            profile_payload["website_url"],
                            json.dumps(profile_payload["languages"]),
                            profile_payload["accepts_new_patients"],
                            profile_payload["practitioner_photo_url"],
                            profile_payload["public_slug"],
                        ),
                    )
                    profiles += 1

                    cur.execute("DELETE FROM tenant_opening_hours WHERE tenant_id = %s", (tenant_id,))
                    for item in opening:
                        cur.execute(
                            """
                            INSERT INTO tenant_opening_hours (
                                tenant_id, day_of_week, is_open, morning_start, morning_end, afternoon_start, afternoon_end, updated_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                            """,
                            (
                                tenant_id,
                                item["day"],
                                item["is_open"],
                                item["morning_start"],
                                item["morning_end"],
                                item["afternoon_start"],
                                item["afternoon_end"],
                            ),
                        )
                    openings += len(opening)

                    cur.execute(
                        """
                        INSERT INTO tenant_availability_settings (
                            tenant_id, temporary_closure_enabled, temporary_closure_start, temporary_closure_end, temporary_closure_message, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, now())
                        ON CONFLICT (tenant_id) DO UPDATE SET
                            temporary_closure_enabled = EXCLUDED.temporary_closure_enabled,
                            temporary_closure_start = EXCLUDED.temporary_closure_start,
                            temporary_closure_end = EXCLUDED.temporary_closure_end,
                            temporary_closure_message = EXCLUDED.temporary_closure_message,
                            updated_at = now()
                        """,
                        (
                            tenant_id,
                            availability_payload["temporary_closure_enabled"],
                            availability_payload["temporary_closure_start"],
                            availability_payload["temporary_closure_end"],
                            availability_payload["temporary_closure_message"],
                        ),
                    )
                    availability += 1

                    cur.execute(
                        """
                        INSERT INTO tenant_booking_rules (
                            tenant_id, default_appointment_duration_minutes, minimum_booking_notice_hours, accepts_new_patients,
                            appointment_reschedule_allowed, appointment_reschedule_notice_hours,
                            appointment_cancel_allowed, appointment_cancel_notice_hours,
                            emergency_instruction, new_patient_instruction, booking_notes, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                        ON CONFLICT (tenant_id) DO UPDATE SET
                            default_appointment_duration_minutes = EXCLUDED.default_appointment_duration_minutes,
                            minimum_booking_notice_hours = EXCLUDED.minimum_booking_notice_hours,
                            accepts_new_patients = EXCLUDED.accepts_new_patients,
                            appointment_reschedule_allowed = EXCLUDED.appointment_reschedule_allowed,
                            appointment_reschedule_notice_hours = EXCLUDED.appointment_reschedule_notice_hours,
                            appointment_cancel_allowed = EXCLUDED.appointment_cancel_allowed,
                            appointment_cancel_notice_hours = EXCLUDED.appointment_cancel_notice_hours,
                            emergency_instruction = EXCLUDED.emergency_instruction,
                            new_patient_instruction = EXCLUDED.new_patient_instruction,
                            booking_notes = EXCLUDED.booking_notes,
                            updated_at = now()
                        """,
                        (
                            tenant_id,
                            booking_payload["default_appointment_duration_minutes"],
                            booking_payload["minimum_booking_notice_hours"],
                            booking_payload["accepts_new_patients"],
                            booking_payload["appointment_reschedule_allowed"],
                            booking_payload["appointment_reschedule_notice_hours"],
                            booking_payload["appointment_cancel_allowed"],
                            booking_payload["appointment_cancel_notice_hours"],
                            booking_payload["emergency_instruction"],
                            booking_payload["new_patient_instruction"],
                            booking_payload["booking_notes"],
                        ),
                    )
                    rules += 1

                    cur.execute(
                        """
                        INSERT INTO tenant_assistant_settings (
                            tenant_id, assistant_name, welcome_message, documents_to_bring, access_instructions,
                            payment_methods, parking_info, pmr_access, sensitive_medical_instruction,
                            escalation_instruction, human_handoff_instruction, faq_items_json, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, now())
                        ON CONFLICT (tenant_id) DO UPDATE SET
                            assistant_name = EXCLUDED.assistant_name,
                            welcome_message = EXCLUDED.welcome_message,
                            documents_to_bring = EXCLUDED.documents_to_bring,
                            access_instructions = EXCLUDED.access_instructions,
                            payment_methods = EXCLUDED.payment_methods,
                            parking_info = EXCLUDED.parking_info,
                            pmr_access = EXCLUDED.pmr_access,
                            sensitive_medical_instruction = EXCLUDED.sensitive_medical_instruction,
                            escalation_instruction = EXCLUDED.escalation_instruction,
                            human_handoff_instruction = EXCLUDED.human_handoff_instruction,
                            faq_items_json = EXCLUDED.faq_items_json,
                            updated_at = now()
                        """,
                        (
                            tenant_id,
                            assistant_payload["assistant_name"],
                            assistant_payload["welcome_message"],
                            assistant_payload["documents_to_bring"],
                            assistant_payload["access_instructions"],
                            assistant_payload["payment_methods"],
                            assistant_payload["parking_info"],
                            assistant_payload["pmr_access"],
                            assistant_payload["sensitive_medical_instruction"],
                            assistant_payload["escalation_instruction"],
                            assistant_payload["human_handoff_instruction"],
                            json.dumps(assistant_payload["faq_items"]),
                        ),
                    )
                    assistant += 1

                    cur.execute("DELETE FROM tenant_appointment_reasons WHERE tenant_id = %s", (tenant_id,))
                    for item in reasons_payload:
                        cur.execute(
                            """
                            INSERT INTO tenant_appointment_reasons (
                                id, tenant_id, label, duration_minutes, description, enabled, allowed_for_new_patients, created_at, updated_at
                            )
                            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, now(), now())
                            ON CONFLICT (id) DO UPDATE SET
                                label = EXCLUDED.label,
                                duration_minutes = EXCLUDED.duration_minutes,
                                description = EXCLUDED.description,
                                enabled = EXCLUDED.enabled,
                                allowed_for_new_patients = EXCLUDED.allowed_for_new_patients,
                                updated_at = now()
                            """,
                            (
                                item["id"],
                                tenant_id,
                                item["label"],
                                item["duration_minutes"],
                                item["description"],
                                item["enabled"],
                                item["allowed_for_new_patients"],
                            ),
                        )
                    reasons += len(reasons_payload)

            if not args.dry_run:
                conn.commit()
                print("Backfill terminé.")
                print(
                    f"Profiles={profiles}, opening_rows={openings}, availability={availability}, "
                    f"booking_rules={rules}, assistant_settings={assistant}, reasons={reasons}"
                )
            else:
                print("Dry-run terminé (aucune écriture).")
        return 0
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
