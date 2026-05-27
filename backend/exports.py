"""
Exports CSV pour dashboards admin et client.

Source unique pour eviter la duplication entre routes admin et tenant.
- export_calls_csv() : appels d'un tenant (ou tous tenants si admin)
- export_bookings_csv() : RDV confirmes (events booking_confirmed)

Format : CSV BOM UTF-8 + delimiteur `;` (Excel-friendly FR par defaut, configurable).
Streaming via StreamingResponse pour eviter de tout charger en memoire.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Iterator, List, Mapping, Optional

logger = logging.getLogger(__name__)

# Caracteres de fin de ligne CSV Windows-friendly (Excel attend \r\n)
CSV_LINETERMINATOR = "\r\n"
# Delimiteur par defaut : `;` (Excel FR ouvre directement sans wizard d'import)
CSV_DELIMITER_DEFAULT = ";"
# BOM UTF-8 prefixe pour qu'Excel reconnaisse l'encoding tout seul
UTF8_BOM = "\ufeff"


def _safe_filename(prefix: str, tenant_id: Optional[int], days: int) -> str:
    """Genere un nom de fichier sans caracteres dangereux."""
    today = datetime.utcnow().strftime("%Y%m%d")
    parts = [prefix, today, f"{days}j"]
    if tenant_id is not None:
        parts.append(f"tenant{tenant_id}")
    base = "_".join(parts)
    # garde-fou : strip tout sauf alphanum + - _
    base = re.sub(r"[^a-zA-Z0-9_-]", "", base)
    return f"{base}.csv"


def _format_iso_to_local(value: Any) -> str:
    """Convertit un str/datetime en `YYYY-MM-DD HH:MM:SS` (UTC). Vide si None."""
    if value is None or value == "":
        return ""
    if hasattr(value, "strftime"):
        try:
            return value.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(value)
    s = str(value).replace("T", " ")
    # tronque "2026-05-09 12:34:56Z" / ".123" -> "2026-05-09 12:34:56"
    if "+" in s:
        s = s.split("+")[0]
    if "Z" in s:
        s = s.replace("Z", "")
    if "." in s:
        s = s.split(".")[0]
    return s.strip()


def _format_duration(seconds: Optional[int]) -> str:
    """Format `Mm SSs` ou `Hh MMm` selon longueur. Vide si None."""
    if seconds is None or seconds == "":
        return ""
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return ""
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60:02d}s"
    return f"{s // 3600}h {(s % 3600) // 60:02d}m"


def _result_label_fr(result: str) -> str:
    return {
        "rdv": "RDV pris",
        "transfer": "Transfert humain",
        "abandoned": "Abandon",
        "error": "Erreur",
        "other": "Autre",
    }.get((result or "").lower(), (result or "").capitalize())


def _csv_writer(buf: io.StringIO, delimiter: str) -> "csv.writer":
    return csv.writer(
        buf,
        delimiter=delimiter,
        quotechar='"',
        quoting=csv.QUOTE_MINIMAL,
        lineterminator=CSV_LINETERMINATOR,
    )


def stream_csv(
    rows: Iterable[Mapping[str, Any]],
    headers: List[str],
    columns: List[str],
    delimiter: str = CSV_DELIMITER_DEFAULT,
) -> Iterator[bytes]:
    """
    Genere un flux CSV depuis un iterable de dicts.

    `headers` = libelles d'en-tete (1 par colonne).
    `columns` = cles a piocher dans chaque dict, dans le meme ordre que headers.

    Stream pour gros volumes : on yield par chunks de ~50 lignes.
    """
    buf = io.StringIO()
    writer = _csv_writer(buf, delimiter)

    # BOM + en-tetes
    buf.write(UTF8_BOM)
    writer.writerow(headers)
    yield buf.getvalue().encode("utf-8")
    buf.seek(0)
    buf.truncate()

    chunk_size = 50
    rows_in_chunk = 0
    for row in rows:
        line = [_csv_value(row.get(c)) for c in columns]
        writer.writerow(line)
        rows_in_chunk += 1
        if rows_in_chunk >= chunk_size:
            yield buf.getvalue().encode("utf-8")
            buf.seek(0)
            buf.truncate()
            rows_in_chunk = 0

    # Flush final
    if rows_in_chunk > 0:
        yield buf.getvalue().encode("utf-8")


def _csv_value(v: Any) -> str:
    """Convertit une valeur en string CSV-safe (None -> '', booleens -> oui/non)."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "oui" if v else "non"
    if isinstance(v, (int, float)):
        return str(v)
    return str(v)


# =============================================================================
# Calls CSV
# =============================================================================

CALLS_HEADERS = [
    "Date",
    "Heure",
    "Tenant",
    "Tenant ID",
    "Numero appelant",
    "Resultat",
    "Duree",
    "Duree (s)",
    "Last event",
    "Call ID",
]
CALLS_COLUMNS = [
    "_date",
    "_time",
    "tenant_name",
    "tenant_id",
    "customer_number",
    "_result_label",
    "_duration_label",
    "duration_sec",
    "last_event",
    "call_id",
]


def _enrich_call_row(row: Mapping[str, Any]) -> dict:
    """Ajoute les colonnes derivees `_date`, `_time`, `_result_label`, `_duration_label`."""
    started = row.get("started_at") or row.get("last_event_at") or ""
    iso = _format_iso_to_local(started)
    date_part, _, time_part = iso.partition(" ")
    enriched = dict(row)
    enriched["_date"] = date_part
    enriched["_time"] = time_part
    enriched["_result_label"] = _result_label_fr(row.get("result") or "")
    enriched["_duration_label"] = _format_duration(row.get("duration_sec"))
    return enriched


def build_calls_csv_response(
    items: Iterable[Mapping[str, Any]],
    *,
    tenant_id: Optional[int],
    days: int,
    delimiter: str = CSV_DELIMITER_DEFAULT,
):
    """
    Construit une `StreamingResponse` FastAPI prete a retourner.

    Importe FastAPI ici pour permettre l'import du module sans dependance forte.
    """
    from fastapi.responses import StreamingResponse

    enriched = (_enrich_call_row(r) for r in items)
    fname = _safe_filename("appels", tenant_id, days)
    return StreamingResponse(
        stream_csv(enriched, CALLS_HEADERS, CALLS_COLUMNS, delimiter=delimiter),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{fname}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


# =============================================================================
# Bookings CSV (RDV confirmes via le bot vocal — events ivr_events)
# =============================================================================

BOOKINGS_HEADERS = [
    "Date prise",
    "Heure prise",
    "Tenant",
    "Tenant ID",
    "Patient",
    "Telephone",
    "Date RDV",
    "Heure RDV",
    "Motif",
    "Statut",
    "Source",
    "Call ID",
]
BOOKINGS_COLUMNS = [
    "_date_taken",
    "_time_taken",
    "tenant_name",
    "tenant_id",
    "patient_name",
    "patient_phone",
    "_date_rdv",
    "_time_rdv",
    "motif",
    "status",
    "source",
    "call_id",
]


def _enrich_booking_row(row: Mapping[str, Any]) -> dict:
    """Ajoute colonnes derivees pour les RDV."""
    taken = row.get("created_at") or ""
    iso_taken = _format_iso_to_local(taken)
    date_taken, _, time_taken = iso_taken.partition(" ")
    rdv_dt = row.get("rdv_at") or row.get("slot_label") or ""
    iso_rdv = _format_iso_to_local(rdv_dt)
    date_rdv, _, time_rdv = iso_rdv.partition(" ")
    enriched = dict(row)
    enriched["_date_taken"] = date_taken
    enriched["_time_taken"] = time_taken
    enriched["_date_rdv"] = date_rdv if date_rdv else (rdv_dt if not iso_rdv else "")
    enriched["_time_rdv"] = time_rdv
    return enriched


def build_bookings_csv_response(
    items: Iterable[Mapping[str, Any]],
    *,
    tenant_id: Optional[int],
    days: int,
    delimiter: str = CSV_DELIMITER_DEFAULT,
):
    from fastapi.responses import StreamingResponse

    enriched = (_enrich_booking_row(r) for r in items)
    fname = _safe_filename("rdv", tenant_id, days)
    return StreamingResponse(
        stream_csv(enriched, BOOKINGS_HEADERS, BOOKINGS_COLUMNS, delimiter=delimiter),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{fname}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


def fetch_bookings_from_pg(
    *,
    tenant_id: Optional[int],
    days: int,
    limit: int = 5000,
) -> List[dict]:
    """
    Recupere les RDV pris (events `booking_confirmed` dans ivr_events).

    Source primaire : ivr_events.event = 'booking_confirmed'
    On joint sur call_sessions pour recuperer le numero patient si dispo.

    Retourne [] si PG indispo.
    """
    try:
        from backend.pg_pool import pg_connection
    except Exception:
        return []

    now = datetime.utcnow()
    start = (now - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
    end = now.strftime("%Y-%m-%d %H:%M:%S")

    params: List[Any] = [start, end]
    tenant_filter = ""
    if tenant_id is not None:
        tenant_filter = " AND ie.client_id = %s"
        params.append(tenant_id)
    params.append(limit)

    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT ie.client_id AS tenant_id,
                           ie.call_id,
                           ie.created_at,
                           ie.event,
                           ie.meta_json,
                           cs.customer_number AS patient_phone
                    FROM ivr_events ie
                    LEFT JOIN call_sessions cs
                      ON cs.tenant_id = ie.client_id AND cs.call_id = ie.call_id
                    WHERE ie.event = 'booking_confirmed'
                      AND ie.created_at >= %s AND ie.created_at <= %s
                      {tenant_filter}
                    ORDER BY ie.created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                rows = cur.fetchall() or []
                out: List[dict] = []
                for r in rows:
                    d = dict(r) if hasattr(r, "items") else {
                        "tenant_id": r[0], "call_id": r[1], "created_at": r[2],
                        "event": r[3], "meta_json": r[4], "patient_phone": r[5],
                    }
                    meta = d.get("meta_json") or {}
                    if isinstance(meta, str):
                        try:
                            import json as _json
                            meta = _json.loads(meta)
                        except Exception:
                            meta = {}
                    out.append({
                        "tenant_id": d.get("tenant_id"),
                        "call_id": d.get("call_id") or "",
                        "created_at": d.get("created_at"),
                        "patient_name": meta.get("patient_name") or meta.get("name") or "",
                        "patient_phone": d.get("patient_phone") or meta.get("phone") or "",
                        "rdv_at": meta.get("rdv_at") or meta.get("start") or meta.get("slot") or "",
                        "motif": meta.get("motif") or meta.get("reason") or "",
                        "status": "confirme",
                        "source": "appel",
                    })
                return out
    except Exception as e:
        logger.warning("fetch_bookings_from_pg failed: %s", e)
        return []
