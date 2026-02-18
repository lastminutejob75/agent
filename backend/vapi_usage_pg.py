# backend/vapi_usage_pg.py
"""
Persistance conso Vapi (webhook end-of-call-report).
Vapi = source de vérité durée/coût ; table vapi_call_usage (migration 009).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _pg_url() -> Optional[str]:
    return os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")


def upsert_vapi_call_usage(
    tenant_id: int,
    vapi_call_id: str,
    *,
    started_at: Optional[datetime] = None,
    ended_at: Optional[datetime] = None,
    duration_sec: Optional[float] = None,
    cost_usd: Optional[float] = None,
    cost_currency: str = "USD",
    costs_json: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Upsert une ligne vapi_call_usage (ON CONFLICT DO UPDATE).
    Retourne True si succès.
    """
    url = _pg_url()
    if not url or not (vapi_call_id or "").strip():
        return False
    vapi_call_id = (vapi_call_id or "").strip()
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM vapi_call_usage WHERE tenant_id = %s AND vapi_call_id = %s",
                    (tenant_id, vapi_call_id),
                )
                existed = cur.rowcount and cur.fetchone()
                cur.execute(
                    """
                    INSERT INTO vapi_call_usage
                    (tenant_id, vapi_call_id, started_at, ended_at, duration_sec, cost_usd, cost_currency, costs_json, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (tenant_id, vapi_call_id) DO UPDATE SET
                        started_at = COALESCE(EXCLUDED.started_at, vapi_call_usage.started_at),
                        ended_at = COALESCE(EXCLUDED.ended_at, vapi_call_usage.ended_at),
                        duration_sec = COALESCE(EXCLUDED.duration_sec, vapi_call_usage.duration_sec),
                        cost_usd = COALESCE(EXCLUDED.cost_usd, vapi_call_usage.cost_usd),
                        cost_currency = EXCLUDED.cost_currency,
                        costs_json = COALESCE(EXCLUDED.costs_json, vapi_call_usage.costs_json),
                        updated_at = now()
                    """,
                    (
                        tenant_id,
                        vapi_call_id,
                        started_at,
                        ended_at,
                        float(duration_sec) if duration_sec is not None else None,
                        float(cost_usd) if cost_usd is not None else None,
                        cost_currency or "USD",
                        costs_json,
                    ),
                )
                conn.commit()
                if existed:
                    logger.info("VAPI_USAGE_UPDATED existing row tenant_id=%s vapi_call_id=%s", tenant_id, vapi_call_id[:32])
                else:
                    logger.info("VAPI_USAGE_INSERTED tenant_id=%s vapi_call_id=%s", tenant_id, vapi_call_id[:32])
        return True
    except Exception as e:
        if "does not exist" in str(e).lower() or "vapi_call_usage" in str(e):
            logger.warning("vapi_call_usage table missing (run migration 009): %s", e)
        else:
            logger.warning("vapi_usage upsert failed: %s", e)
        return False


def _parse_iso_or_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.utcfromtimestamp(value)
        except Exception:
            return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")[:30])
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:26].rstrip("Z"), fmt.replace(".%fZ", "").replace("Z", ""))
        except Exception:
            continue
    return None


def _sum_cost_usd(costs: List[Dict[str, Any]]) -> float:
    total = 0.0
    for c in (costs or []):
        if not isinstance(c, dict):
            continue
        val = None
        for key in ("cost", "amount", "value"):
            if key in c:
                try:
                    val = float(c[key])
                    break
                except (TypeError, ValueError):
                    pass
        if val is not None:
            total += val
        elif c:
            logger.warning("vapi cost item unknown schema (no cost/amount/value): keys=%s", list(c.keys())[:8])
    return round(total, 4)


def _get_any(d: dict, keys: List[str], default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def ingest_end_of_call_report(payload: dict) -> bool:
    """
    Parse un payload webhook Vapi message.type === "end-of-call-report"
    (ou message contenant l'objet call avec startedAt, endedAt, costs).
    Retrouve tenant_id via DID (normalisé sip: / E.164) → tenant_routing.
    Upsert vapi_call_usage. Retourne True si upsert OK.
    """
    call = payload.get("call") or (payload.get("message") or {}).get("call") or {}
    vapi_call_id = (
        _get_any(call, ["id", "callId"])
        or payload.get("callId")
        or ""
    )
    if isinstance(vapi_call_id, dict):
        vapi_call_id = ""
    vapi_call_id = str(vapi_call_id).strip()
    if not vapi_call_id:
        logger.debug("end-of-call-report: no call id in payload")
        return False

    from backend.tenant_routing import extract_to_number_from_vapi_payload, resolve_tenant_id_from_vocal_call
    to_number = extract_to_number_from_vapi_payload(payload)
    if to_number and isinstance(to_number, str):
        to_number = to_number.replace("sip:", "").strip() or to_number
    tenant_id, _ = resolve_tenant_id_from_vocal_call(to_number or "", channel="vocal")
    if tenant_id is None:
        logger.debug("end-of-call-report: could not resolve tenant for call_id=%s", vapi_call_id[:24])
        return False

    started_at = _parse_iso_or_ts(_get_any(call, ["startedAt", "started_at", "startTime", "started_time"]))
    ended_at = _parse_iso_or_ts(_get_any(call, ["endedAt", "ended_at", "endTime", "ended_time"]))
    duration_sec = None
    raw_duration = _get_any(call, ["duration", "durationSec", "duration_sec"])
    if raw_duration is not None:
        try:
            duration_sec = float(raw_duration)
            if duration_sec > 24 * 3600 and isinstance(raw_duration, (int, float)) and raw_duration == int(raw_duration):
                duration_sec = duration_sec / 1000.0
        except (TypeError, ValueError):
            pass
    if duration_sec is None and started_at and ended_at:
        duration_sec = (ended_at - started_at).total_seconds()

    costs = call.get("costs") or call.get("cost") or []
    if not isinstance(costs, list):
        costs = [costs] if costs else []
    cost_usd = _sum_cost_usd(costs)
    costs_json = None
    if costs:
        costs_json = {"items": costs}

    return upsert_vapi_call_usage(
        tenant_id=tenant_id,
        vapi_call_id=vapi_call_id,
        started_at=started_at,
        ended_at=ended_at,
        duration_sec=duration_sec,
        cost_usd=cost_usd if cost_usd else None,
        costs_json=costs_json,
    )
