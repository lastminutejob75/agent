#!/usr/bin/env python3
"""
Rattrapage profil cabinet : notes wizard admin + clés legacy params_json
→ champs canoniques (practitioner_name, address_line1, phone_number, …)
→ sync tenant_profiles.

Usage:
  DATABASE_URL='postgresql://...' python3 scripts/backfill_tenant_profile_from_params.py --dry-run
  DATABASE_URL='postgresql://...' python3 scripts/backfill_tenant_profile_from_params.py
  python3 scripts/backfill_tenant_profile_from_params.py --tenant-id 2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
_env = _root / ".env"
if _env.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(_env)
    except ImportError:
        pass


def _parse_wizard_notes(notes_raw: Any) -> Dict[str, Any]:
    if not notes_raw:
        return {}
    if isinstance(notes_raw, dict):
        return notes_raw if notes_raw.get("wizard") else {}
    if isinstance(notes_raw, str):
        try:
            data = json.loads(notes_raw)
            if isinstance(data, dict) and data.get("wizard"):
                return data
        except Exception:
            pass
    return {}


def _build_patch(params: Dict[str, Any], tenant_name: str) -> Dict[str, Any]:
    from backend.cabinet_profile_pg import canonicalize_cabinet_params

    patch: Dict[str, Any] = {}
    wizard = _parse_wizard_notes(params.get("notes"))

    practitioner = (
        (params.get("practitioner_name") or params.get("primary_practitioner_name") or wizard.get("practitioner") or "")
        .strip()
    )
    if practitioner:
        patch["practitioner_name"] = practitioner

    cabinet = (params.get("business_name") or tenant_name or "").strip()
    if cabinet:
        patch["business_name"] = cabinet

    specialty = (params.get("specialty_label") or params.get("profession") or wizard.get("profession") or "").strip()
    if specialty:
        patch["specialty_label"] = specialty

    phone = (params.get("phone_number") or params.get("current_phone_number") or "").strip()
    if phone:
        patch["phone_number"] = phone

    email = (params.get("contact_email") or "").strip()
    if email:
        patch["contact_email"] = email

    address = (
        (params.get("address_line1") or params.get("address_line") or params.get("address") or wizard.get("address") or "")
        .strip()
    )
    if address:
        patch["address_line1"] = address

    city = (params.get("city") or wizard.get("city") or "").strip()
    if city:
        patch["city"] = city

    postal = (params.get("postal_code") or "").strip()
    if postal:
        patch["postal_code"] = postal

    return canonicalize_cabinet_params(patch)


def _load_tenants(tenant_id: Optional[int]) -> list:
    from backend.tenants_pg import _pg_url

    url = _pg_url()
    if not url:
        print("Erreur: DATABASE_URL / PG_TENANTS_URL requis", file=sys.stderr)
        sys.exit(1)
    import psycopg
    from psycopg.rows import dict_row

    rows = []
    with psycopg.connect(url, row_factory=dict_row) as conn:
        from backend.pg_tenant_context import set_bypass_tenant_rls_on_connection

        set_bypass_tenant_rls_on_connection(conn, enabled=True)
        with conn.cursor() as cur:
            if tenant_id:
                cur.execute(
                    """
                    SELECT t.tenant_id, t.name, tc.params_json
                    FROM tenants t
                    JOIN tenant_config tc ON tc.tenant_id = t.tenant_id
                    WHERE t.tenant_id = %s
                    """,
                    (tenant_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT t.tenant_id, t.name, tc.params_json
                    FROM tenants t
                    JOIN tenant_config tc ON tc.tenant_id = t.tenant_id
                    WHERE t.status = 'active' OR t.status IS NULL
                    ORDER BY t.tenant_id
                    """
                )
            rows = list(cur.fetchall())
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description="Backfill profil cabinet depuis params_json")
    p.add_argument("--tenant-id", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    from backend import config

    if not config.USE_PG_TENANTS:
        print("Requiert USE_PG_TENANTS=true", file=sys.stderr)
        return 1

    from backend.cabinet_profile_pg import sync_normalized_from_params
    from backend.tenants_pg import pg_get_tenant_params, pg_update_tenant_params

    updated = 0
    skipped = 0

    for row in _load_tenants(args.tenant_id):
        tid = int(row["tenant_id"])
        name = (row.get("name") or "").strip()
        params = row.get("params_json") or {}
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {}
        if not isinstance(params, dict):
            params = {}

        patch = _build_patch(params, name)
        if not patch:
            skipped += 1
            continue

        print(f"tenant_id={tid} patch={json.dumps(patch, ensure_ascii=False)}")
        if args.dry_run:
            updated += 1
            continue

        existing_pair = pg_get_tenant_params(tid)
        existing = (existing_pair or ({}, "none"))[0] if existing_pair else {}
        merged = dict(existing or {})
        merged.update(patch)
        if not pg_update_tenant_params(tid, patch):
            print(f"  WARN: pg_update_tenant_params failed tenant_id={tid}", file=sys.stderr)
            continue
        try:
            sync_normalized_from_params(tid, merged)
        except Exception as e:
            print(f"  WARN: sync_normalized tenant_id={tid}: {e}", file=sys.stderr)
        updated += 1

    print(f"OK — {updated} tenant(s) traités, {skipped} sans données à rattraper")
    return 0


if __name__ == "__main__":
    sys.exit(main())
