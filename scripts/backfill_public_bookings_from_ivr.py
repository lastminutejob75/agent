#!/usr/bin/env python3
"""
Backfill public_bookings depuis ivr_events (call_id public-{uuid}).

Usage:
  python3 scripts/backfill_public_bookings_from_ivr.py --tenant-id 2
  python3 scripts/backfill_public_bookings_from_ivr.py --prod --tenant-id 2
  python3 scripts/backfill_public_bookings_from_ivr.py --prod --tenant-id 2 --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_env_railway() -> None:
    env_path = ROOT / ".env.railway"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    pub = (os.environ.get("DATABASE_PUBLIC_URL") or "").strip()
    if pub:
        os.environ["DATABASE_URL"] = pub
        os.environ["PG_TENANTS_URL"] = pub


def _parse_context(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _fetch_candidates(tenant_id: int) -> List[Dict[str, Any]]:
    from backend.pg_pool import pg_connection
    from backend.pg_tenant_context import set_bypass_tenant_rls_on_connection

    rows: List[Dict[str, Any]] = []
    with pg_connection() as conn:
        set_bypass_tenant_rls_on_connection(conn, enabled=True)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT call_id, event, context, created_at
                FROM ivr_events
                WHERE client_id = %s
                  AND call_id LIKE 'public-%%'
                  AND event IN ('booking_confirmed', 'booking_requested')
                ORDER BY created_at ASC
                """,
                (tenant_id,),
            )
            for r in cur.fetchall() or []:
                call_id = str(r.get("call_id") or "").strip()
                if not call_id.startswith("public-"):
                    continue
                booking_id = call_id[len("public-") :].strip()
                if not booking_id:
                    continue
                ctx = _parse_context(r.get("context"))
                rows.append(
                    {
                        "booking_id": booking_id,
                        "call_id": call_id,
                        "event": str(r.get("event") or "").strip(),
                        "created_at": r.get("created_at"),
                        "context": ctx,
                    }
                )
    return rows


def _existing_ids(tenant_id: int) -> set[str]:
    from backend.public_bookings_pg import ensure_public_bookings_schema
    from backend.pg_pool import pg_connection
    from backend.pg_tenant_context import set_tenant_id_on_connection

    ensure_public_bookings_schema()
    with pg_connection() as conn:
        set_tenant_id_on_connection(conn, tenant_id)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id::text FROM public_bookings WHERE tenant_id = %s",
                (tenant_id,),
            )
            return {str(r.get("id") or "").strip() for r in (cur.fetchall() or []) if r.get("id")}


def backfill(tenant_id: int, *, apply: bool) -> Dict[str, int]:
    from backend.public_bookings_pg import ensure_public_bookings_schema, insert_public_booking

    ensure_public_bookings_schema()
    existing = _existing_ids(tenant_id)
    candidates = _fetch_candidates(tenant_id)
    stats = {"candidates": len(candidates), "skipped_existing": 0, "inserted": 0, "errors": 0}

    seen: set[str] = set()
    for row in candidates:
        bid = row["booking_id"]
        if bid in seen:
            continue
        seen.add(bid)
        if bid in existing:
            stats["skipped_existing"] += 1
            continue

        ctx = row.get("context") or {}
        status = "confirmed" if row.get("event") == "booking_confirmed" else "pending"
        payload = {
            "booking_id": bid,
            "tenant_id": tenant_id,
            "slot_id": str(ctx.get("slot_id") or ctx.get("slotId") or "backfill")[:80],
            "slot_label": str(ctx.get("slot_label") or ctx.get("slotLabel") or "Créneau")[:140],
            "patient_name": str(ctx.get("patient_name") or ctx.get("patientName") or "Patient")[:200],
            "patient_phone": str(ctx.get("patient_phone") or ctx.get("patientPhone") or "0000000000")[:40],
            "patient_email": (ctx.get("patient_email") or ctx.get("patientEmail") or None),
            "motif": str(ctx.get("motif") or "Consultation")[:120],
            "source": str(ctx.get("source") or "page_publique")[:40],
            "status": status,
            "start_iso": (ctx.get("start_iso") or ctx.get("startIso") or None),
            "booking_code": None,
            "google_event_id": None,
        }

        if not apply:
            print(
                f"  [dry-run] {bid} | {status} | {payload['patient_name']} | {payload['slot_label']}"
            )
            stats["inserted"] += 1
            continue

        try:
            insert_public_booking(**payload)
            stats["inserted"] += 1
            print(f"  [insert] {bid} | {status} | {payload['patient_name']}")
        except Exception as exc:
            stats["errors"] += 1
            print(f"  [error] {bid}: {exc}", file=sys.stderr)

    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prod", action="store_true", help="Charge .env.railway")
    parser.add_argument("--tenant-id", type=int, default=2)
    parser.add_argument("--apply", action="store_true", help="Écrit en base (sinon dry-run)")
    args = parser.parse_args()

    if args.prod:
        _load_env_railway()

    if not (os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")):
        raise SystemExit("DATABASE_URL requis")

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"Backfill public_bookings tenant_id={args.tenant_id} ({mode})")
    stats = backfill(int(args.tenant_id), apply=bool(args.apply))
    print(
        f"Terminé: candidates={stats['candidates']} inserted={stats['inserted']} "
        f"skipped_existing={stats['skipped_existing']} errors={stats['errors']}"
    )


if __name__ == "__main__":
    main()
