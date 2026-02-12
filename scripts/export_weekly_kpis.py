#!/usr/bin/env python3
# scripts/export_weekly_kpis.py (v2)
"""
Export hebdomadaire KPIs par tenant (ivr_events SQLite).
- Tous les tenants actifs, même avec 0 appel (JOIN tenants)
- convert_after_refuse_pref : parmi les calls avec slot_refuse_pref_asked, combien ont booking_confirmed
- 3 CSV : kpi_weekly_*.csv + kpi_weekly_details_*.csv + kpi_weekly_digest_*.csv (résumé client)
- Verrou anti double-exécution : si fichiers existent → skip (--force pour override)

Usage:
  python scripts/export_weekly_kpis.py --start 2026-02-02 --end 2026-02-09
  python scripts/export_weekly_kpis.py --last-week  # auto calcule semaine précédente
  python scripts/export_weekly_kpis.py --last-week --force  # override si déjà généré
  DATABASE_URL=postgres://... python scripts/export_weekly_kpis.py --last-week  # prod: lit Postgres
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_DB_PATH = os.environ.get("UWI_DB_PATH", "agent.db")

# Tables / colonnes (schéma actuel)
TENANTS_TABLE = "tenants"
TENANT_ID_COL = "tenant_id"
TENANT_NAME_COL = "name"
TENANT_STATUS_COL = "status"

IVR_EVENTS_TABLE = "ivr_events"
COL_TENANT = "client_id"   # vocal: tenant_id == client_id
COL_CALL_ID = "call_id"    # conv_id / call_id unique par session
COL_EVENT = "event"        # nom colonne ivr_events
COL_CONTEXT = "context"
COL_REASON = "reason"
COL_TS = "created_at"

# Event aliases (legacy)
TRANSFER_EVENTS = {"transferred_human", "transfer_human", "transfer", "transferred"}
ABANDON_EVENTS = {"user_abandon", "abandon", "hangup", "user_hangup"}
BOOKING_CONFIRMED_EVENTS = {"booking_confirmed"}

REPEAT_EVENTS = {"repeat_used"}
YES_AMBIGUOUS_ROUTER_EVENTS = {"yes_ambiguous_router"}
SLOT_REFUSE_PREF_EVENTS = {"slot_refuse_pref_asked"}

EMPTY_MESSAGE_EVENTS = {"empty_message"}
ANTI_LOOP_EVENTS = {"anti_loop_trigger"}
INTENT_ROUTER_EVENTS = {"intent_router_trigger"}
CANCEL_DONE_EVENTS = {"cancel_done"}
CANCEL_FAILED_EVENTS = {"cancel_failed"}

DETAIL_EVENTS = {"recovery_step", "intent_router_trigger"}


@dataclass
class TenantInfo:
    tenant_id: int
    name: str
    status: str


@dataclass
class TenantKPI:
    week_start: str
    week_end: str
    tenant_id: int
    tenant_name: str
    calls_total: int = 0

    bookings_confirmed: int = 0
    transfers: int = 0
    abandons: int = 0

    repeat_used_calls: int = 0
    yes_ambiguous_router_calls: int = 0
    slot_refuse_pref_asked_calls: int = 0

    convert_after_refuse_pref_num: int = 0
    convert_after_refuse_pref_den: int = 0
    convert_after_refuse_pref_rate: float = 0.0

    empty_message_calls: int = 0
    anti_loop_calls: int = 0
    intent_router_calls: int = 0
    cancel_done_calls: int = 0
    cancel_failed_calls: int = 0

    transfer_rate: float = 0.0
    abandon_rate: float = 0.0
    booking_rate: float = 0.0
    repeat_rate: float = 0.0
    yes_ambiguous_router_rate: float = 0.0
    slot_refuse_pref_rate: float = 0.0


def _last_week_iso() -> Tuple[str, str]:
    """
    Semaine précédente : lundi 00:00 → lundi suivant 00:00.
    Compatible cron (pas besoin de date -d / BusyBox).
    """
    now = datetime.now()
    # Dernier lundi (0=Monday)
    days_since_monday = (now.weekday()) % 7
    last_monday = now - timedelta(days=days_since_monday + 7)
    next_monday = last_monday + timedelta(days=7)
    return last_monday.strftime("%Y-%m-%d"), next_monday.strftime("%Y-%m-%d")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Export weekly KPIs per tenant from ivr_events (SQLite)."
    )
    p.add_argument(
        "--db", default=DEFAULT_DB_PATH,
        help=f"SQLite DB path (default: {DEFAULT_DB_PATH})",
    )
    p.add_argument(
        "--start",
        help="Start datetime (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    )
    p.add_argument(
        "--end",
        help="End datetime exclusive (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    )
    p.add_argument(
        "--last-week",
        action="store_true",
        help="Use previous week (Mon->Mon). Overrides --start/--end. Cron-friendly.",
    )
    p.add_argument(
        "--out_dir", default=".",
        help="Output directory (default: .)",
    )
    p.add_argument(
        "--include_inactive",
        action="store_true",
        help="Include inactive tenants (default: false)",
    )
    p.add_argument(
        "--details-limit", type=int, default=20,
        help="Top N reasons per tenant in details CSV (default: 20)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Override existing files (default: skip if both CSVs exist = idempotent cron)",
    )
    p.add_argument(
        "--db-pg-url",
        default=os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL"),
        help="Postgres URL for ivr_events (prod). If set, read from PG instead of SQLite.",
    )
    return p.parse_args()


def _parse_dt(s: str) -> str:
    s = s.strip()
    if len(s) == 10:
        return s + " 00:00:00"
    return s.replace("T", " ")


def _connect_sqlite(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_pg(url: str) -> Any:
    import psycopg
    from psycopg.rows import dict_row
    return psycopg.connect(url, row_factory=dict_row)


def _execute_ivr(conn_ivr: Any, query: str, params: list, is_pg: bool) -> list:
    """Execute on ivr_events (SQLite or Postgres)."""
    if is_pg:
        with conn_ivr.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
    return conn_ivr.execute(query, params).fetchall()


def _unique_session_expr() -> str:
    return f"COALESCE(NULLIF(TRIM({COL_CALL_ID}), ''), 'UNKNOWN')"


def _safe_rate(n: int, d: int) -> float:
    return (n / d) if d else 0.0


def fetch_tenants_from_pg(include_inactive: bool) -> Optional[List[TenantInfo]]:
    """PG-first : charge tenants depuis Postgres si disponible."""
    try:
        from backend.tenants_pg import pg_fetch_tenants
        result = pg_fetch_tenants(include_inactive)
        if result:
            rows, _ = result
            return [
                TenantInfo(
                    tenant_id=int(r["tenant_id"]),
                    name=str(r.get("name") or ""),
                    status=str(r.get("status") or "active"),
                )
                for r in rows
            ]
    except Exception:
        pass
    return None


def fetch_tenants(conn: sqlite3.Connection, include_inactive: bool, use_pg: bool = False) -> List[TenantInfo]:
    if use_pg:
        pg_tenants = fetch_tenants_from_pg(include_inactive)
        if pg_tenants:
            return pg_tenants
    if include_inactive:
        q = f"""
        SELECT {TENANT_ID_COL} AS tenant_id, {TENANT_NAME_COL} AS name, {TENANT_STATUS_COL} AS status
        FROM {TENANTS_TABLE}
        ORDER BY {TENANT_ID_COL}
        """
    else:
        q = f"""
        SELECT {TENANT_ID_COL} AS tenant_id, {TENANT_NAME_COL} AS name, {TENANT_STATUS_COL} AS status
        FROM {TENANTS_TABLE}
        WHERE COALESCE({TENANT_STATUS_COL}, 'active') = 'active'
        ORDER BY {TENANT_ID_COL}
        """
    rows = conn.execute(q).fetchall()
    out: List[TenantInfo] = []
    for r in rows:
        out.append(
            TenantInfo(
                tenant_id=int(r["tenant_id"]),
                name=str(r["name"] or ""),
                status=str(r["status"] or "active"),
            )
        )
    return out


def _ph(n: int, is_pg: bool) -> str:
    return ",".join(["%s" if is_pg else "?"] * n)


def fetch_calls_total(
    conn_ivr: Any, start: str, end: str, is_pg: bool,
) -> Dict[int, int]:
    q = f"""
    SELECT {COL_TENANT} AS tenant_id,
           COUNT(DISTINCT {_unique_session_expr()}) AS calls_total
    FROM {IVR_EVENTS_TABLE}
    WHERE {COL_TS} >= {"%s" if is_pg else "?"} AND {COL_TS} < {"%s" if is_pg else "?"}
      AND {COL_TENANT} IS NOT NULL
    GROUP BY {COL_TENANT}
    """
    out: Dict[int, int] = {}
    for r in _execute_ivr(conn_ivr, q, [start, end], is_pg):
        out[int(r["tenant_id"])] = int(r["calls_total"])
    return out


def fetch_event_calls(
    conn_ivr: Any, start: str, end: str, events: Iterable[str], is_pg: bool,
) -> Dict[int, int]:
    ev = list(events)
    if not ev:
        return {}
    ph = _ph(len(ev), is_pg)
    q = f"""
    SELECT {COL_TENANT} AS tenant_id,
           COUNT(DISTINCT {_unique_session_expr()}) AS calls_with_event
    FROM {IVR_EVENTS_TABLE}
    WHERE {COL_TS} >= {"%s" if is_pg else "?"} AND {COL_TS} < {"%s" if is_pg else "?"}
      AND {COL_TENANT} IS NOT NULL
      AND {COL_EVENT} IN ({ph})
    GROUP BY {COL_TENANT}
    """
    params = [start, end] + ev
    out: Dict[int, int] = {}
    for r in _execute_ivr(conn_ivr, q, params, is_pg):
        out[int(r["tenant_id"])] = int(r["calls_with_event"])
    return out


def fetch_convert_after_refuse_pref(
    conn_ivr: Any, start: str, end: str, is_pg: bool,
) -> Dict[int, Tuple[int, int]]:
    """
    den = calls having slot_refuse_pref_asked
    num = among those, calls also having booking_confirmed
    """
    p = "%s" if is_pg else "?"
    ph_den = _ph(len(SLOT_REFUSE_PREF_EVENTS), is_pg)
    ph_num = _ph(len(BOOKING_CONFIRMED_EVENTS), is_pg)
    q = f"""
    WITH refuse_calls AS (
      SELECT {COL_TENANT} AS tenant_id,
             {_unique_session_expr()} AS call_key
      FROM {IVR_EVENTS_TABLE}
      WHERE {COL_TS} >= {p} AND {COL_TS} < {p}
        AND {COL_TENANT} IS NOT NULL
        AND {COL_EVENT} IN ({ph_den})
      GROUP BY {COL_TENANT}, call_key
    ),
    confirmed_calls AS (
      SELECT {COL_TENANT} AS tenant_id,
             {_unique_session_expr()} AS call_key
      FROM {IVR_EVENTS_TABLE}
      WHERE {COL_TS} >= {p} AND {COL_TS} < {p}
        AND {COL_TENANT} IS NOT NULL
        AND {COL_EVENT} IN ({ph_num})
      GROUP BY {COL_TENANT}, call_key
    )
    SELECT r.tenant_id AS tenant_id,
           COUNT(*) AS den,
           SUM(CASE WHEN c.call_key IS NOT NULL THEN 1 ELSE 0 END) AS num
    FROM refuse_calls r
    LEFT JOIN confirmed_calls c
      ON c.tenant_id = r.tenant_id AND c.call_key = r.call_key
    GROUP BY r.tenant_id
    """
    params = (
        [start, end] + list(SLOT_REFUSE_PREF_EVENTS)
        + [start, end] + list(BOOKING_CONFIRMED_EVENTS)
    )
    out: Dict[int, Tuple[int, int]] = {}
    for r in _execute_ivr(conn_ivr, q, params, is_pg):
        tid = int(r["tenant_id"])
        den = int(r["den"] or 0)
        num = int(r["num"] or 0)
        out[tid] = (num, den)
    return out


def _extract_reason(context: Optional[str], reason: Optional[str]) -> str:
    """Combine context + reason (ivr_events n'a pas payload_json)."""
    parts = []
    if reason and str(reason).strip():
        parts.append(str(reason).strip())
    if context and str(context).strip():
        parts.append(str(context).strip())
    return " | ".join(parts) if parts else "(none)"


def fetch_details_top_reasons(
    conn_ivr: Any,
    start: str,
    end: str,
    is_pg: bool,
    limit_per_tenant: int = 10,
) -> List[Dict[str, str]]:
    """
    Produces rows for details CSV:
      tenant_id, event_type, reason, n
    For recovery_step + intent_router_trigger.
    Reason from context + reason columns.
    """
    ph = _ph(len(DETAIL_EVENTS), is_pg)
    p = "%s" if is_pg else "?"
    q = f"""
    SELECT {COL_TENANT} AS tenant_id,
           {COL_EVENT} AS event_type,
           {COL_CONTEXT} AS context,
           {COL_REASON} AS reason
    FROM {IVR_EVENTS_TABLE}
    WHERE {COL_TS} >= {p} AND {COL_TS} < {p}
      AND {COL_TENANT} IS NOT NULL
      AND {COL_EVENT} IN ({ph})
    """
    params = [start, end] + list(DETAIL_EVENTS)
    rows = _execute_ivr(conn_ivr, q, params, is_pg)

    agg: Dict[Tuple[int, str, str], int] = {}
    for r in rows:
        tid = int(r["tenant_id"])
        et = str(r["event_type"])
        reason = _extract_reason(r["context"], r["reason"])
        key = (tid, et, reason)
        agg[key] = agg.get(key, 0) + 1

    by_tenant: Dict[int, List[Tuple[str, str, int]]] = {}
    for (tid, et, reason), n in agg.items():
        by_tenant.setdefault(tid, []).append((et, reason, n))

    out: List[Dict[str, str]] = []
    for tid, items in by_tenant.items():
        items.sort(key=lambda x: x[2], reverse=True)
        for et, reason, n in items[:limit_per_tenant]:
            out.append({
                "tenant_id": str(tid),
                "event_type": et,
                "reason": reason,
                "n": str(n),
            })

    out.sort(key=lambda d: (int(d["tenant_id"]), d["event_type"], -int(d["n"])))
    return out


def _tenant_name_or_unknown(tenants: List[TenantInfo], tenant_id: int) -> str:
    """Fallback tenant_name='(unknown)' si client_id en PG sans tenant côté SQLite."""
    for t in tenants:
        if t.tenant_id == tenant_id:
            return t.name
    return "(unknown)"


def build_kpis(
    tenants: List[TenantInfo],
    calls_total: Dict[int, int],
    maps: Dict[str, Dict[int, int]],
    convert_map: Dict[int, Tuple[int, int]],
    start: str,
    end: str,
) -> List[TenantKPI]:
    # Inclure tous les tenant_ids : SQLite + PG (client_ids ivr_events sans tenant connu)
    all_tids = set(t.tenant_id for t in tenants) | set(calls_total.keys())
    for m in maps.values():
        all_tids |= set(m.keys())
    all_tids |= set(convert_map.keys())
    out: List[TenantKPI] = []
    for tid in sorted(all_tids):
        k = TenantKPI(
            week_start=start,
            week_end=end,
            tenant_id=tid,
            tenant_name=_tenant_name_or_unknown(tenants, tid),
            calls_total=calls_total.get(tid, 0),
        )

        k.bookings_confirmed = maps.get("bookings", {}).get(tid, 0)
        k.transfers = maps.get("transfers", {}).get(tid, 0)
        k.abandons = maps.get("abandons", {}).get(tid, 0)

        k.repeat_used_calls = maps.get("repeat", {}).get(tid, 0)
        k.yes_ambiguous_router_calls = maps.get("yes_ambiguous_router", {}).get(tid, 0)
        k.slot_refuse_pref_asked_calls = maps.get("slot_refuse_pref", {}).get(tid, 0)

        k.empty_message_calls = maps.get("empty_message", {}).get(tid, 0)
        k.anti_loop_calls = maps.get("anti_loop", {}).get(tid, 0)
        k.intent_router_calls = maps.get("intent_router", {}).get(tid, 0)
        k.cancel_done_calls = maps.get("cancel_done", {}).get(tid, 0)
        k.cancel_failed_calls = maps.get("cancel_failed", {}).get(tid, 0)

        num, den = convert_map.get(tid, (0, 0))
        k.convert_after_refuse_pref_num = num
        k.convert_after_refuse_pref_den = den
        k.convert_after_refuse_pref_rate = _safe_rate(num, den)

        k.transfer_rate = _safe_rate(k.transfers, k.calls_total)
        k.abandon_rate = _safe_rate(k.abandons, k.calls_total)
        k.booking_rate = _safe_rate(k.bookings_confirmed, k.calls_total)
        k.repeat_rate = _safe_rate(k.repeat_used_calls, k.calls_total)
        k.yes_ambiguous_router_rate = _safe_rate(k.yes_ambiguous_router_calls, k.calls_total)
        k.slot_refuse_pref_rate = _safe_rate(k.slot_refuse_pref_asked_calls, k.calls_total)

        out.append(k)

    out.sort(key=lambda x: x.tenant_id)
    return out


def write_kpi_csv(rows: List[TenantKPI], out_path: str) -> None:
    fieldnames = [
        "week_start", "week_end",
        "tenant_id", "tenant_name",
        "calls_total",
        "bookings_confirmed", "booking_rate",
        "transfers", "transfer_rate",
        "abandons", "abandon_rate",
        "repeat_used_calls", "repeat_rate",
        "yes_ambiguous_router_calls", "yes_ambiguous_router_rate",
        "slot_refuse_pref_asked_calls", "slot_refuse_pref_rate",
        "convert_after_refuse_pref_num", "convert_after_refuse_pref_den", "convert_after_refuse_pref_rate",
        "empty_message_calls",
        "anti_loop_calls",
        "intent_router_calls",
        "cancel_done_calls",
        "cancel_failed_calls",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({
                "week_start": r.week_start,
                "week_end": r.week_end,
                "tenant_id": r.tenant_id,
                "tenant_name": r.tenant_name,
                "calls_total": r.calls_total,
                "bookings_confirmed": r.bookings_confirmed,
                "booking_rate": round(r.booking_rate, 4),
                "transfers": r.transfers,
                "transfer_rate": round(r.transfer_rate, 4),
                "abandons": r.abandons,
                "abandon_rate": round(r.abandon_rate, 4),
                "repeat_used_calls": r.repeat_used_calls,
                "repeat_rate": round(r.repeat_rate, 4),
                "yes_ambiguous_router_calls": r.yes_ambiguous_router_calls,
                "yes_ambiguous_router_rate": round(r.yes_ambiguous_router_rate, 4),
                "slot_refuse_pref_asked_calls": r.slot_refuse_pref_asked_calls,
                "slot_refuse_pref_rate": round(r.slot_refuse_pref_rate, 4),
                "convert_after_refuse_pref_num": r.convert_after_refuse_pref_num,
                "convert_after_refuse_pref_den": r.convert_after_refuse_pref_den,
                "convert_after_refuse_pref_rate": round(r.convert_after_refuse_pref_rate, 4),
                "empty_message_calls": r.empty_message_calls,
                "anti_loop_calls": r.anti_loop_calls,
                "intent_router_calls": r.intent_router_calls,
                "cancel_done_calls": r.cancel_done_calls,
                "cancel_failed_calls": r.cancel_failed_calls,
            })


def build_digest_rows(
    rows: List[TenantKPI],
    details: List[Dict[str, str]],
    start: str,
    end: str,
) -> List[Dict[str, str]]:
    """
    Résumé client : 1 ligne par tenant.
    top_reason_1 = première raison (highest n) de recovery_step/intent_router.
    """
    # top reason par tenant (premier de details trié par tenant + n desc)
    by_tenant: Dict[int, str] = {}
    for d in details:
        tid = int(d["tenant_id"])
        if tid not in by_tenant:
            by_tenant[tid] = d["reason"]
    out: List[Dict[str, str]] = []
    for r in rows:
        top = by_tenant.get(r.tenant_id, "")
        out.append({
            "week_start": start,
            "week_end": end,
            "tenant_id": str(r.tenant_id),
            "tenant_name": r.tenant_name,
            "calls_total": str(r.calls_total),
            "booking_rate": f"{r.booking_rate:.2%}",
            "transfer_rate": f"{r.transfer_rate:.2%}",
            "abandon_rate": f"{r.abandon_rate:.2%}",
            "convert_after_refuse_pref_rate": f"{r.convert_after_refuse_pref_rate:.2%}" if r.convert_after_refuse_pref_den else "N/A",
            "top_reason_1": top or "(none)",
        })
    return out


def write_digest_csv(
    digest_rows: List[Dict[str, str]],
    out_path: str,
) -> None:
    fieldnames = [
        "week_start", "week_end",
        "tenant_id", "tenant_name",
        "calls_total",
        "booking_rate", "transfer_rate", "abandon_rate",
        "convert_after_refuse_pref_rate",
        "top_reason_1",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(digest_rows)


def write_details_csv(
    details: List[Dict[str, str]],
    out_path: str,
    start: str,
    end: str,
) -> None:
    fieldnames = ["week_start", "week_end", "tenant_id", "event_type", "reason", "n"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for d in details:
            w.writerow({
                "week_start": start,
                "week_end": end,
                **d,
            })


def _check_pg_lag(conn_ivr: Any, lag_alert_sec: int = 300) -> None:
    """Lag monitor : si max(created_at) retard > lag_alert_sec → log [PG_LAG]."""
    try:
        with conn_ivr.cursor() as cur:
            cur.execute(
                "SELECT EXTRACT(EPOCH FROM (NOW() - MAX(created_at))) AS lag_sec FROM ivr_events"
            )
            row = cur.fetchone()
        if row and row.get("lag_sec") is not None:
            lag = float(row["lag_sec"])
            if lag > lag_alert_sec:
                print(f"[PG_LAG] lag_seconds={lag:.0f} (dual-write may be broken)")
    except Exception as e:
        print(f"[PG_LAG] check failed: {e}")


def main() -> None:
    args = parse_args()

    if args.last_week:
        start_str, end_str = _last_week_iso()
        start = _parse_dt(start_str)
        end = _parse_dt(end_str)
    else:
        if not args.start or not args.end:
            print("Error: --start and --end required, or use --last-week")
            sys.exit(1)
        start = _parse_dt(args.start)
        end = _parse_dt(args.end)

    conn_sqlite = _connect_sqlite(args.db)
    use_pg = bool(args.db_pg_url and args.db_pg_url.strip())
    if use_pg:
        conn_ivr = _connect_pg(args.db_pg_url.strip())
        is_pg = True
        _check_pg_lag(conn_ivr)
    else:
        conn_ivr = conn_sqlite
        is_pg = False

    tenants = fetch_tenants(conn_sqlite, include_inactive=args.include_inactive, use_pg=use_pg)
    if not tenants:
        print("No tenants found. Ensure tenants table exists and has rows.")
        return

    calls_total = fetch_calls_total(conn_ivr, start, end, is_pg)

    maps = {
        "bookings": fetch_event_calls(conn_ivr, start, end, BOOKING_CONFIRMED_EVENTS, is_pg),
        "transfers": fetch_event_calls(conn_ivr, start, end, TRANSFER_EVENTS, is_pg),
        "abandons": fetch_event_calls(conn_ivr, start, end, ABANDON_EVENTS, is_pg),
        "repeat": fetch_event_calls(conn_ivr, start, end, REPEAT_EVENTS, is_pg),
        "yes_ambiguous_router": fetch_event_calls(
            conn_ivr, start, end, YES_AMBIGUOUS_ROUTER_EVENTS, is_pg
        ),
        "slot_refuse_pref": fetch_event_calls(
            conn_ivr, start, end, SLOT_REFUSE_PREF_EVENTS, is_pg
        ),
        "empty_message": fetch_event_calls(conn_ivr, start, end, EMPTY_MESSAGE_EVENTS, is_pg),
        "anti_loop": fetch_event_calls(conn_ivr, start, end, ANTI_LOOP_EVENTS, is_pg),
        "intent_router": fetch_event_calls(conn_ivr, start, end, INTENT_ROUTER_EVENTS, is_pg),
        "cancel_done": fetch_event_calls(conn_ivr, start, end, CANCEL_DONE_EVENTS, is_pg),
        "cancel_failed": fetch_event_calls(conn_ivr, start, end, CANCEL_FAILED_EVENTS, is_pg),
    }

    convert_map = fetch_convert_after_refuse_pref(conn_ivr, start, end, is_pg)
    rows = build_kpis(tenants, calls_total, maps, convert_map, start, end)

    s = start.replace(":", "").replace(" ", "_").replace("-", "")
    e = end.replace(":", "").replace(" ", "_").replace("-", "")
    out_dir = args.out_dir.rstrip("/")
    os.makedirs(out_dir, exist_ok=True)

    kpi_path = f"{out_dir}/kpi_weekly_{s}_{e}.csv"
    details_path = f"{out_dir}/kpi_weekly_details_{s}_{e}.csv"
    digest_path = f"{out_dir}/kpi_weekly_digest_{s}_{e}.csv"

    # Verrou anti double-exécution (idempotence cron)
    if not args.force and os.path.isfile(kpi_path) and os.path.isfile(details_path):
        print(f"Skip (already exists): {kpi_path} + {details_path}. Use --force to override.")
        return

    write_kpi_csv(rows, kpi_path)

    details = fetch_details_top_reasons(
        conn_ivr, start, end, is_pg, limit_per_tenant=args.details_limit
    )
    write_details_csv(details, details_path, start, end)

    digest_rows = build_digest_rows(rows, details, start, end)
    write_digest_csv(digest_rows, digest_path)

    if use_pg:
        conn_ivr.close()
    print(f"Wrote KPI CSV: {kpi_path} (tenants={len(rows)})")
    print(f"Wrote details CSV: {details_path} (rows={len(details)})")
    print(f"Wrote digest CSV: {digest_path} (tenants={len(digest_rows)})")


if __name__ == "__main__":
    main()
