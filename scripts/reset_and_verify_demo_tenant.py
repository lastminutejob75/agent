#!/usr/bin/env python3
"""
Reset des données opérationnelles du cabinet démo + re-liaison + vérifications.

Supprime appels, RDV, patients exemple, bookings page publique, etc.
Conserve : tenant_config, tenant_routing, tenant_users, tenant_profiles.

Usage (racine du projet) :
  python3 scripts/reset_and_verify_demo_tenant.py --prod -y
  python3 scripts/reset_and_verify_demo_tenant.py              # SQLite local tenant 1

Variables :
  DATABASE_URL / DATABASE_PUBLIC_URL  (Postgres prod)
  BASE_URL                            (API pour vérifs HTTP, ex. Railway)
  DEMO_TENANT_ID / TEST_TENANT_ID     (défaut 2 prod, 1 local)
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEMO_DID = "+33939240575"
PUBLIC_SLUG = "cabinet-demo-uwi"
DEFAULT_VAPI_ASSISTANT_ID = "78dd0e14-337e-40ab-96d9-7dbbe92cdf95"


def _tenant_id(prod: bool, override: Optional[int]) -> int:
    if override is not None:
        return int(override)
    default = 2 if prod else 1
    raw = os.getenv("DEMO_TENANT_ID") or os.getenv("TEST_TENANT_ID")
    return int(raw) if raw else default


def _pg_delete_queries(tenant_id: int) -> List[Tuple[str, str]]:
    """(label, SQL) — ordre respectant les FK implicites."""
    tid = tenant_id
    return [
        ("public_page_events", "DELETE FROM public_page_events WHERE tenant_id = %s"),
        ("public_bookings", "DELETE FROM public_bookings WHERE tenant_id = %s"),
        ("call_transcripts", "DELETE FROM call_transcripts WHERE tenant_id = %s"),
        ("call_messages", "DELETE FROM call_messages WHERE tenant_id = %s"),
        ("call_state_checkpoints", "DELETE FROM call_state_checkpoints WHERE tenant_id = %s"),
        ("call_sessions", "DELETE FROM call_sessions WHERE tenant_id = %s"),
        ("vapi_call_usage", "DELETE FROM vapi_call_usage WHERE tenant_id = %s"),
        ("vapi_calls", "DELETE FROM vapi_calls WHERE tenant_id = %s"),
        ("ivr_events", "DELETE FROM ivr_events WHERE client_id = %s"),
        ("web_sessions", "DELETE FROM web_sessions WHERE tenant_id = %s"),
        ("human_handoffs", "DELETE FROM human_handoffs WHERE tenant_id = %s"),
        ("appointments", "DELETE FROM appointments WHERE tenant_id = %s"),
        ("slots (libérer)", "UPDATE slots SET is_booked = FALSE WHERE tenant_id = %s"),
        ("tenant_clients", "DELETE FROM tenant_clients WHERE tenant_id = %s"),
    ]


def _table_exists(cur, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
    row = cur.fetchone()
    val = row[0] if isinstance(row, tuple) else (row.get("to_regclass") if row else None)
    return bool(val)


def purge_postgres(tenant_id: int) -> Dict[str, int]:
    from backend.pg_pool import pg_connection
    from backend.pg_tenant_context import set_bypass_tenant_rls_on_connection

    deleted: Dict[str, int] = {}
    with pg_connection() as conn:
        set_bypass_tenant_rls_on_connection(conn, enabled=True)
        with conn.cursor() as cur:
            for label, sql in _pg_delete_queries(tenant_id):
                table = label.split()[0]
                if table not in ("ivr_events",) and not _table_exists(cur, table):
                    deleted[label] = 0
                    continue
                try:
                    cur.execute(sql, (tenant_id,))
                    deleted[label] = int(cur.rowcount or 0)
                except Exception as exc:
                    if "does not exist" in str(exc).lower():
                        deleted[label] = 0
                    else:
                        raise
        conn.commit()
    return deleted


def purge_sqlite(tenant_id: int, db_path: Path) -> Dict[str, int]:
    deleted: Dict[str, int] = {}
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()

        def run(label: str, sql: str, params: tuple) -> None:
            try:
                cur.execute(sql, params)
                deleted[label] = cur.rowcount
            except sqlite3.OperationalError as exc:
                if "no such table" in str(exc).lower():
                    deleted[label] = 0
                else:
                    raise

        run("ivr_events (tenant)", "DELETE FROM ivr_events WHERE client_id = ?", (tenant_id,))
        run("ivr_events (demo-*)", "DELETE FROM ivr_events WHERE call_id LIKE 'demo-%'", ())
        run("human_handoffs", "DELETE FROM human_handoffs WHERE tenant_id = ?", (tenant_id,))
        run("cabinet_clients", "DELETE FROM cabinet_clients WHERE tenant_id = ?", (tenant_id,))
        run("appointments", "DELETE FROM appointments WHERE tenant_id = ?", (tenant_id,))
        run("slots (libérer)", "UPDATE slots SET is_booked = 0 WHERE tenant_id = ?", (tenant_id,))
        conn.commit()
    finally:
        conn.close()
    return deleted


def relink_demo(prod: bool, tenant_id: int, create_user: bool) -> None:
    cmd = [sys.executable, str(ROOT / "scripts" / "link_demo_tenant.py")]
    if prod:
        cmd.append("--prod")
    cmd.extend(["--tenant-id", str(tenant_id)])
    if create_user:
        cmd.append("--create-demo-user")
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def regenerate_slots_pg(tenant_id: int) -> None:
    try:
        from backend.slots_pg import pg_cleanup_and_ensure_slots

        pg_cleanup_and_ensure_slots(tenant_id)
        print(f"  [OK] Créneaux PG régénérés pour tenant {tenant_id}")
    except Exception as exc:
        print(f"  [WARN] Régénération créneaux PG : {exc}")


def _http_get(base_url: str, path: str) -> Tuple[Optional[dict], Optional[str]]:
    url = f"{base_url.rstrip('/')}{path}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read().decode()), None
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode()[:300]
        except Exception:
            body = ""
        return None, f"HTTP {exc.code}: {body}"
    except Exception as exc:
        return None, str(exc)


def verify_connections(base_url: str, tenant_id: int) -> int:
    """Retourne le nombre de checks OK."""
    ok = 0
    total = 0
    print(f"\n--- Vérifications HTTP ({base_url}) ---")

    checks = [
        ("/health", lambda d: d.get("status") == "ok", "Health backend"),
        ("/api/vapi/health", lambda d: d.get("status") == "ok", "Vapi health"),
        ("/api/vapi/test", lambda d: d.get("status") == "ok", "Vapi engine"),
        (
            f"/api/public/practitioner/{PUBLIC_SLUG}?requireExists=1",
            lambda d: d.get("slug") == PUBLIC_SLUG and d.get("source") != "demo",
            "Page publique (tenant réel, pas fallback demo)",
        ),
        (
            f"/api/public/slots/{PUBLIC_SLUG}?count=6",
            lambda d: isinstance(d.get("slots"), list) and len(d.get("slots") or []) > 0,
            "Créneaux page publique",
        ),
    ]

    for path, predicate, label in checks:
        total += 1
        data, err = _http_get(base_url, path)
        if err:
            print(f"  [KO] {label} → {err}")
            continue
        if predicate(data):
            ok += 1
            print(f"  [OK] {label}")
            if path == "/health":
                print(
                    f"       GCal credentials={data.get('credentials_loaded')} "
                    f"calendar_id={data.get('calendar_id_set')}"
                )
            if "practitioner" in path:
                print(
                    f"       name={data.get('name')} phone={data.get('phone')} "
                    f"tenantId={data.get('tenantId')} source={data.get('source')}"
                )
            if "slots" in path:
                print(f"       source={data.get('source')} count={len(data.get('slots') or [])}")
        else:
            print(f"  [KO] {label} → {data}")

    total += 1
    data, err = _http_get(base_url, "/api/vapi/test-calendar")
    if err:
        print(f"  [KO] Google Calendar test → {err}")
    elif data.get("status") == "ok" or data.get("success") is True:
        ok += 1
        print("  [OK] Google Calendar test")
    else:
        print(f"  [KO] Google Calendar test → {data}")

    total += 1
    data, err = _http_get(base_url, f"/api/public/praticiens/{PUBLIC_SLUG}/patient-hint?phone=%2B33612345678")
    if err:
        print(f"  [KO] API patient-hint → {err}")
    else:
        ok += 1
        print(f"  [OK] API patient-hint (found={data.get('found')})")

    print(f"\nVérifications HTTP : {ok}/{total} OK")
    verify_postgres_config(tenant_id)
    return ok


def verify_postgres_config(tenant_id: int) -> None:
    url = os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")
    if not url:
        return
    print("\n--- Config Postgres (tenant démo) ---")
    try:
        from backend.pg_pool import pg_connection
        from backend.pg_tenant_context import set_bypass_tenant_rls_on_connection

        with pg_connection() as conn:
            set_bypass_tenant_rls_on_connection(conn, enabled=True)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT params_json->>'public_slug' AS slug, "
                    "params_json->>'vapi_assistant_id' AS vapi, "
                    "params_json->>'phone_number' AS phone, "
                    "params_json->>'calendar_id' AS cal, "
                    "params_json->>'calendar_provider' AS cal_provider "
                    "FROM tenant_config WHERE tenant_id = %s",
                    (tenant_id,),
                )
                cfg = cur.fetchone() or {}
                cur.execute(
                    "SELECT key, is_active FROM tenant_routing "
                    "WHERE tenant_id = %s AND channel = 'vocal'",
                    (tenant_id,),
                )
                routes = cur.fetchall() or []
                cur.execute("SELECT COUNT(*) AS c FROM vapi_calls WHERE tenant_id = %s", (tenant_id,))
                calls = int((cur.fetchone() or {}).get("c") or 0)
                cur.execute("SELECT COUNT(*) AS c FROM public_bookings WHERE tenant_id = %s", (tenant_id,))
                bookings = int((cur.fetchone() or {}).get("c") or 0)
                cur.execute("SELECT COUNT(*) AS c FROM ivr_events WHERE client_id = %s", (tenant_id,))
                events = int((cur.fetchone() or {}).get("c") or 0)

        slug = cfg.get("slug")
        vapi = cfg.get("vapi") or DEFAULT_VAPI_ASSISTANT_ID
        phone = cfg.get("phone")
        print(f"  slug={slug} {'OK' if slug == PUBLIC_SLUG else 'KO'}")
        print(f"  vapi_assistant_id={vapi}")
        print(f"  phone_number={phone} {'OK' if phone == DEMO_DID else 'KO'}")
        print(f"  calendar={cfg.get('cal_provider')} id={bool(cfg.get('cal'))}")
        print(f"  routing vocal: {[dict(r) for r in routes]}")
        print(f"  données restantes: vapi_calls={calls} public_bookings={bookings} ivr_events={events}")
        if calls or bookings or events:
            print("  [WARN] Des données opérationnelles subsistent (normal si purge partielle).")
        else:
            print("  [OK] Base opérationnelle vide pour ce tenant.")
    except Exception as exc:
        print(f"  [WARN] Vérif Postgres impossible : {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset données démo + re-liaison + vérifs")
    parser.add_argument("--prod", action="store_true", help="Postgres (DATABASE_URL)")
    parser.add_argument("--tenant-id", type=int, default=None)
    parser.add_argument("--create-demo-user", action="store_true", help="Recrée demo@uwi.app")
    parser.add_argument(
        "--base-url",
        default=os.getenv("BASE_URL", "").strip(),
        help="URL API pour vérifs HTTP (ex. https://xxx.railway.app). Vide = skip HTTP.",
    )
    parser.add_argument("--skip-purge", action="store_true", help="Ne pas supprimer les données")
    parser.add_argument("--skip-relink", action="store_true", help="Ne pas relancer link_demo_tenant")
    parser.add_argument("-y", "--yes", action="store_true", help="Sans confirmation")
    args = parser.parse_args()

    tenant_id = _tenant_id(args.prod, args.tenant_id)
    mode = "Postgres prod" if args.prod else "SQLite local"
    db_path = ROOT / "agent.db"

    print("=" * 60)
    print("Reset cabinet démo UWi")
    print(f"  Mode      : {mode}")
    print(f"  tenant_id : {tenant_id}")
    print(f"  slug      : {PUBLIC_SLUG}")
    print(f"  numéro    : {DEMO_DID}")
    print("=" * 60)

    if not args.yes and not args.skip_purge:
        answer = input(f"\nSupprimer TOUTES les données opérationnelles du tenant {tenant_id} ? [y/N] ")
        if answer.strip().lower() not in ("y", "yes", "o", "oui"):
            print("Annulé.")
            return 1

    if not args.skip_purge:
        print("\n--- Purge données opérationnelles ---")
        if args.prod:
            if not (os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")):
                print("❌ DATABASE_URL requis pour --prod")
                return 1
            deleted = purge_postgres(tenant_id)
        else:
            if not db_path.exists():
                print(f"❌ {db_path} introuvable")
                return 1
            deleted = purge_sqlite(tenant_id, db_path)

        for label, count in deleted.items():
            print(f"  {label}: {count} ligne(s)")

        if args.prod:
            regenerate_slots_pg(tenant_id)

    if not args.skip_relink:
        print("\n--- Re-liaison tenant démo (Vapi, page publique, routing) ---")
        relink_demo(args.prod, tenant_id, args.create_demo_user or args.prod)

    if args.base_url:
        verify_connections(args.base_url, tenant_id)
    else:
        print("\n--- Vérifications HTTP ignorées (BASE_URL / --base-url non défini) ---")
        if args.prod:
            verify_postgres_config(tenant_id)

    print("\n✅ Terminé.")
    print(f"   Page publique : https://www.uwiapp.com/p/{PUBLIC_SLUG}")
    print(f"   Dashboard     : login demo@uwi.app (tenant {tenant_id})")
    print("   Prochain test : 1 appel vocal + 1 RDV page publique → dashboard doit rester cohérent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
