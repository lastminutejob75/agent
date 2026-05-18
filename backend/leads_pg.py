# backend/leads_pg.py — Pre-onboarding leads (table pre_onboarding_leads)
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _safe_lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_calls_volume(raw: Any) -> str:
    value = str(raw or "").strip()
    if value in {"<10", "10-25", "25-50", "50-100", "100+"}:
        return value
    return "unknown"


def _compute_lead_score(lead: Dict[str, Any]) -> int:
    score = 0
    calls = _normalize_calls_volume(lead.get("daily_call_volume"))
    if calls == "100+":
        score += 25
    elif calls == "50-100":
        score += 20
    elif calls == "25-50":
        score += 12
    elif calls == "10-25":
        score += 6

    specialty = _safe_lower(lead.get("medical_specialty"))
    if specialty in {"centre_medical", "clinique_privee"}:
        score += 10

    assistant_name = str(lead.get("assistant_name") or "").strip().lower()
    if not assistant_name or assistant_name in {"none", "non", "sans", "n/a"}:
        score += 15

    pain = _safe_lower(lead.get("primary_pain_point"))
    if any(key in pain for key in ("appel", "interruption", "débord", "debord", "secrétariat", "secretariat")):
        score += 10

    source = _safe_lower(lead.get("source"))
    if source in {"landing_create_assistant", "landing_cta", "create_assistant"}:
        score += 10

    if str(lead.get("medical_specialty_label") or "").strip():
        score += 5
    if str(lead.get("callback_phone") or "").strip():
        score += 5
    return max(0, min(100, int(score)))


def _derive_priority(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _derive_segment(lead: Dict[str, Any], score: int) -> str:
    calls = _normalize_calls_volume(lead.get("daily_call_volume"))
    specialty = _safe_lower(lead.get("medical_specialty"))
    assistant_name = str(lead.get("assistant_name") or "").strip().lower()
    if calls == "100+" or specialty in {"centre_medical", "clinique_privee"}:
        return "grand_account"
    if not assistant_name or assistant_name in {"none", "non", "sans", "n/a"}:
        return "without_assistant"
    if specialty in {"medecin_generaliste", "dentiste", "kinesitherapeute", "infirmier_liberal"} and score < 70:
        return "solo_practitioner"
    return "standard"


def _source_detail(source: str) -> str:
    mapping = {
        "landing_create_assistant": "Créer mon assistant",
        "landing_cta": "Formulaire landing",
        "linkedin": "LinkedIn",
        "manual": "Saisie manuelle",
        "recommendation": "Recommandation",
    }
    return mapping.get(source, source or "Inconnu")


def _lead_display_fields(lead: Dict[str, Any]) -> Dict[str, Any]:
    email = str(lead.get("email") or "").strip()
    local = email.split("@")[0] if "@" in email else email
    cabinet_guess = " ".join([p.capitalize() for p in local.replace("+", " ").replace(".", " ").replace("-", " ").split()[:3]]).strip()
    cabinet_name = str(lead.get("cabinet_name") or "").strip() or (cabinet_guess if cabinet_guess else f"Cabinet {str(lead.get('id') or '')[:6]}")
    contact_name = str(lead.get("contact_name") or "").strip() or str(lead.get("assistant_name") or "").strip() or "Contact cabinet"
    specialty_label = str(lead.get("medical_specialty_label") or "").strip() or str(lead.get("medical_specialty") or "").strip() or "Cabinet médical"
    city = str(lead.get("city") or "").strip()
    return {
        "cabinet_name": cabinet_name,
        "contact_name": contact_name,
        "contact_role": str(lead.get("contact_role") or "").strip(),
        "profession": specialty_label,
        "specialty": specialty_label,
        "city": city,
    }


def _enrich_lead(lead: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(lead)
    score = _compute_lead_score(row)
    priority = _derive_priority(score)
    segment = _derive_segment(row, score)
    source = _safe_lower(row.get("source"))
    row.update(_lead_display_fields(row))
    row["score"] = score
    row["priority"] = priority
    row["segment"] = segment
    row["source_detail"] = _source_detail(source)
    row["calls_per_day"] = _normalize_calls_volume(row.get("daily_call_volume"))
    row["status_label"] = {
        "new": "Nouveau",
        "contacted": "Contacté",
        "interested": "Intéressé",
        "demo_scheduled": "Démo prévue",
        "trial_offered": "Essai proposé",
        "trial_started": "Essai gratuit",
        "converted": "Converti",
        "lost": "Perdu",
        "later": "À relancer plus tard",
    }.get(_safe_lower(row.get("status")), str(row.get("status") or "Nouveau").strip().capitalize())
    return row


def _sort_rows(rows: List[Dict[str, Any]], sort: str) -> List[Dict[str, Any]]:
    mode = _safe_lower(sort or "created_desc")
    if mode == "score_desc":
        return sorted(rows, key=lambda r: int(r.get("score") or 0), reverse=True)
    if mode == "calls_desc":
        order = {"100+": 5, "50-100": 4, "25-50": 3, "10-25": 2, "<10": 1, "unknown": 0}
        return sorted(rows, key=lambda r: order.get(str(r.get("calls_per_day") or "unknown"), 0), reverse=True)
    if mode in {"next_action_asc", "next_asc"}:
        return sorted(rows, key=lambda r: str(r.get("follow_up_at") or "9999-12-31T00:00:00Z"))
    if mode == "name_asc":
        return sorted(rows, key=lambda r: _safe_lower(r.get("cabinet_name")))
    return sorted(rows, key=lambda r: str(r.get("created_at") or ""), reverse=True)


def _pipeline_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"all": len(rows)}
    for key in ("new", "to_contact", "contacted", "demo_scheduled", "trial_started", "converted", "lost"):
        counts[key] = 0
    for row in rows:
        st = _safe_lower(row.get("status"))
        if st == "new":
            counts["new"] += 1
            counts["to_contact"] += 1
        elif st in {"contacted", "interested"}:
            counts["contacted"] += 1
        elif st == "demo_scheduled":
            counts["demo_scheduled"] += 1
        elif st in {"trial_offered", "trial_started"}:
            counts["trial_started"] += 1
        elif st == "converted":
            counts["converted"] += 1
        elif st == "lost":
            counts["lost"] += 1
    return counts


def _get_conn():
    import psycopg
    from psycopg.rows import dict_row
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")
    if not url:
        raise RuntimeError("DATABASE_URL or PG_TENANTS_URL required for leads")
    return psycopg.connect(url, row_factory=dict_row)


def get_lead_by_email_for_upsert(email: str) -> Optional[Dict[str, Any]]:
    """
    Retourne un lead existant avec status in ('new','contacted') pour déduplication, ou None.
    Les leads converted/lost ne sont jamais retournés → jamais modifiés par un nouveau commit
    (pas d'écrasement d'historique ou de config).
    Si email vide, retourne None (pas de déduplication par email).
    """
    if not email or not (email or "").strip():
        return None
    email = (email or "").strip()
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, created_at, email, daily_call_volume, medical_specialty, medical_specialty_label, specialty_other, primary_pain_point, assistant_name, voice_gender,
                           opening_hours, wants_callback, callback_phone, callback_booking_date, callback_booking_slot, is_enterprise, source, status, notes, contacted_at, converted_at,
                           updated_at, last_submitted_at, max_daily_amplitude
                    FROM pre_onboarding_leads
                    WHERE LOWER(TRIM(email)) = LOWER(TRIM(%s)) AND status IN ('new', 'contacted')
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (email.strip(),),
                )
                row = cur.fetchone()
        return _row_to_lead(row) if row else None
    except Exception as e:
        logger.exception("get_lead_by_email_for_upsert failed: %s", e)
        return None


def upsert_lead(
    email: Optional[str],
    daily_call_volume: str,
    medical_specialty: str,
    primary_pain_point: str,
    assistant_name: str,
    voice_gender: str,
    opening_hours: Dict[str, Any],
    wants_callback: bool = False,
    callback_phone: Optional[str] = None,
    specialty_other: Optional[str] = None,
    medical_specialty_label: Optional[str] = None,
    source: str = "landing_cta",
) -> Optional[str]:
    """
    Si un lead existe déjà avec cet email et status in ('new','contacted') → UPDATE et retourne son id.
    Sinon INSERT et retourne le nouvel id. Évite les doublons quand un médecin refait le wizard.
    Si email vide/None (lead téléphone seul), pas de déduplication → insert.
    """
    is_enterprise = (daily_call_volume == "100+")
    existing = get_lead_by_email_for_upsert(email or "") if (email and (email or "").strip()) else None
    if existing:
        lead_id = existing["id"]
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    max_amp = compute_max_daily_amplitude(opening_hours)
                    cur.execute(
                        """
                        UPDATE pre_onboarding_leads
                        SET daily_call_volume = %s, medical_specialty = %s, medical_specialty_label = %s, primary_pain_point = %s, assistant_name = %s, voice_gender = %s,
                            opening_hours = %s::jsonb, wants_callback = %s, callback_phone = %s, specialty_other = %s, is_enterprise = %s, source = %s,
                            max_daily_amplitude = %s, updated_at = NOW(), last_submitted_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            daily_call_volume,
                            (medical_specialty or "").strip() or None,
                            (medical_specialty_label or "").strip() or None,
                            (primary_pain_point or "").strip() or None,
                            assistant_name.strip(),
                            voice_gender,
                            _json_dumps(opening_hours),
                            bool(wants_callback),
                            (callback_phone or "").strip() or None,
                            (specialty_other or "").strip() or None,
                            is_enterprise,
                            source,
                            max_amp,
                            lead_id,
                        ),
                    )
                conn.commit()
            return lead_id
        except Exception as e:
            logger.exception("upsert_lead update failed: %s", e)
            return None
    return insert_lead(
        email=(email or "").strip() or "",
        daily_call_volume=daily_call_volume,
        medical_specialty=medical_specialty,
        primary_pain_point=primary_pain_point,
        assistant_name=assistant_name,
        voice_gender=voice_gender,
        opening_hours=opening_hours,
        wants_callback=wants_callback,
        callback_phone=callback_phone,
        specialty_other=specialty_other,
        medical_specialty_label=medical_specialty_label,
        source=source,
    )


def insert_lead(
    email: str,  # peut être "" pour lead téléphone seul (colonne NOT NULL accepte '')
    daily_call_volume: str,
    medical_specialty: str,
    primary_pain_point: str,
    assistant_name: str,
    voice_gender: str,
    opening_hours: Dict[str, Any],
    wants_callback: bool = False,
    callback_phone: Optional[str] = None,
    specialty_other: Optional[str] = None,
    medical_specialty_label: Optional[str] = None,
    source: str = "landing_cta",
) -> Optional[str]:
    """Insert a new lead. Returns lead_id (uuid) or None on error."""
    try:
        lead_id = str(uuid.uuid4())
        max_amp = compute_max_daily_amplitude(opening_hours)
        with _get_conn() as conn:
            with conn.cursor() as cur:
                is_enterprise = (daily_call_volume == "100+")
                cur.execute(
                    """
                    INSERT INTO pre_onboarding_leads
                    (id, email, daily_call_volume, medical_specialty, medical_specialty_label, primary_pain_point, assistant_name, voice_gender, opening_hours, wants_callback, callback_phone, specialty_other, is_enterprise, source, status, last_submitted_at, updated_at, max_daily_amplitude)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, 'new', NOW(), NOW(), %s)
                    """,
                    (
                        lead_id,
                        (email or "").strip(),
                        daily_call_volume,
                        (medical_specialty or "").strip() or None,
                        (medical_specialty_label or "").strip() or None,
                        (primary_pain_point or "").strip() or None,
                        assistant_name.strip(),
                        voice_gender,
                        _json_dumps(opening_hours),
                        bool(wants_callback),
                        (callback_phone or "").strip() or None,
                        (specialty_other or "").strip() or None,
                        is_enterprise,
                        source,
                        max_amp,
                    ),
                )
            conn.commit()
        return lead_id
    except Exception as e:
        logger.exception("insert_lead failed: %s", e)
        return None


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


def _time_to_hours(t: str) -> float:
    """Parse HH:MM to decimal hours (e.g. 08:30 -> 8.5, 21:00 -> 21.0)."""
    if not t or not isinstance(t, str):
        return 0.0
    parts = (t.strip().split(":") + ["0"])[:2]
    try:
        h = int(parts[0].strip() or "0")
        m = int(parts[1].strip() or "0")
        return h + m / 60.0
    except (ValueError, TypeError):
        return 0.0


def compute_max_daily_amplitude(opening_hours: Optional[Dict[str, Any]]) -> Optional[float]:
    """
    Pour chaque jour ouvert: amplitude = end - start (heures).
    Retourne max(amplitudes) sur la semaine, ou None si aucun jour ouvert.
    """
    if not opening_hours or not isinstance(opening_hours, dict):
        return None
    day_keys_alt = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    amplitudes = []
    for i in range(7):
        key = str(i)
        slot = opening_hours.get(key) or opening_hours.get(
            (["lun", "mar", "mer", "jeu", "ven", "sam", "dim"][i])
        )
        if not slot and i < len(day_keys_alt):
            slot = opening_hours.get(day_keys_alt[i]) or opening_hours.get(day_keys_alt[i][:3])
        if not slot or not isinstance(slot, dict) or slot.get("closed"):
            continue
        start = (slot.get("start") or "").strip()
        end = (slot.get("end") or "").strip()
        if not start and not end:
            continue
        sh, eh = _time_to_hours(start), _time_to_hours(end)
        if eh > sh:
            amplitudes.append(eh - sh)
    return max(amplitudes) if amplitudes else None


def compute_amplitude_score(opening_hours: Optional[Dict[str, Any]]) -> int:
    """+20 si max_daily_amplitude >= 12h, +10 si >= 10h, sinon 0."""
    max_h = compute_max_daily_amplitude(opening_hours)
    if max_h is None:
        return 0
    if max_h >= 12:
        return 20
    if max_h >= 10:
        return 10
    return 0


def list_leads(
    status: Optional[str] = None,
    enterprise_only: Optional[bool] = None,
    limit: int = 200,
    search: Optional[str] = None,
    source: Optional[str] = None,
    priority: Optional[str] = None,
    segment: Optional[str] = None,
    sort: str = "created_desc",
    page: int = 1,
    follow_up_today: bool = False,
) -> Dict[str, Any]:
    """Liste leads avec filtres + enrichissement commercial (score/priorité/segment)."""
    where_parts = []
    params = []
    if status:
        where_parts.append("status = %s")
        params.append(status)
    if enterprise_only:
        where_parts.append("is_enterprise = true")
    if source:
        where_parts.append("source = %s")
        params.append(source)
    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    query_limit = max(200, min(max(1, int(limit or 200)) * 8, 5000))
    params.append(query_limit)

    def _normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for row in rows:
            d = _row_to_lead(row)
            d.setdefault("notes_log", "[]")
            d.setdefault("follow_up_at", None)
            out.append(_enrich_lead(d))
        return out

    normalized_rows: List[Dict[str, Any]] = []
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, created_at, email, daily_call_volume, medical_specialty, medical_specialty_label, specialty_other, primary_pain_point, assistant_name, voice_gender,
                           opening_hours, wants_callback, callback_phone, callback_booking_date, callback_booking_slot, is_enterprise, source, status, notes,
                           COALESCE(notes_log, '[]'::jsonb) AS notes_log, follow_up_at,
                           contacted_at, converted_at, updated_at, last_submitted_at, max_daily_amplitude
                    FROM pre_onboarding_leads
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()
        normalized_rows = _normalize_rows(rows)
    except Exception as e:
        logger.warning("list_leads full query failed (schema?): %s", e)
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT id, created_at, email, daily_call_volume, medical_specialty, medical_specialty_label, specialty_other, primary_pain_point, assistant_name, voice_gender,
                               opening_hours, wants_callback, callback_phone, callback_booking_date, callback_booking_slot, is_enterprise, source, status, notes,
                               contacted_at, converted_at, updated_at, last_submitted_at, max_daily_amplitude
                        FROM pre_onboarding_leads
                        {where_sql}
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        tuple(params),
                    )
                    rows = cur.fetchall()
            logger.info("list_leads: used minimal query (notes_log/follow_up_at may be missing)")
            normalized_rows = _normalize_rows(rows)
        except Exception as e2:
            logger.exception("list_leads minimal failed: %s", e2)
            normalized_rows = []

    q = _safe_lower(search)
    if q:
        normalized_rows = [
            row
            for row in normalized_rows
            if q in " ".join(
                [
                    _safe_lower(row.get("cabinet_name")),
                    _safe_lower(row.get("contact_name")),
                    _safe_lower(row.get("email")),
                    _safe_lower(row.get("callback_phone")),
                    _safe_lower(row.get("profession")),
                    _safe_lower(row.get("specialty")),
                    _safe_lower(row.get("city")),
                    _safe_lower(row.get("source")),
                    _safe_lower(row.get("source_detail")),
                    _safe_lower(row.get("primary_pain_point")),
                    _safe_lower(row.get("notes")),
                ]
            )
        ]

    if follow_up_today:
        from datetime import timedelta

        start_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_day = start_day + timedelta(days=1)
        kept = []
        for row in normalized_rows:
            raw = row.get("follow_up_at")
            if not raw:
                continue
            try:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if dt.tzinfo is not None:
                    dt = dt.astimezone().replace(tzinfo=None)
                if start_day <= dt < end_day:
                    kept.append(row)
            except Exception:
                continue
        normalized_rows = kept

    if priority:
        pr = _safe_lower(priority)
        normalized_rows = [row for row in normalized_rows if _safe_lower(row.get("priority")) == pr]

    if segment:
        seg = _safe_lower(segment)
        if seg == "with_assistant":
            normalized_rows = [row for row in normalized_rows if _safe_lower(row.get("segment")) in {"standard", "grand_account"}]
        else:
            normalized_rows = [row for row in normalized_rows if _safe_lower(row.get("segment")) == seg]

    sorted_rows = _sort_rows(normalized_rows, sort)
    total = len(sorted_rows)
    page_n = max(1, int(page or 1))
    lim = max(1, min(int(limit or 25), 500))
    start = (page_n - 1) * lim
    items = sorted_rows[start : start + lim]

    return {
        "items": items,
        "total": total,
        "page": page_n,
        "limit": lim,
        "pipeline": _pipeline_counts(sorted_rows),
    }


def lead_exists(lead_id: str) -> bool:
    """Vérifie l'existence d'un lead (requête minimale, robuste au schema)."""
    if not lead_id or not str(lead_id).strip():
        return False
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pre_onboarding_leads WHERE id = %s LIMIT 1", (str(lead_id).strip(),))
                return cur.fetchone() is not None
    except Exception as e:
        logger.warning("lead_exists failed: %s", e)
        return False


def _get_lead_full(lead_id: str) -> Optional[Dict[str, Any]]:
    """Requête complète (avec notes_log, follow_up_at). Peut échouer si migration 031 non appliquée."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, created_at, email, daily_call_volume, medical_specialty, medical_specialty_label, specialty_other, primary_pain_point, assistant_name, voice_gender,
                       opening_hours, wants_callback, callback_phone, callback_booking_date, callback_booking_slot, is_enterprise, source, status, notes,
                       COALESCE(notes_log, '[]'::jsonb) AS notes_log, follow_up_at,
                       tenant_id, contacted_at, converted_at, updated_at, last_submitted_at, max_daily_amplitude
                FROM pre_onboarding_leads
                WHERE id = %s
                """,
                (lead_id,),
            )
            row = cur.fetchone()
    return _row_to_lead(row) if row else None


def _get_lead_minimal(lead_id: str) -> Optional[Dict[str, Any]]:
    """Requête sans notes_log/follow_up_at (schema avant migration 031). Pour fallback."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, created_at, email, daily_call_volume, medical_specialty, medical_specialty_label, specialty_other, primary_pain_point, assistant_name, voice_gender,
                       opening_hours, wants_callback, callback_phone, callback_booking_date, callback_booking_slot, is_enterprise, source, status, notes,
                       tenant_id, contacted_at, converted_at, updated_at, last_submitted_at, max_daily_amplitude
                FROM pre_onboarding_leads
                WHERE id = %s
                """,
                (lead_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    d = _row_to_lead(row)
    if d is not None:
        d.setdefault("notes_log", "[]")
        d.setdefault("follow_up_at", None)
    return d


def get_lead(lead_id: str) -> Optional[Dict[str, Any]]:
    """Get one lead by id. Fallback sur requête minimale si schema incomplet (migration 031)."""
    if not lead_id or not str(lead_id).strip():
        return None
    lead_id = str(lead_id).strip()
    try:
        lead = _get_lead_full(lead_id)
        if lead is not None:
            return lead
    except Exception as e:
        logger.warning("get_lead full query failed (schema?): %s", e)
    try:
        lead = _get_lead_minimal(lead_id)
        if lead is not None:
            logger.info("get_lead: used minimal query (notes_log/follow_up_at may be missing)")
            return lead
    except Exception as e:
        logger.exception("get_lead minimal failed: %s", e)
    return None


def update_lead_callback_booking(
    lead_id: str,
    callback_booking_date: Optional[str],
    callback_booking_slot: Optional[str],
    callback_phone: Optional[str],
) -> bool:
    """Enregistre le créneau de rappel choisi (écran finalisation) et marque le lead comme contacté."""
    if not callback_booking_date or not callback_booking_slot:
        return False
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE pre_onboarding_leads
                    SET callback_booking_date = %s::date,
                        callback_booking_slot = %s,
                        callback_phone = COALESCE(NULLIF(TRIM(%s), ''), callback_phone),
                        status = CASE WHEN status = 'new' THEN 'contacted' ELSE status END,
                        contacted_at = COALESCE(contacted_at, NOW()),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (callback_booking_date, (callback_booking_slot or "").strip() or None, (callback_phone or "").strip() or None, lead_id),
                )
            conn.commit()
        return True
    except Exception as e:
        logger.exception("update_lead_callback_booking failed: %s", e)
        return False


def update_lead(
    lead_id: str,
    status: Optional[str] = None,
    notes: Optional[str] = None,
    notes_log: Optional[str] = None,
    follow_up_at: Optional[str] = None,
    tenant_id: Optional[int] = None,
) -> bool:
    """Update lead status, notes, notes_log, follow_up_at and/or tenant_id. Set contacted_at/converted_at when status changes."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                updates = []
                params = []
                if status is not None:
                    updates.append("status = %s")
                    params.append(status)
                    if status == "contacted":
                        updates.append("contacted_at = COALESCE(contacted_at, NOW())")
                    elif status == "converted":
                        updates.append("converted_at = COALESCE(converted_at, NOW())")
                if notes is not None:
                    updates.append("notes = %s")
                    params.append(notes)
                if notes_log is not None:
                    updates.append("notes_log = %s::jsonb")
                    params.append(notes_log)
                if follow_up_at is not None:
                    if follow_up_at.strip():
                        updates.append("follow_up_at = %s::timestamptz")
                        params.append(follow_up_at.strip())
                    else:
                        updates.append("follow_up_at = NULL")
                if tenant_id is not None:
                    updates.append("tenant_id = %s")
                    params.append(int(tenant_id))
                if not updates:
                    return True
                params.append(lead_id)
                cur.execute(
                    f"UPDATE pre_onboarding_leads SET {', '.join(updates)} WHERE id = %s",
                    params,
                )
            conn.commit()
        return True
    except Exception as e:
        logger.exception("update_lead failed: %s", e)
        return False


def count_new_leads() -> int:
    """Count leads with status = 'new' (for sidebar badge)."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS c FROM pre_onboarding_leads WHERE status = 'new'"
                )
                row = cur.fetchone()
        return int(row["c"]) if row else 0
    except Exception as e:
        logger.exception("count_new_leads failed: %s", e)
        return 0


def count_leads_total() -> int:
    """Compte total des leads (diagnostic). Retourne -1 si erreur."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM pre_onboarding_leads")
                row = cur.fetchone()
        return int(row["c"]) if row else 0
    except Exception as e:
        logger.warning("count_leads_total failed: %s", e)
        return -1


def leads_summary(period_days: int = 30) -> Dict[str, Any]:
    """KPI synthèse pour /admin/leads."""
    days = max(1, min(int(period_days or 30), 366))
    payload = list_leads(limit=5000, page=1, sort="created_desc")
    rows = payload.get("items") or []
    now = datetime.utcnow()
    cutoff = now.timestamp() - (days * 86400)
    recent = []
    for row in rows:
        created = row.get("created_at")
        try:
            ts = datetime.fromisoformat(str(created).replace("Z", "+00:00")).timestamp()
            if ts >= cutoff:
                recent.append(row)
        except Exception:
            recent.append(row)

    def _count_status(*statuses: str) -> int:
        wanted = {_safe_lower(s) for s in statuses if s}
        return sum(1 for row in recent if _safe_lower(row.get("status")) in wanted)

    scores = [int(row.get("score") or 0) for row in recent]
    return {
        "period": f"{days}d",
        "new_leads_count": _count_status("new"),
        "to_contact_count": _count_status("new"),
        "demo_scheduled_count": _count_status("demo_scheduled"),
        "trial_leads_count": _count_status("trial_offered", "trial_started"),
        "high_priority_count": sum(1 for row in recent if _safe_lower(row.get("priority")) == "high"),
        "average_score": int(round(sum(scores) / len(scores), 0)) if scores else 0,
        "converted_count": _count_status("converted"),
        "lost_count": _count_status("lost"),
        "conversion_rate": round((_count_status("converted") / len(recent)), 3) if recent else 0.0,
    }


def leads_stats(period_days: int = 30) -> Dict[str, Any]:
    """Stats conversion et breakdowns."""
    days = max(1, min(int(period_days or 30), 366))
    payload = list_leads(limit=5000, page=1, sort="created_desc")
    rows = payload.get("items") or []
    now = datetime.utcnow()
    cutoff = now.timestamp() - (days * 86400)
    recent = []
    for row in rows:
        created = row.get("created_at")
        try:
            ts = datetime.fromisoformat(str(created).replace("Z", "+00:00")).timestamp()
            if ts >= cutoff:
                recent.append(row)
        except Exception:
            recent.append(row)

    created_count = len(recent)
    converted_count = sum(1 for row in recent if _safe_lower(row.get("status")) == "converted")
    lost_count = sum(1 for row in recent if _safe_lower(row.get("status")) == "lost")

    by_source: Dict[str, Dict[str, int]] = {}
    by_status: Dict[str, int] = {}
    by_segment: Dict[str, int] = {}
    for row in recent:
        source = _safe_lower(row.get("source")) or "unknown"
        status = _safe_lower(row.get("status")) or "new"
        segment = _safe_lower(row.get("segment")) or "standard"
        by_status[status] = by_status.get(status, 0) + 1
        by_segment[segment] = by_segment.get(segment, 0) + 1
        src = by_source.setdefault(source, {"count": 0, "converted": 0})
        src["count"] += 1
        if status == "converted":
            src["converted"] += 1

    return {
        "period": f"{days}d",
        "created_count": created_count,
        "converted_count": converted_count,
        "lost_count": lost_count,
        "conversion_rate": round((converted_count / created_count), 3) if created_count else 0.0,
        "average_time_to_convert_days": None,
        "by_source": [
            {"source": source, "count": v["count"], "converted": v["converted"]}
            for source, v in sorted(by_source.items(), key=lambda it: it[1]["count"], reverse=True)
        ],
        "by_status": [
            {"status": status, "count": count}
            for status, count in sorted(by_status.items(), key=lambda it: it[1], reverse=True)
        ],
        "by_segment": [
            {"segment": segment, "count": count}
            for segment, count in sorted(by_segment.items(), key=lambda it: it[1], reverse=True)
        ],
    }


def _row_to_lead(r: Dict) -> Dict[str, Any]:
    out = dict(r)
    for key in ("created_at", "contacted_at", "converted_at", "updated_at", "last_submitted_at", "callback_booking_date", "follow_up_at"):
        if out.get(key) and hasattr(out[key], "isoformat"):
            out[key] = out[key].isoformat()
    return out
