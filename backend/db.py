# backend/db.py
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

DB_PATH = "agent.db"
logger = logging.getLogger(__name__)

SLOT_TIMES = [
    "08:00", "08:15", "08:30", "08:45",
    "09:00", "09:15", "09:30", "09:45",
    "10:00", "10:15", "10:30", "10:45",
    "11:00", "11:15", "11:30", "11:45",
    "14:00", "14:15", "14:30", "14:45",
    "15:00", "15:15", "15:30", "15:45",
    "16:00", "16:15", "16:30", "16:45",
    "17:00", "17:15", "17:30", "17:45",
]
TARGET_MIN_SLOTS = 240
MAX_DAYS_AHEAD = 60


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tenants_tables(conn: sqlite3.Connection) -> None:
    """Crée les tables tenants + tenant_config (feature flags par tenant)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            tenant_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            timezone TEXT DEFAULT 'Europe/Paris',
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenant_config (
            tenant_id INTEGER PRIMARY KEY,
            flags_json TEXT NOT NULL DEFAULT '{}',
            params_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tenant_status ON tenants(status)")

    # Migration: ajouter params_json si absente (schéma legacy)
    try:
        cur = conn.execute("PRAGMA table_info(tenant_config)")
        cols = [row[1] for row in cur.fetchall()]
        if "params_json" not in cols:
            conn.execute("ALTER TABLE tenant_config ADD COLUMN params_json TEXT NOT NULL DEFAULT '{}'")
    except Exception:
        pass

    # Seed minimal (INSERT OR IGNORE = ne pas écraser config existant)
    conn.execute("INSERT OR IGNORE INTO tenants (tenant_id, name) VALUES (1, 'DEFAULT')")
    conn.execute(
        "INSERT OR IGNORE INTO tenant_config (tenant_id, flags_json, params_json, updated_at) VALUES (1, '{}', '{}', datetime('now'))"
    )

    # tenant_routing (DID → tenant_id)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenant_routing (
            channel TEXT NOT NULL DEFAULT 'vocal',
            did_key TEXT NOT NULL,
            tenant_id INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (channel, did_key),
            FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tenant_routing_lookup ON tenant_routing(channel, did_key)")

    # Demandes de connexion agenda (logiciel métier)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agenda_contact_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            software TEXT NOT NULL,
            software_other TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
        )
    """)


def ensure_tenant_config() -> None:
    """Garantit que les tables tenants/tenant_config existent."""
    conn = get_conn()
    try:
        _ensure_tenants_tables(conn)
        conn.commit()
    finally:
        conn.close()


def _ensure_ivr_tables(conn: sqlite3.Connection) -> None:
    """Crée les tables ivr_events et calls si absentes (rapport quotidien IVR)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            call_id TEXT NOT NULL,
            outcome TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ivr_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            call_id TEXT,
            event TEXT NOT NULL,
            context TEXT,
            reason TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ivr_events_client_date ON ivr_events(client_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ivr_events_client_event_date ON ivr_events(client_id, event, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_calls_client_date ON calls(client_id, created_at)")


def _ensure_call_followups_table(conn: sqlite3.Connection) -> None:
    """Crée la table de suivi d'appels côté tenant si absente."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS call_followups (
            tenant_id INTEGER NOT NULL,
            call_id TEXT NOT NULL,
            followup_state TEXT NOT NULL DEFAULT 'new',
            notes TEXT,
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (tenant_id, call_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_call_followups_state ON call_followups(tenant_id, followup_state, updated_at)")


def _ensure_human_handoffs_table(conn: sqlite3.Connection) -> None:
    """Crée la table des transferts / rappels humains côté tenant."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS human_handoffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            call_id TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'vocal',
            reason TEXT NOT NULL,
            target TEXT NOT NULL,
            mode TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'normal',
            status TEXT NOT NULL DEFAULT 'callback_created',
            patient_phone TEXT,
            raw_name TEXT,
            validated_name TEXT,
            display_name TEXT,
            summary TEXT,
            transcript_excerpt TEXT,
            booking_start_iso TEXT,
            booking_end_iso TEXT,
            booking_motif TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            processed_at TEXT,
            UNIQUE (tenant_id, call_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_human_handoffs_tenant_created ON human_handoffs(tenant_id, created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_human_handoffs_tenant_status_created ON human_handoffs(tenant_id, status, created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_human_handoffs_tenant_target_status_created ON human_handoffs(tenant_id, target, status, created_at)"
    )


def _pg_events_url() -> Optional[str]:
    return os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")


def _should_use_pg_events_dual_write() -> bool:
    """
    Active l'écriture PG des ivr_events dès qu'une base PG événements est configurée.
    Cela évite de perdre les métadonnées de booking en prod si USE_PG_EVENTS
    n'a pas été explicitement activé alors que DATABASE_URL est bien présent.
    """
    try:
        from backend import config

        return bool(config.USE_PG_EVENTS or _pg_events_url())
    except Exception:
        return bool(_pg_events_url())


def _pg_table_exists(conn: Any, table_name: str) -> bool:
    """
    Vrai si la table existe déjà dans le schéma `public` du Postgres connecté.
    Utilise to_regclass() qui ne nécessite PAS le privilège CREATE.

    Important : permet aux helpers `_ensure_*_table_pg` de court-circuiter le
    CREATE TABLE IF NOT EXISTS quand le rôle DB n'a pas `CREATE ON SCHEMA public`
    (cas du rôle `uwi_app` en prod). Sinon PG renvoie 'permission denied' même
    si la table existe, et toutes les requêtes patient échouent silencieusement.
    """
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
            row = cur.fetchone()
            if isinstance(row, dict):
                return bool(next(iter(row.values())))
            return bool(row and row[0])
    except Exception:
        return False


def _ensure_call_followups_table_pg(conn: Any) -> None:
    if _pg_table_exists(conn, "call_followups"):
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS call_followups (
                tenant_id INTEGER NOT NULL,
                call_id TEXT NOT NULL,
                followup_state TEXT NOT NULL DEFAULT 'new',
                notes TEXT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (tenant_id, call_id)
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_call_followups_state
            ON call_followups (tenant_id, followup_state, updated_at)
            """
        )


def _ensure_human_handoffs_table_pg(conn: Any) -> None:
    if _pg_table_exists(conn, "human_handoffs"):
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS human_handoffs (
                id BIGSERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL,
                call_id TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'vocal',
                reason TEXT NOT NULL,
                target TEXT NOT NULL,
                mode TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'normal',
                status TEXT NOT NULL DEFAULT 'callback_created',
                patient_phone TEXT,
                raw_name TEXT,
                validated_name TEXT,
                display_name TEXT,
                summary TEXT,
                transcript_excerpt TEXT,
                booking_start_iso TEXT,
                booking_end_iso TEXT,
                booking_motif TEXT,
                notes TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                processed_at TIMESTAMPTZ,
                UNIQUE (tenant_id, call_id)
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_human_handoffs_tenant_created
            ON human_handoffs (tenant_id, created_at)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_human_handoffs_tenant_status_created
            ON human_handoffs (tenant_id, status, created_at)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_human_handoffs_tenant_target_status_created
            ON human_handoffs (tenant_id, target, status, created_at)
            """
        )


def get_call_followup(tenant_id: int, call_id: str) -> Optional[Dict[str, Any]]:
    """Retourne le suivi d'un appel (state + notes) depuis PG ou SQLite."""
    call_id_norm = (call_id or "").strip()
    if not call_id_norm:
        return None

    url = _pg_events_url()
    if url:
        try:

            from backend.pg_pool import pg_connection_for
            with pg_connection_for(url) as conn:
                _ensure_call_followups_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT followup_state, notes, updated_at
                        FROM call_followups
                        WHERE tenant_id = %s AND call_id = %s
                        LIMIT 1
                        """,
                        (tenant_id, call_id_norm),
                    )
                    row = cur.fetchone()
                    if row:
                        return {
                            "followup_state": row.get("followup_state") or "new",
                            "notes": row.get("notes") or "",
                            "updated_at": str(row.get("updated_at") or ""),
                        }
        except Exception:
            pass

    conn = get_conn()
    try:
        _ensure_call_followups_table(conn)
        row = conn.execute(
            """
            SELECT followup_state, notes, updated_at
            FROM call_followups
            WHERE tenant_id = ? AND call_id = ?
            LIMIT 1
            """,
            (tenant_id, call_id_norm),
        ).fetchone()
        if not row:
            return None
        return {
            "followup_state": row["followup_state"] or "new",
            "notes": row["notes"] or "",
            "updated_at": row["updated_at"] or "",
        }
    finally:
        conn.close()


def list_call_followups(tenant_id: int, call_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Retourne les suivis d'appels en lot, indexés par call_id."""
    call_ids_norm = [str(call_id or "").strip() for call_id in call_ids if str(call_id or "").strip()]
    if not call_ids_norm:
        return {}
    call_ids_norm = list(dict.fromkeys(call_ids_norm))

    url = _pg_events_url()
    if url:
        try:

            from backend.pg_pool import pg_connection_for
            with pg_connection_for(url) as conn:
                _ensure_call_followups_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT call_id, followup_state, notes, updated_at
                        FROM call_followups
                        WHERE tenant_id = %s AND call_id = ANY(%s)
                        """,
                        (tenant_id, call_ids_norm),
                    )
                    rows = cur.fetchall()
                    return {
                        str(row.get("call_id") or "").strip(): {
                            "followup_state": row.get("followup_state") or "new",
                            "notes": row.get("notes") or "",
                            "updated_at": str(row.get("updated_at") or ""),
                        }
                        for row in rows
                        if str(row.get("call_id") or "").strip()
                    }
        except Exception:
            pass

    conn = get_conn()
    try:
        _ensure_call_followups_table(conn)
        placeholders = ",".join("?" for _ in call_ids_norm)
        rows = conn.execute(
            f"""
            SELECT call_id, followup_state, notes, updated_at
            FROM call_followups
            WHERE tenant_id = ? AND call_id IN ({placeholders})
            """,
            [tenant_id, *call_ids_norm],
        ).fetchall()
        return {
            str(row["call_id"] or "").strip(): {
                "followup_state": row["followup_state"] or "new",
                "notes": row["notes"] or "",
                "updated_at": row["updated_at"] or "",
            }
            for row in rows
            if str(row["call_id"] or "").strip()
        }
    finally:
        conn.close()


def upsert_call_followup(tenant_id: int, call_id: str, followup_state: str, notes: str = "") -> bool:
    """Crée ou met à jour le suivi d'un appel côté tenant."""
    call_id_norm = (call_id or "").strip()
    state = (followup_state or "new").strip().lower()
    if not call_id_norm:
        return False
    if state not in {"new", "callback", "processed"}:
        return False

    clean_notes = (notes or "").strip()[:4000]
    url = _pg_events_url()
    if url:
        try:

            from backend.pg_pool import pg_connection_for
            with pg_connection_for(url) as conn:
                _ensure_call_followups_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO call_followups (tenant_id, call_id, followup_state, notes, updated_at)
                        VALUES (%s, %s, %s, %s, now())
                        ON CONFLICT (tenant_id, call_id)
                        DO UPDATE SET
                            followup_state = EXCLUDED.followup_state,
                            notes = EXCLUDED.notes,
                            updated_at = now()
                        """,
                        (tenant_id, call_id_norm, state, clean_notes or None),
                    )
                    conn.commit()
                    return True
        except Exception:
            pass

    conn = get_conn()
    try:
        _ensure_call_followups_table(conn)
        conn.execute(
            """
            INSERT INTO call_followups (tenant_id, call_id, followup_state, notes, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, call_id)
            DO UPDATE SET
                followup_state = excluded.followup_state,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (tenant_id, call_id_norm, state, clean_notes or None, datetime.utcnow().isoformat()),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def normalize_phone_number(value: Optional[str]) -> str:
    """Normalise un numéro pour clé métier tenant_id + téléphone."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    cleaned = re.sub(r"[^\d+]", "", raw)
    if cleaned.startswith("00"):
        cleaned = f"+{cleaned[2:]}"
    if cleaned.startswith("+"):
        return cleaned
    if cleaned.startswith("0") and len(cleaned) == 10:
        return f"+33{cleaned[1:]}"
    # +33xxxxxxxxxx erronément lu comme espace (« application/x-www-form-urlencoded » dans ?phone=)
    # → « 336… » sans + ; doit matcher les fiches stockées en +33…
    if re.fullmatch(r"33\d{9}", cleaned):
        return f"+{cleaned}"
    return cleaned


def is_valid_patient_phone(value: Optional[str]) -> bool:
    """Vrai si le numéro, une fois normalisé, est un téléphone plausible (E.164).

    `normalize_phone_number` laisse passer tel quel ce qu'elle ne sait pas
    reconnaître (ex. « 06968547855555555 » à 17 chiffres). Cette validation
    impose un format strict : « + » suivi de 8 à 15 chiffres. Les numéros FR
    nationaux valides (10 chiffres) sont convertis en +33… donc acceptés.
    """
    norm = normalize_phone_number(value or "")
    return bool(re.fullmatch(r"\+\d{8,15}", norm))


def is_valid_contact_email(value: Optional[str]) -> bool:
    """E-mail contact plausible (vide accepté = pas de valeur)."""
    v = str(value or "").strip()
    if not v:
        return True
    if len(v) > 254 or " " in v:
        return False
    return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v))


def _phone_digit_search_patterns(digits_fragment: str) -> List[str]:
    """
    Fragments pour LIKE sur regexp_replace(phone, '\\D', '', 'g').
    Une recherche au format national 06xxxxxxxx doit aussi matcher une fiche en +336xxxxxxxx.
    """
    d = re.sub(r"\D", "", digits_fragment or "")
    if not d:
        return []
    patterns: List[str] = []
    seen: set[str] = set()

    def add(pat: str) -> None:
        if pat and pat not in seen:
            seen.add(pat)
            patterns.append(pat)

    add(d)

    probes: List[str] = [d]
    if len(d) == 10 and d.startswith("0"):
        probes.append(f"+33{d[1:]}")
    elif re.fullmatch(r"33\d{9}", d):
        probes.append(f"+{d}")
    elif len(d) >= 11 and not d.startswith("0"):
        probes.append(d)

    for pv in probes:
        norm = normalize_phone_number(pv)
        if norm.startswith("+"):
            flat = re.sub(r"\D", "", norm)
            add(flat)
            add(flat[2:] if flat.startswith("33") and len(flat) >= 11 else flat)
    # Redondance sûre : 0601020304 -> 33601020304
    if len(d) == 10 and d.startswith("0"):
        add("33" + d[1:])

    return patterns


def _ensure_cabinet_clients_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cabinet_clients (
            tenant_id INTEGER NOT NULL,
            phone TEXT NOT NULL,
            raw_name TEXT,
            validated_name TEXT,
            display_name TEXT,
            validation_status TEXT NOT NULL DEFAULT 'pending',
            email TEXT,
            source_call_id TEXT,
            last_call_id TEXT,
            last_booking_start TEXT,
            last_booking_end TEXT,
            last_booking_motif TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (tenant_id, phone)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cabinet_clients_search ON cabinet_clients(tenant_id, display_name, raw_name, updated_at)"
    )
    # migrate: add email column if missing
    try:
        conn.execute("SELECT email FROM cabinet_clients LIMIT 0")
    except Exception:
        conn.execute("ALTER TABLE cabinet_clients ADD COLUMN email TEXT")
    try:
        conn.execute("SELECT birth_date FROM cabinet_clients LIMIT 0")
    except Exception:
        conn.execute("ALTER TABLE cabinet_clients ADD COLUMN birth_date TEXT")
    try:
        conn.execute("SELECT treating_physician_name FROM cabinet_clients LIMIT 0")
    except Exception:
        conn.execute("ALTER TABLE cabinet_clients ADD COLUMN treating_physician_name TEXT")
    try:
        conn.execute("SELECT treating_physician_city FROM cabinet_clients LIMIT 0")
    except Exception:
        conn.execute("ALTER TABLE cabinet_clients ADD COLUMN treating_physician_city TEXT")

    _ensure_patient_documents_table(conn)
    _ensure_patient_notes_table(conn)
    _ensure_patient_consultations_table(conn)


def _migrate_cabinet_clients_columns_pg(conn: Any) -> None:
    """Best-effort DDL réservé à la création initiale (pas sur le chemin lecture prod)."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DO $$ BEGIN
                    ALTER TABLE cabinet_clients ADD COLUMN email TEXT;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
                """
            )
            cur.execute(
                """
                DO $$ BEGIN
                    ALTER TABLE cabinet_clients ADD COLUMN birth_date DATE;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
                """
            )
            cur.execute(
                """
                DO $$ BEGIN
                    ALTER TABLE cabinet_clients ADD COLUMN treating_physician_name TEXT;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
                """
            )
            cur.execute(
                """
                DO $$ BEGIN
                    ALTER TABLE cabinet_clients ADD COLUMN treating_physician_city TEXT;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
                """
            )
    except Exception as exc:
        logging.getLogger(__name__).debug("cabinet_clients pg column migrate skipped: %s", exc)


_CABINET_CLIENT_COLS_BASE = (
    "phone, raw_name, validated_name, display_name, validation_status, email, "
    "source_call_id, last_call_id, last_booking_start, last_booking_end, "
    "last_booking_motif, created_at, updated_at"
)
_CABINET_CLIENT_COLS_EXTENDED = (
    f"{_CABINET_CLIENT_COLS_BASE}, birth_date, treating_physician_name, treating_physician_city"
)
_CABINET_CLIENT_COLS_COMPACT = (
    "phone, display_name, validated_name, raw_name, validation_status, updated_at, created_at"
)
_cabinet_client_cols_cache: Optional[str] = None


def _reset_cabinet_client_cols_cache() -> None:
    global _cabinet_client_cols_cache
    _cabinet_client_cols_cache = None


def _cabinet_clients_profile_column_names_pg(conn: Any) -> set[str]:
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'cabinet_clients'
                  AND column_name IN (
                    'birth_date', 'treating_physician_name', 'treating_physician_city'
                  )
                """
            )
            rows = cur.fetchall() or []
        out: set[str] = set()
        for row in rows:
            if isinstance(row, dict):
                out.add(str(row.get("column_name") or ""))
            elif row:
                out.add(str(row[0]))
        return {c for c in out if c}
    except Exception:
        return set()


def _cabinet_clients_profile_columns_ready_pg(conn: Any) -> bool:
    cols = _cabinet_clients_profile_column_names_pg(conn)
    return "birth_date" in cols and "treating_physician_name" in cols


def _cabinet_client_select_columns_for_pg(conn: Any) -> str:
    profile_cols = _cabinet_clients_profile_column_names_pg(conn)
    if "birth_date" in profile_cols and "treating_physician_name" in profile_cols:
        suffix = "birth_date, treating_physician_name"
        if "treating_physician_city" in profile_cols:
            suffix += ", treating_physician_city"
        return f"{_CABINET_CLIENT_COLS_BASE}, {suffix}"
    return _CABINET_CLIENT_COLS_BASE


def _ensure_cabinet_clients_profile_columns_pg(conn: Any) -> bool:
    """Tente d'ajouter birth_date / treating_physician_name (migration 040) avant écriture."""
    try:
        _migrate_cabinet_clients_columns_pg(conn)
        _reset_cabinet_client_cols_cache()
        return _cabinet_clients_profile_columns_ready_pg(conn)
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "cabinet_clients profile columns ensure failed: %s",
            exc,
        )
        return False


def _pg_error_is_missing_profile_column(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "birth_date" in msg
        or "treating_physician_name" in msg
        or "treating_physician_city" in msg
        or "undefined column" in msg
        or "does not exist" in msg
    )


def _cabinet_client_select_columns_pg(conn: Any) -> str:
    """Colonnes SELECT cabinet_clients (avec champs profil si migration appliquée)."""
    global _cabinet_client_cols_cache
    if _cabinet_client_cols_cache:
        return _cabinet_client_cols_cache
    try:
        _cabinet_client_cols_cache = _cabinet_client_select_columns_for_pg(conn)
    except Exception:
        _cabinet_client_cols_cache = _CABINET_CLIENT_COLS_BASE
    return _cabinet_client_cols_cache


def _ensure_cabinet_clients_table_pg(conn: Any) -> None:
    if _pg_table_exists(conn, "cabinet_clients"):
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cabinet_clients (
                tenant_id INTEGER NOT NULL,
                phone TEXT NOT NULL,
                raw_name TEXT,
                validated_name TEXT,
                display_name TEXT,
                validation_status TEXT NOT NULL DEFAULT 'pending',
                email TEXT,
                birth_date DATE,
                treating_physician_name TEXT,
                treating_physician_city TEXT,
                source_call_id TEXT,
                last_call_id TEXT,
                last_booking_start TIMESTAMPTZ,
                last_booking_end TIMESTAMPTZ,
                last_booking_motif TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (tenant_id, phone)
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cabinet_clients_search
            ON cabinet_clients (tenant_id, display_name, raw_name, updated_at)
            """
        )
    _migrate_cabinet_clients_columns_pg(conn)
    _ensure_patient_documents_table_pg(conn)
    _ensure_patient_notes_table_pg(conn)
    _ensure_patient_consultations_table_pg(conn)


def _cabinet_client_row_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "phone": row.get("phone") or "",
        "raw_name": row.get("raw_name") or "",
        "validated_name": row.get("validated_name") or "",
        "display_name": row.get("display_name") or row.get("validated_name") or row.get("raw_name") or "",
        "validation_status": row.get("validation_status") or "pending",
        "email": row.get("email") or "",
        "birth_date": str(row.get("birth_date") or "")[:10] if row.get("birth_date") else "",
        "treating_physician_name": row.get("treating_physician_name") or "",
        "treating_physician_city": row.get("treating_physician_city") or "",
        "source_call_id": row.get("source_call_id") or "",
        "last_call_id": row.get("last_call_id") or "",
        "last_booking_start": str(row.get("last_booking_start") or ""),
        "last_booking_end": str(row.get("last_booking_end") or ""),
        "last_booking_motif": row.get("last_booking_motif") or "",
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
    }


# ─── Patient documents ───────────────────────────────────────

def _ensure_patient_documents_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            patient_phone TEXT NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            mime_type TEXT,
            size_bytes INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )


def _ensure_patient_documents_table_pg(conn: Any) -> None:
    if _pg_table_exists(conn, "patient_documents"):
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS patient_documents (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL,
                patient_phone TEXT NOT NULL,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                mime_type TEXT,
                size_bytes INTEGER,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    conn.commit()


def _ensure_patient_notes_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            patient_phone TEXT NOT NULL,
            note_text TEXT NOT NULL,
            author TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )


def _ensure_patient_notes_table_pg(conn: Any) -> None:
    if _pg_table_exists(conn, "patient_notes"):
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS patient_notes (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL,
                patient_phone TEXT NOT NULL,
                note_text TEXT NOT NULL,
                author TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )


def _ensure_patient_consultations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_consultations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            patient_phone TEXT NOT NULL,
            appointment_id TEXT,
            consultation_date TEXT NOT NULL,
            mode_consultation TEXT NOT NULL DEFAULT 'rapide',
            motif TEXT NOT NULL,
            anamnese TEXT,
            etat_general TEXT,
            examen_physique TEXT,
            impression_clinique TEXT NOT NULL,
            cim10 TEXT,
            examens_demandes TEXT,
            prescription TEXT,
            orientation TEXT,
            suivi_prochain_rdv TEXT,
            suivi_consignes TEXT,
            note_praticien TEXT,
            ia_resume TEXT,
            ia_contexte_patient TEXT,
            ia_status TEXT NOT NULL DEFAULT 'pending',
            ia_validated_at TEXT,
            raw_payload TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_patient_consultations_tenant_phone_date
        ON patient_consultations (tenant_id, patient_phone, consultation_date DESC, created_at DESC)
        """
    )
    _ensure_patient_consultation_vitals_table(conn)


def _ensure_patient_consultation_vitals_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_consultation_vitals (
            consultation_id INTEGER PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            patient_phone TEXT NOT NULL,
            measured_at TEXT NOT NULL,
            fc_bpm INTEGER,
            pa_systolique INTEGER,
            pa_diastolique INTEGER,
            temperature_c REAL,
            spo2_pct INTEGER,
            fr_min INTEGER,
            poids_kg REAL,
            taille_cm INTEGER,
            imc REAL,
            source TEXT NOT NULL DEFAULT 'praticien',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (consultation_id) REFERENCES patient_consultations(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_patient_consultation_vitals_tenant_phone_date
        ON patient_consultation_vitals (tenant_id, patient_phone, measured_at DESC)
        """
    )


def _ensure_patient_consultations_table_pg(conn: Any) -> None:
    if not _pg_table_exists(conn, "patient_consultations"):
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS patient_consultations (
                    id BIGSERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL,
                    patient_phone TEXT NOT NULL,
                    appointment_id TEXT,
                    consultation_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    mode_consultation TEXT NOT NULL DEFAULT 'rapide',
                    motif TEXT NOT NULL,
                    anamnese TEXT,
                    etat_general TEXT,
                    examen_physique TEXT,
                    impression_clinique TEXT NOT NULL,
                    cim10 TEXT,
                    examens_demandes TEXT[] NOT NULL DEFAULT '{}',
                    prescription TEXT,
                    orientation TEXT,
                    suivi_prochain_rdv DATE,
                    suivi_consignes TEXT,
                    note_praticien TEXT,
                    ia_resume TEXT,
                    ia_contexte_patient TEXT,
                    ia_status TEXT NOT NULL DEFAULT 'pending',
                    ia_validated_at TIMESTAMPTZ,
                    raw_payload JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_patient_consultations_tenant_phone_date
                ON patient_consultations (tenant_id, patient_phone, consultation_date DESC, created_at DESC)
                """
            )
        conn.commit()
    _ensure_patient_consultation_vitals_table_pg(conn)


def _ensure_patient_consultation_vitals_table_pg(conn: Any) -> None:
    if _pg_table_exists(conn, "patient_consultation_vitals"):
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS patient_consultation_vitals (
                consultation_id BIGINT PRIMARY KEY REFERENCES patient_consultations(id) ON DELETE CASCADE,
                tenant_id INTEGER NOT NULL,
                patient_phone TEXT NOT NULL,
                measured_at DATE NOT NULL,
                fc_bpm SMALLINT CHECK (fc_bpm BETWEEN 20 AND 300),
                pa_systolique SMALLINT CHECK (pa_systolique BETWEEN 50 AND 300),
                pa_diastolique SMALLINT CHECK (pa_diastolique BETWEEN 20 AND 200),
                temperature_c NUMERIC(4,1) CHECK (temperature_c BETWEEN 30 AND 45),
                spo2_pct SMALLINT CHECK (spo2_pct BETWEEN 50 AND 100),
                fr_min SMALLINT CHECK (fr_min BETWEEN 4 AND 80),
                poids_kg NUMERIC(5,1) CHECK (poids_kg BETWEEN 1 AND 400),
                taille_cm SMALLINT CHECK (taille_cm BETWEEN 30 AND 250),
                imc NUMERIC(5,1),
                source TEXT NOT NULL DEFAULT 'praticien',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_patient_consultation_vitals_tenant_phone_date
            ON patient_consultation_vitals (tenant_id, patient_phone, measured_at DESC)
            """
        )
    conn.commit()


def update_patient_fields(
    tenant_id: int,
    phone: str,
    *,
    email: Optional[str] = None,
    birth_date: Optional[str] = None,
    treating_physician_name: Optional[str] = None,
    treating_physician_city: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update specific fields on an existing cabinet_client row."""
    phone_norm = normalize_phone_number(phone)
    if not phone_norm:
        return None

    sets = []
    params: list = []
    if email is not None:
        clean_email = email.strip()[:254]
        sets.append("email = ?")
        params.append(clean_email)
    if birth_date is not None:
        clean_birth = birth_date.strip()[:10]
        sets.append("birth_date = ?")
        params.append(clean_birth or None)
    if treating_physician_name is not None:
        clean_physician = treating_physician_name.strip()[:200]
        sets.append("treating_physician_name = ?")
        params.append(clean_physician or None)
    if treating_physician_city is not None:
        clean_city = treating_physician_city.strip()[:120]
        sets.append("treating_physician_city = ?")
        params.append(clean_city or None)
    if not sets:
        return get_cabinet_client_by_phone(tenant_id, phone)

    sets.append("updated_at = datetime('now')")
    params.extend([tenant_id, phone_norm])

    has_profile_fields = (
        birth_date is not None
        or treating_physician_name is not None
        or treating_physician_city is not None
    )
    url = _pg_events_url()
    if url:
        try:
            pg_sets = [s.replace("?", "%s").replace("datetime('now')", "now()") for s in sets]
            from backend.pg_pool import pg_connection_for
            with pg_connection_for(url) as conn:
                _ensure_cabinet_clients_table_pg(conn)
                if has_profile_fields and not _cabinet_clients_profile_columns_ready_pg(conn):
                    _ensure_cabinet_clients_profile_columns_pg(conn)
                    if not _cabinet_clients_profile_columns_ready_pg(conn):
                        logging.getLogger(__name__).error(
                            "update_patient_fields: colonnes profil absentes tenant_id=%s phone=%s",
                            tenant_id,
                            phone_norm,
                        )
                        return None

                rowcount = 0
                for attempt in range(2):
                    try:
                        with conn.cursor() as cur:
                            cur.execute(
                                f"UPDATE cabinet_clients SET {', '.join(pg_sets)} WHERE tenant_id = %s AND phone = %s",
                                params,
                            )
                            rowcount = cur.rowcount
                        conn.commit()
                        _reset_cabinet_client_cols_cache()
                        break
                    except Exception as exc:
                        if (
                            attempt == 0
                            and has_profile_fields
                            and _pg_error_is_missing_profile_column(exc)
                        ):
                            _ensure_cabinet_clients_profile_columns_pg(conn)
                            try:
                                conn.commit()
                            except Exception:
                                pass
                            continue
                        raise

            if rowcount == 0:
                logging.getLogger(__name__).warning(
                    "update_patient_fields: 0 ligne MAJ (tenant_id=%s phone=%s) — fiche absente ?",
                    tenant_id,
                    phone_norm,
                )
            return get_cabinet_client_by_phone(tenant_id, phone)
        except Exception as exc:
            logging.getLogger(__name__).error(
                "update_patient_fields PG failed tenant_id=%s phone=%s: %s",
                tenant_id,
                phone_norm,
                exc,
            )
            return None

    conn = get_conn()
    _ensure_cabinet_clients_table(conn)
    conn.execute(
        f"UPDATE cabinet_clients SET {', '.join(sets)} WHERE tenant_id = ? AND phone = ?",
        params,
    )
    conn.commit()
    return get_cabinet_client_by_phone(tenant_id, phone)


def list_patient_documents(tenant_id: int, phone: str) -> List[Dict[str, Any]]:
    phone_norm = normalize_phone_number(phone) or phone.strip()
    url = _pg_events_url()
    if url:
        from backend.pg_pool import pg_connection_for
        with pg_connection_for(url) as conn:
            _ensure_patient_documents_table_pg(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM patient_documents WHERE tenant_id = %s AND patient_phone = %s ORDER BY created_at DESC",
                    (tenant_id, phone_norm),
                )
                return [dict(r) for r in cur.fetchall()]
    conn = get_conn()
    _ensure_patient_documents_table(conn)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM patient_documents WHERE tenant_id = ? AND patient_phone = ? ORDER BY created_at DESC",
        (tenant_id, phone_norm),
    ).fetchall()
    return [dict(r) for r in rows]


def insert_patient_document(
    tenant_id: int, phone: str, *, filename: str, original_name: str, mime_type: str, size_bytes: int,
) -> Dict[str, Any]:
    phone_norm = normalize_phone_number(phone) or phone.strip()
    url = _pg_events_url()
    if url:
        from backend.pg_pool import pg_connection_for
        with pg_connection_for(url) as conn:
            _ensure_patient_documents_table_pg(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO patient_documents (tenant_id, patient_phone, filename, original_name, mime_type, size_bytes)
                       VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
                    (tenant_id, phone_norm, filename, original_name, mime_type, size_bytes),
                )
                row = cur.fetchone()
            conn.commit()
            if not row:
                raise RuntimeError("insert_patient_document: INSERT sans ligne retournée")
            return dict(row)
    conn = get_conn()
    _ensure_patient_documents_table(conn)
    cur = conn.execute(
        """INSERT INTO patient_documents (tenant_id, patient_phone, filename, original_name, mime_type, size_bytes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (tenant_id, phone_norm, filename, original_name, mime_type, size_bytes),
    )
    conn.commit()
    return {"id": cur.lastrowid, "tenant_id": tenant_id, "patient_phone": phone_norm,
            "filename": filename, "original_name": original_name, "mime_type": mime_type,
            "size_bytes": size_bytes, "created_at": ""}


def delete_patient_document(
    tenant_id: int,
    doc_id: int,
    *,
    patient_phone: Optional[str] = None,
) -> bool:
    """
    Supprime un document patient. Si `patient_phone` est fourni (recommandé),
    la suppression est limitée aux documents de ce patient — anti-IDOR.
    """
    phone_norm = normalize_phone_number(patient_phone) if patient_phone else ""
    url = _pg_events_url()
    if url:
        try:
            from backend.pg_pool import pg_connection_for
            with pg_connection_for(url) as conn:
                with conn.cursor() as cur:
                    if phone_norm:
                        cur.execute(
                            "DELETE FROM patient_documents WHERE id = %s AND tenant_id = %s AND patient_phone = %s",
                            (doc_id, tenant_id, phone_norm),
                        )
                    else:
                        cur.execute("DELETE FROM patient_documents WHERE id = %s AND tenant_id = %s", (doc_id, tenant_id))
                    deleted = cur.rowcount > 0
                conn.commit()
                return deleted
        except Exception:
            pass
    conn = get_conn()
    _ensure_patient_documents_table(conn)
    if phone_norm:
        cur = conn.execute(
            "DELETE FROM patient_documents WHERE id = ? AND tenant_id = ? AND patient_phone = ?",
            (doc_id, tenant_id, phone_norm),
        )
    else:
        cur = conn.execute("DELETE FROM patient_documents WHERE id = ? AND tenant_id = ?", (doc_id, tenant_id))
    conn.commit()
    return cur.rowcount > 0


def list_patient_notes(tenant_id: int, phone: str, *, limit: int = 100) -> List[Dict[str, Any]]:
    """Lit les notes patient et déchiffre `note_text` à la volée (rétrocompat clair)."""
    from backend.crypto_at_rest import decrypt_str

    phone_norm = normalize_phone_number(phone) or phone.strip()
    limit = max(1, min(int(limit or 100), 300))
    url = _pg_events_url()
    rows: List[Dict[str, Any]] = []
    if url:
        try:
            from backend.pg_pool import pg_connection_for
            with pg_connection_for(url) as conn:
                _ensure_patient_notes_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, tenant_id, patient_phone, note_text, author, created_at
                        FROM patient_notes
                        WHERE tenant_id = %s AND patient_phone = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (tenant_id, phone_norm, limit),
                    )
                    rows = [dict(r) for r in cur.fetchall()]
        except Exception:
            rows = []
    if not rows:
        conn = get_conn()
        _ensure_patient_notes_table(conn)
        conn.row_factory = sqlite3.Row
        rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT id, tenant_id, patient_phone, note_text, author, created_at
                FROM patient_notes
                WHERE tenant_id = ? AND patient_phone = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (tenant_id, phone_norm, limit),
            ).fetchall()
        ]
    for r in rows:
        r["note_text"] = decrypt_str(r.get("note_text"))
    return rows


def insert_patient_note(
    tenant_id: int,
    phone: str,
    *,
    note_text: str,
    author: str = "",
) -> Dict[str, Any]:
    """Insère une note patient. `note_text` est chiffré au repos si DATA_ENCRYPTION_KEY est défini."""
    from backend.crypto_at_rest import encrypt_str

    phone_norm = normalize_phone_number(phone) or phone.strip()
    text = (note_text or "").strip()[:4000]
    if not text:
        return {}
    author_clean = (author or "").strip()[:120]
    stored = encrypt_str(text)
    url = _pg_events_url()
    if url:
        try:
            from backend.pg_pool import pg_connection_for
            with pg_connection_for(url) as conn:
                _ensure_patient_notes_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO patient_notes (tenant_id, patient_phone, note_text, author)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id, tenant_id, patient_phone, author, created_at
                        """,
                        (tenant_id, phone_norm, stored, author_clean or None),
                    )
                    row = cur.fetchone()
                conn.commit()
                if row:
                    out = dict(row)
                    out["note_text"] = text
                    return out
                return {}
        except Exception:
            pass
    conn = get_conn()
    _ensure_patient_notes_table(conn)
    cur = conn.execute(
        """
        INSERT INTO patient_notes (tenant_id, patient_phone, note_text, author)
        VALUES (?, ?, ?, ?)
        """,
        (tenant_id, phone_norm, stored, author_clean or None),
    )
    conn.commit()
    return {
        "id": cur.lastrowid,
        "tenant_id": tenant_id,
        "patient_phone": phone_norm,
        "note_text": text,
        "author": author_clean,
        "created_at": "",
    }


def delete_patient_note(
    tenant_id: int,
    note_id: int,
    *,
    patient_phone: Optional[str] = None,
) -> bool:
    """
    Supprime une note patient. Si `patient_phone` est fourni (recommandé),
    la suppression est limitée aux notes de ce patient — anti-IDOR.
    """
    phone_norm = normalize_phone_number(patient_phone) if patient_phone else ""
    url = _pg_events_url()
    if url:
        try:
            from backend.pg_pool import pg_connection_for
            with pg_connection_for(url) as conn:
                _ensure_patient_notes_table_pg(conn)
                with conn.cursor() as cur:
                    if phone_norm:
                        cur.execute(
                            "DELETE FROM patient_notes WHERE id = %s AND tenant_id = %s AND patient_phone = %s",
                            (note_id, tenant_id, phone_norm),
                        )
                    else:
                        cur.execute("DELETE FROM patient_notes WHERE id = %s AND tenant_id = %s", (note_id, tenant_id))
                    deleted = cur.rowcount > 0
                conn.commit()
                return deleted
        except Exception:
            pass
    conn = get_conn()
    _ensure_patient_notes_table(conn)
    if phone_norm:
        cur = conn.execute(
            "DELETE FROM patient_notes WHERE id = ? AND tenant_id = ? AND patient_phone = ?",
            (note_id, tenant_id, phone_norm),
        )
    else:
        cur = conn.execute("DELETE FROM patient_notes WHERE id = ? AND tenant_id = ?", (note_id, tenant_id))
    conn.commit()
    return cur.rowcount > 0


def update_patient_note(
    tenant_id: int,
    note_id: int,
    *,
    note_text: str,
    patient_phone: Optional[str] = None,
) -> Dict[str, Any]:
    """Met à jour une note patient (texte) avec scope anti-IDOR optionnel."""
    from backend.crypto_at_rest import encrypt_str

    phone_norm = normalize_phone_number(patient_phone) if patient_phone else ""
    text = (note_text or "").strip()[:4000]
    if not text:
        return {}
    stored = encrypt_str(text)
    url = _pg_events_url()
    if url:
        try:
            from backend.pg_pool import pg_connection_for

            with pg_connection_for(url) as conn:
                _ensure_patient_notes_table_pg(conn)
                with conn.cursor() as cur:
                    if phone_norm:
                        cur.execute(
                            """
                            UPDATE patient_notes
                            SET note_text = %s
                            WHERE id = %s AND tenant_id = %s AND patient_phone = %s
                            RETURNING id, tenant_id, patient_phone, author, created_at
                            """,
                            (stored, note_id, tenant_id, phone_norm),
                        )
                    else:
                        cur.execute(
                            """
                            UPDATE patient_notes
                            SET note_text = %s
                            WHERE id = %s AND tenant_id = %s
                            RETURNING id, tenant_id, patient_phone, author, created_at
                            """,
                            (stored, note_id, tenant_id),
                        )
                    row = cur.fetchone()
                conn.commit()
                if not row:
                    return {}
                out = dict(row)
                out["note_text"] = text
                return out
        except Exception:
            pass

    conn = get_conn()
    _ensure_patient_notes_table(conn)
    if phone_norm:
        cur = conn.execute(
            "UPDATE patient_notes SET note_text = ? WHERE id = ? AND tenant_id = ? AND patient_phone = ?",
            (stored, note_id, tenant_id, phone_norm),
        )
    else:
        cur = conn.execute(
            "UPDATE patient_notes SET note_text = ? WHERE id = ? AND tenant_id = ?",
            (stored, note_id, tenant_id),
        )
    conn.commit()
    if cur.rowcount <= 0:
        return {}
    conn.row_factory = sqlite3.Row
    if phone_norm:
        row = conn.execute(
            """
            SELECT id, tenant_id, patient_phone, author, created_at
            FROM patient_notes
            WHERE id = ? AND tenant_id = ? AND patient_phone = ?
            LIMIT 1
            """,
            (note_id, tenant_id, phone_norm),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT id, tenant_id, patient_phone, author, created_at
            FROM patient_notes
            WHERE id = ? AND tenant_id = ?
            LIMIT 1
            """,
            (note_id, tenant_id),
        ).fetchone()
    if not row:
        return {}
    out = dict(row)
    out["note_text"] = text
    return out


_CONSULTATION_VITAL_FIELDS = (
    "fc_bpm",
    "pa_systolique",
    "pa_diastolique",
    "temperature_c",
    "spo2_pct",
    "fr_min",
    "poids_kg",
    "taille_cm",
    "imc",
)
_CONSULTATION_VITAL_INT_FIELDS = {
    "fc_bpm",
    "pa_systolique",
    "pa_diastolique",
    "spo2_pct",
    "fr_min",
    "taille_cm",
}


def _coerce_iso_date(value: Any, *, fallback_today: bool = False) -> Optional[str]:
    if isinstance(value, date):
        return value.isoformat()
    raw = str(value or "").strip()[:10]
    if not raw:
        return date.today().isoformat() if fallback_today else None
    try:
        datetime.strptime(raw, "%Y-%m-%d")
        return raw
    except Exception:
        return date.today().isoformat() if fallback_today else None


def _consultation_parse_examens(raw: Any) -> List[str]:
    source: List[str] = []
    if isinstance(raw, list):
        source = [str(x or "").strip() for x in raw]
    elif isinstance(raw, str):
        text = raw.strip()
        if text:
            if text.startswith("[") and text.endswith("]"):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        source = [str(x or "").strip() for x in parsed]
                except Exception:
                    source = []
            if not source:
                source = [chunk.strip() for chunk in text.split(",")]
    out: List[str] = []
    seen = set()
    for item in source:
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item[:120])
    return out


def _consultation_vitals_to_dict(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not row:
        return {}
    out: Dict[str, Any] = {
        "measured_at": str(row.get("measured_at") or "")[:10],
        "source": str(row.get("source") or "praticien"),
    }
    for field in _CONSULTATION_VITAL_FIELDS:
        raw = row.get(field)
        if raw in (None, ""):
            continue
        try:
            if field in _CONSULTATION_VITAL_INT_FIELDS:
                out[field] = int(raw)
            else:
                out[field] = float(raw)
        except Exception:
            continue
    return out


def _consultation_row_to_dict(row: Dict[str, Any], vitals: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "id": int(row.get("id") or 0),
        "tenant_id": int(row.get("tenant_id") or 0),
        "patient_phone": str(row.get("patient_phone") or ""),
        "appointment_id": str(row.get("appointment_id") or ""),
        "date_consultation": str(row.get("consultation_date") or "")[:10],
        "mode_consultation": str(row.get("mode_consultation") or "rapide"),
        "motif": str(row.get("motif") or ""),
        "anamnese": str(row.get("anamnese") or ""),
        "etat_general": str(row.get("etat_general") or ""),
        "examen_physique": str(row.get("examen_physique") or ""),
        "impression_clinique": str(row.get("impression_clinique") or ""),
        "cim10": str(row.get("cim10") or ""),
        "examens_demandes": _consultation_parse_examens(row.get("examens_demandes")),
        "prescription": str(row.get("prescription") or ""),
        "orientation": str(row.get("orientation") or ""),
        "suivi_prochain_rdv": str(row.get("suivi_prochain_rdv") or "")[:10],
        "suivi_consignes": str(row.get("suivi_consignes") or ""),
        "note_praticien": str(row.get("note_praticien") or ""),
        "ia_resume": str(row.get("ia_resume") or ""),
        "ia_contexte_patient": str(row.get("ia_contexte_patient") or ""),
        "ia_status": str(row.get("ia_status") or "pending"),
        "ia_validated_at": str(row.get("ia_validated_at") or ""),
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
        "vitals": vitals or {},
    }


def get_patient_consultation_by_id(
    tenant_id: int,
    phone: str,
    consultation_id: int,
) -> Optional[Dict[str, Any]]:
    phone_norm = normalize_phone_number(phone) or phone.strip()
    if not phone_norm:
        return None
    cid = int(consultation_id or 0)
    if cid <= 0:
        return None

    url = _pg_events_url()
    if url:
        try:
            from backend.pg_pool import pg_connection_for
            with pg_connection_for(url) as conn:
                _ensure_patient_consultations_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT *
                        FROM patient_consultations
                        WHERE id = %s AND tenant_id = %s AND patient_phone = %s
                        LIMIT 1
                        """,
                        (cid, tenant_id, phone_norm),
                    )
                    row = cur.fetchone()
                    if not row:
                        return None
                    cur.execute(
                        """
                        SELECT *
                        FROM patient_consultation_vitals
                        WHERE consultation_id = %s AND tenant_id = %s AND patient_phone = %s
                        LIMIT 1
                        """,
                        (cid, tenant_id, phone_norm),
                    )
                    vitals_row = cur.fetchone()
                    return _consultation_row_to_dict(
                        dict(row),
                        _consultation_vitals_to_dict(dict(vitals_row)) if vitals_row else {},
                    )
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "get_patient_consultation_by_id pg failed tenant_id=%s phone=%s id=%s err=%s",
                tenant_id,
                phone_norm,
                cid,
                exc,
            )

    conn = get_conn()
    try:
        _ensure_patient_consultations_table(conn)
        row = conn.execute(
            """
            SELECT *
            FROM patient_consultations
            WHERE id = ? AND tenant_id = ? AND patient_phone = ?
            LIMIT 1
            """,
            (cid, tenant_id, phone_norm),
        ).fetchone()
        if not row:
            return None
        vitals_row = conn.execute(
            """
            SELECT *
            FROM patient_consultation_vitals
            WHERE consultation_id = ? AND tenant_id = ? AND patient_phone = ?
            LIMIT 1
            """,
            (cid, tenant_id, phone_norm),
        ).fetchone()
        return _consultation_row_to_dict(
            dict(row),
            _consultation_vitals_to_dict(dict(vitals_row)) if vitals_row else {},
        )
    finally:
        conn.close()


def list_patient_consultations(
    tenant_id: int,
    phone: str,
    *,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    phone_norm = normalize_phone_number(phone) or phone.strip()
    if not phone_norm:
        return []
    cap = max(1, min(int(limit or 100), 300))

    url = _pg_events_url()
    if url:
        try:
            from backend.pg_pool import pg_connection_for
            with pg_connection_for(url) as conn:
                _ensure_patient_consultations_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT *
                        FROM patient_consultations
                        WHERE tenant_id = %s AND patient_phone = %s
                        ORDER BY consultation_date DESC, created_at DESC
                        LIMIT %s
                        """,
                        (tenant_id, phone_norm, cap),
                    )
                    rows = [dict(r) for r in cur.fetchall()]
                    if not rows:
                        return []
                    ids = [int(r.get("id") or 0) for r in rows if int(r.get("id") or 0) > 0]
                    vitals_by_id: Dict[int, Dict[str, Any]] = {}
                    if ids:
                        cur.execute(
                            """
                            SELECT *
                            FROM patient_consultation_vitals
                            WHERE tenant_id = %s
                              AND patient_phone = %s
                              AND consultation_id = ANY(%s)
                            """,
                            (tenant_id, phone_norm, ids),
                        )
                        for vr in cur.fetchall():
                            vdict = dict(vr)
                            vitals_by_id[int(vdict.get("consultation_id") or 0)] = _consultation_vitals_to_dict(vdict)
                    return [
                        _consultation_row_to_dict(
                            row,
                            vitals_by_id.get(int(row.get("id") or 0), {}),
                        )
                        for row in rows
                    ]
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "list_patient_consultations pg failed tenant_id=%s phone=%s err=%s",
                tenant_id,
                phone_norm,
                exc,
            )

    conn = get_conn()
    try:
        _ensure_patient_consultations_table(conn)
        rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT *
                FROM patient_consultations
                WHERE tenant_id = ? AND patient_phone = ?
                ORDER BY consultation_date DESC, created_at DESC
                LIMIT ?
                """,
                (tenant_id, phone_norm, cap),
            ).fetchall()
        ]
        if not rows:
            return []
        ids = [int(r.get("id") or 0) for r in rows if int(r.get("id") or 0) > 0]
        vitals_by_id: Dict[int, Dict[str, Any]] = {}
        if ids:
            placeholders = ",".join("?" for _ in ids)
            sql = (
                "SELECT * FROM patient_consultation_vitals "
                f"WHERE tenant_id = ? AND patient_phone = ? AND consultation_id IN ({placeholders})"
            )
            params = [tenant_id, phone_norm, *ids]
            for vr in conn.execute(sql, params).fetchall():
                vdict = dict(vr)
                vitals_by_id[int(vdict.get("consultation_id") or 0)] = _consultation_vitals_to_dict(vdict)
        return [
            _consultation_row_to_dict(
                row,
                vitals_by_id.get(int(row.get("id") or 0), {}),
            )
            for row in rows
        ]
    finally:
        conn.close()


def create_patient_consultation(
    tenant_id: int,
    phone: str,
    *,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    phone_norm = normalize_phone_number(phone) or phone.strip()
    if not phone_norm:
        raise ValueError("patient_phone requis")

    mode = str(body.get("mode_consultation") or "rapide").strip().lower()
    if mode not in ("rapide", "complete"):
        mode = "rapide"

    consultation_date = _coerce_iso_date(body.get("date"), fallback_today=True) or date.today().isoformat()
    motif = str(body.get("motif") or "").strip()[:240]
    impression = str(body.get("impression_clinique") or "").strip()[:6000]
    if len(motif) < 1:
        raise ValueError("motif requis")
    if len(impression) < 1:
        raise ValueError("impression_clinique requis")

    examen = body.get("examen_clinique") if isinstance(body.get("examen_clinique"), dict) else {}
    conduite = body.get("conduite_a_tenir") if isinstance(body.get("conduite_a_tenir"), dict) else {}
    suivi = conduite.get("suivi") if isinstance(conduite.get("suivi"), dict) else {}
    ia = body.get("ia_uwi") if isinstance(body.get("ia_uwi"), dict) else {}
    constantes = examen.get("constantes") if isinstance(examen.get("constantes"), dict) else {}

    examens = _consultation_parse_examens(conduite.get("examens_complementaires"))
    ia_validated = bool(ia.get("validated_by_practitioner"))
    ia_status = "validated" if ia_validated else "pending"
    ia_validated_at = datetime.utcnow().isoformat() if ia_validated else None
    payload_json = json.dumps(body or {}, ensure_ascii=False)

    vitals_payload: Dict[str, Any] = {}
    for field in _CONSULTATION_VITAL_FIELDS:
        raw = constantes.get(field)
        if raw in (None, ""):
            continue
        try:
            if field in _CONSULTATION_VITAL_INT_FIELDS:
                vitals_payload[field] = int(float(raw))
            else:
                vitals_payload[field] = float(raw)
        except Exception:
            continue

    insert_payload = {
        "tenant_id": tenant_id,
        "patient_phone": phone_norm,
        "appointment_id": str(body.get("appointment_id") or "").strip()[:120] or None,
        "consultation_date": consultation_date,
        "mode_consultation": mode,
        "motif": motif,
        "anamnese": str(body.get("anamnese") or "").strip()[:12000] or None,
        "etat_general": str(examen.get("etat_general") or "").strip()[:3000] or None,
        "examen_physique": str(examen.get("examen_physique") or "").strip()[:6000] or None,
        "impression_clinique": impression,
        "cim10": str(body.get("cim10") or "").strip()[:40] or None,
        "examens_demandes": examens,
        "prescription": str(conduite.get("prescription") or "").strip()[:6000] or None,
        "orientation": str(conduite.get("orientation") or "").strip()[:4000] or None,
        "suivi_prochain_rdv": _coerce_iso_date(suivi.get("prochain_rdv"), fallback_today=False),
        "suivi_consignes": str(suivi.get("consignes") or "").strip()[:4000] or None,
        "note_praticien": str(body.get("note_praticien") or "").strip()[:12000] or None,
        "ia_resume": str(ia.get("resume_consultation") or "").strip()[:12000] or None,
        "ia_contexte_patient": str(ia.get("contexte_patient") or "").strip()[:12000] or None,
        "ia_status": ia_status,
        "ia_validated_at": ia_validated_at,
        "raw_payload": payload_json,
    }

    url = _pg_events_url()
    if url:
        try:
            from backend.pg_pool import pg_connection_for
            with pg_connection_for(url) as conn:
                _ensure_patient_consultations_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO patient_consultations (
                            tenant_id, patient_phone, appointment_id, consultation_date, mode_consultation,
                            motif, anamnese, etat_general, examen_physique, impression_clinique, cim10,
                            examens_demandes, prescription, orientation, suivi_prochain_rdv, suivi_consignes,
                            note_praticien, ia_resume, ia_contexte_patient, ia_status, ia_validated_at, raw_payload
                        ) VALUES (
                            %(tenant_id)s, %(patient_phone)s, %(appointment_id)s, %(consultation_date)s, %(mode_consultation)s,
                            %(motif)s, %(anamnese)s, %(etat_general)s, %(examen_physique)s, %(impression_clinique)s, %(cim10)s,
                            %(examens_demandes)s, %(prescription)s, %(orientation)s, %(suivi_prochain_rdv)s, %(suivi_consignes)s,
                            %(note_praticien)s, %(ia_resume)s, %(ia_contexte_patient)s, %(ia_status)s, %(ia_validated_at)s, %(raw_payload)s
                        )
                        RETURNING id
                        """,
                        insert_payload,
                    )
                    row = cur.fetchone()
                    if not row:
                        raise RuntimeError("create_patient_consultation pg insert failed")
                    consultation_id = int(row.get("id") or 0)
                    if consultation_id <= 0:
                        raise RuntimeError("create_patient_consultation pg invalid id")
                    if vitals_payload:
                        cur.execute(
                            """
                            INSERT INTO patient_consultation_vitals (
                                consultation_id, tenant_id, patient_phone, measured_at,
                                fc_bpm, pa_systolique, pa_diastolique, temperature_c, spo2_pct, fr_min,
                                poids_kg, taille_cm, imc, source
                            ) VALUES (
                                %(consultation_id)s, %(tenant_id)s, %(patient_phone)s, %(measured_at)s,
                                %(fc_bpm)s, %(pa_systolique)s, %(pa_diastolique)s, %(temperature_c)s, %(spo2_pct)s, %(fr_min)s,
                                %(poids_kg)s, %(taille_cm)s, %(imc)s, 'praticien'
                            )
                            """,
                            {
                                "consultation_id": consultation_id,
                                "tenant_id": tenant_id,
                                "patient_phone": phone_norm,
                                "measured_at": consultation_date,
                                "fc_bpm": vitals_payload.get("fc_bpm"),
                                "pa_systolique": vitals_payload.get("pa_systolique"),
                                "pa_diastolique": vitals_payload.get("pa_diastolique"),
                                "temperature_c": vitals_payload.get("temperature_c"),
                                "spo2_pct": vitals_payload.get("spo2_pct"),
                                "fr_min": vitals_payload.get("fr_min"),
                                "poids_kg": vitals_payload.get("poids_kg"),
                                "taille_cm": vitals_payload.get("taille_cm"),
                                "imc": vitals_payload.get("imc"),
                            },
                        )
                conn.commit()
            created = get_patient_consultation_by_id(tenant_id, phone_norm, consultation_id)
            if created:
                return created
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "create_patient_consultation pg failed tenant_id=%s phone=%s err=%s",
                tenant_id,
                phone_norm,
                exc,
            )

    conn = get_conn()
    try:
        _ensure_patient_consultations_table(conn)
        cur = conn.execute(
            """
            INSERT INTO patient_consultations (
                tenant_id, patient_phone, appointment_id, consultation_date, mode_consultation,
                motif, anamnese, etat_general, examen_physique, impression_clinique, cim10,
                examens_demandes, prescription, orientation, suivi_prochain_rdv, suivi_consignes,
                note_praticien, ia_resume, ia_contexte_patient, ia_status, ia_validated_at, raw_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                phone_norm,
                insert_payload["appointment_id"],
                consultation_date,
                mode,
                motif,
                insert_payload["anamnese"],
                insert_payload["etat_general"],
                insert_payload["examen_physique"],
                impression,
                insert_payload["cim10"],
                json.dumps(examens, ensure_ascii=False),
                insert_payload["prescription"],
                insert_payload["orientation"],
                insert_payload["suivi_prochain_rdv"],
                insert_payload["suivi_consignes"],
                insert_payload["note_praticien"],
                insert_payload["ia_resume"],
                insert_payload["ia_contexte_patient"],
                ia_status,
                ia_validated_at,
                payload_json,
            ),
        )
        consultation_id = int(cur.lastrowid or 0)
        if consultation_id <= 0:
            raise RuntimeError("create_patient_consultation sqlite insert failed")
        if vitals_payload:
            conn.execute(
                """
                INSERT INTO patient_consultation_vitals (
                    consultation_id, tenant_id, patient_phone, measured_at,
                    fc_bpm, pa_systolique, pa_diastolique, temperature_c, spo2_pct, fr_min,
                    poids_kg, taille_cm, imc, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    consultation_id,
                    tenant_id,
                    phone_norm,
                    consultation_date,
                    vitals_payload.get("fc_bpm"),
                    vitals_payload.get("pa_systolique"),
                    vitals_payload.get("pa_diastolique"),
                    vitals_payload.get("temperature_c"),
                    vitals_payload.get("spo2_pct"),
                    vitals_payload.get("fr_min"),
                    vitals_payload.get("poids_kg"),
                    vitals_payload.get("taille_cm"),
                    vitals_payload.get("imc"),
                    "praticien",
                ),
            )
        conn.commit()
        created = get_patient_consultation_by_id(tenant_id, phone_norm, consultation_id)
        if created:
            return created
        raise RuntimeError("create_patient_consultation sqlite fetch failed")
    finally:
        conn.close()


def get_patient_consultation_context_pack(tenant_id: int, phone: str) -> Dict[str, Any]:
    consultations = list_patient_consultations(tenant_id, phone, limit=240)
    if not consultations:
        return {
            "dernieres_constantes": {},
            "poids_tendance_6m": {"debut_kg": None, "fin_kg": None, "delta_kg": None, "nb_pesees": 0},
            "pa_moyenne_3_dernieres": {"pas": None, "pad": None, "nb": 0},
            "frequentation": {"nb_12_mois": 0, "derniere_visite": None, "jours_depuis": None},
            "dernieres_consultations": [],
            "examens_recents": [],
        }

    def to_date(value: Any) -> Optional[date]:
        raw = _coerce_iso_date(value, fallback_today=False)
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except Exception:
            return None

    sorted_consultations = sorted(
        consultations,
        key=lambda c: (
            str(c.get("date_consultation") or ""),
            str(c.get("created_at") or ""),
        ),
        reverse=True,
    )

    vital_points: List[Dict[str, Any]] = []
    for consultation in sorted_consultations:
        measured = to_date(consultation.get("vitals", {}).get("measured_at") or consultation.get("date_consultation"))
        if not measured:
            continue
        vital_points.append(
            {
                "measured_at": measured,
                "vitals": dict(consultation.get("vitals") or {}),
            }
        )
    vital_points.sort(key=lambda item: item["measured_at"], reverse=True)

    latest_vitals: Dict[str, Dict[str, Any]] = {}
    for field in _CONSULTATION_VITAL_FIELDS:
        for point in vital_points:
            value = point["vitals"].get(field)
            if value in (None, ""):
                continue
            latest_vitals[field] = {
                "valeur": value,
                "date": point["measured_at"].isoformat(),
            }
            break

    six_months_ago = date.today() - timedelta(days=183)
    weight_points = [
        point for point in vital_points
        if point["measured_at"] >= six_months_ago and point["vitals"].get("poids_kg") not in (None, "")
    ]
    weight_points_sorted = sorted(weight_points, key=lambda item: item["measured_at"])
    if weight_points_sorted:
        start_weight = float(weight_points_sorted[0]["vitals"]["poids_kg"])
        end_weight = float(weight_points_sorted[-1]["vitals"]["poids_kg"])
        weight_trend = {
            "debut_kg": round(start_weight, 1),
            "fin_kg": round(end_weight, 1),
            "delta_kg": round(end_weight - start_weight, 1),
            "nb_pesees": len(weight_points_sorted),
        }
    else:
        weight_trend = {"debut_kg": None, "fin_kg": None, "delta_kg": None, "nb_pesees": 0}

    pa_points = [
        point for point in vital_points
        if point["vitals"].get("pa_systolique") not in (None, "")
        and point["vitals"].get("pa_diastolique") not in (None, "")
    ][:3]
    if pa_points:
        pas_vals = [float(point["vitals"]["pa_systolique"]) for point in pa_points]
        pad_vals = [float(point["vitals"]["pa_diastolique"]) for point in pa_points]
        pa_avg = {
            "pas": round(sum(pas_vals) / len(pas_vals)),
            "pad": round(sum(pad_vals) / len(pad_vals)),
            "nb": len(pa_points),
        }
    else:
        pa_avg = {"pas": None, "pad": None, "nb": 0}

    one_year_ago = date.today() - timedelta(days=365)
    consultations_12m = [
        c for c in sorted_consultations
        if (to_date(c.get("date_consultation")) or date.min) >= one_year_ago
    ]
    last_visit_date = max((to_date(c.get("date_consultation")) for c in consultations_12m), default=None)
    frequentation = {
        "nb_12_mois": len(consultations_12m),
        "derniere_visite": last_visit_date.isoformat() if last_visit_date else None,
        "jours_depuis": (date.today() - last_visit_date).days if last_visit_date else None,
    }

    latest_consults = []
    for item in sorted_consultations[:5]:
        latest_consults.append(
            {
                "date": str(item.get("date_consultation") or ""),
                "motif": str(item.get("motif") or ""),
                "impression": str(item.get("impression_clinique") or ""),
                "resume_ia": str(item.get("ia_resume") or ""),
            }
        )

    three_months_ago = date.today() - timedelta(days=90)
    exams_recent: List[str] = []
    seen_exams = set()
    for item in sorted_consultations:
        c_date = to_date(item.get("date_consultation"))
        if not c_date or c_date < three_months_ago:
            continue
        for exam in _consultation_parse_examens(item.get("examens_demandes")):
            key = exam.lower()
            if key in seen_exams:
                continue
            seen_exams.add(key)
            exams_recent.append(exam)

    return {
        "dernieres_constantes": latest_vitals,
        "poids_tendance_6m": weight_trend,
        "pa_moyenne_3_dernieres": pa_avg,
        "frequentation": frequentation,
        "dernieres_consultations": latest_consults,
        "examens_recents": exams_recent,
    }


def _normalize_patient_email(email: str) -> str:
    return (email or "").strip().lower()[:254]


def find_cabinet_client(
    tenant_id: int,
    *,
    phone: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Recherche un patient connu par téléphone (prioritaire) puis par email."""
    phone_norm = normalize_phone_number(phone or "")
    if phone_norm:
        profile = get_cabinet_client_by_phone(tenant_id, phone_norm)
        if profile:
            return profile
    email_norm = _normalize_patient_email(email or "")
    if email_norm:
        return get_cabinet_client_by_email(tenant_id, email_norm)
    return None


def _patient_display_name(profile: Optional[Dict[str, Any]]) -> str:
    if not profile:
        return "Patient sans nom"
    for key in ("display_name", "validated_name", "raw_name"):
        value = str(profile.get(key) or "").strip()
        if value:
            return value
    return "Patient sans nom"


def detect_patient_duplicate_conflicts(
    tenant_id: int,
    *,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    exclude_phone: Optional[str] = None,
) -> Dict[str, Any]:
    """Détecte si un téléphone ou un email appartient déjà à une autre fiche patient."""
    conflicts: list[Dict[str, Any]] = []
    phone_norm = normalize_phone_number(phone or "")
    exclude_norm = normalize_phone_number(exclude_phone or "") if exclude_phone else ""
    email_norm = _normalize_patient_email(email or "")

    if phone_norm and phone_norm != exclude_norm:
        existing_phone = get_cabinet_client_by_phone(tenant_id, phone_norm)
        if existing_phone:
            conflicts.append(
                {
                    "field": "phone",
                    "phone": existing_phone.get("phone") or phone_norm,
                    "display_name": _patient_display_name(existing_phone),
                    "email": existing_phone.get("email") or "",
                    "has_validated_name": bool(str(existing_phone.get("validated_name") or "").strip()),
                }
            )

    if email_norm and "@" in email_norm:
        existing_email = get_cabinet_client_by_email(tenant_id, email_norm)
        if existing_email:
            existing_phone_norm = normalize_phone_number(existing_email.get("phone") or "")
            if existing_phone_norm and existing_phone_norm != phone_norm and existing_phone_norm != exclude_norm:
                conflicts.append(
                    {
                        "field": "email",
                        "phone": existing_email.get("phone") or existing_phone_norm,
                        "display_name": _patient_display_name(existing_email),
                        "email": existing_email.get("email") or email_norm,
                    }
                )

    return {"has_conflict": bool(conflicts), "conflicts": conflicts}


def get_cabinet_client_by_email(tenant_id: int, email: str) -> Optional[Dict[str, Any]]:
    email_norm = _normalize_patient_email(email)
    if not email_norm or "@" not in email_norm:
        return None

    url = _pg_events_url()
    if url:
        try:

            from backend.pg_pool import pg_connection_for
            with pg_connection_for(url) as conn:
                _ensure_cabinet_clients_table_pg(conn)
                cols = _cabinet_client_select_columns_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT {cols}
                        FROM cabinet_clients
                        WHERE tenant_id = %s AND lower(trim(email)) = %s
                        ORDER BY updated_at DESC NULLS LAST
                        LIMIT 1
                        """,
                        (tenant_id, email_norm),
                    )
                    row = cur.fetchone()
                    if row:
                        return _cabinet_client_row_to_dict(row)
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "get_cabinet_client_by_email pg failed tenant_id=%s: %s",
                tenant_id,
                exc,
            )

    conn = get_conn()
    try:
        _ensure_cabinet_clients_table(conn)
        row = conn.execute(
            f"""
            SELECT {_CABINET_CLIENT_COLS_EXTENDED}
            FROM cabinet_clients
            WHERE tenant_id = ? AND lower(trim(email)) = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (tenant_id, email_norm),
        ).fetchone()
        if not row:
            return None
        return _cabinet_client_row_to_dict(dict(row))
    finally:
        conn.close()


def _cabinet_client_phone_lookup_keys(phone: str) -> List[str]:
    """Variantes de clé téléphone (E.164 + national FR) pour matcher d'anciennes fiches."""
    norm = normalize_phone_number(phone)
    if not norm:
        return []
    keys: List[str] = [norm]
    if norm.startswith("+33") and len(norm) == 12:
        keys.append(f"0{norm[3:]}")
    raw = re.sub(r"[^\d+]", "", str(phone or ""))
    if raw:
        keys.append(raw)
        if raw.startswith("0") and len(raw) == 10:
            keys.append(f"+33{raw[1:]}")
    return list(dict.fromkeys(k for k in keys if k))


def get_cabinet_client_by_phone(tenant_id: int, phone: str) -> Optional[Dict[str, Any]]:
    lookup_keys = _cabinet_client_phone_lookup_keys(phone)
    if not lookup_keys:
        return None

    url = _pg_events_url()
    if url:
        try:
            from backend.pg_pool import pg_connection_for

            with pg_connection_for(url) as conn:
                _ensure_cabinet_clients_table_pg(conn)
                cols = _cabinet_client_select_columns_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT {cols}
                        FROM cabinet_clients
                        WHERE tenant_id = %s AND phone = ANY(%s)
                        LIMIT 1
                        """,
                        (tenant_id, lookup_keys),
                    )
                    row = cur.fetchone()
                    if row:
                        return _cabinet_client_row_to_dict(row)
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "get_cabinet_client_by_phone pg failed tenant_id=%s phone=%s: %s",
                tenant_id,
                lookup_keys[0],
                exc,
            )

    conn = get_conn()
    try:
        _ensure_cabinet_clients_table(conn)
        placeholders = ",".join("?" for _ in lookup_keys)
        row = conn.execute(
            f"""
            SELECT {_CABINET_CLIENT_COLS_EXTENDED}
            FROM cabinet_clients
            WHERE tenant_id = ? AND phone IN ({placeholders})
            LIMIT 1
            """,
            (tenant_id, *lookup_keys),
        ).fetchone()
        if not row:
            return None
        return _cabinet_client_row_to_dict(dict(row))
    finally:
        conn.close()


def delete_cabinet_client_by_phone(tenant_id: int, phone: str) -> bool:
    """Supprime une fiche patient (table `cabinet_clients`) par téléphone normalisé."""
    phone_norm = normalize_phone_number(phone)
    if not phone_norm:
        return False

    url = _pg_events_url()
    if url:
        try:
            from backend.pg_pool import pg_connection_for

            with pg_connection_for(url) as conn:
                _ensure_cabinet_clients_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM cabinet_clients WHERE tenant_id = %s AND phone = %s",
                        (tenant_id, phone_norm),
                    )
                    deleted = cur.rowcount > 0
                conn.commit()
                return deleted
        except Exception:
            pass

    conn = get_conn()
    try:
        _ensure_cabinet_clients_table(conn)
        cur = conn.execute(
            "DELETE FROM cabinet_clients WHERE tenant_id = ? AND phone = ?",
            (tenant_id, phone_norm),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


class PatientPhoneChangeError(Exception):
    """Erreur métier lors du changement de numéro patient."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _apply_patient_phone_related_updates_pg(
    cur: Any,
    tenant_id: int,
    old_keys: List[str],
    new_norm: str,
) -> None:
    """Met à jour les tables liées au téléphone patient (Postgres)."""
    key_list = list(dict.fromkeys(k for k in old_keys if k))
    if not key_list:
        return

    def _safe_update(sql: str, params: tuple) -> None:
        try:
            cur.execute(sql, params)
        except Exception as exc:
            if "does not exist" in str(exc).lower():
                return
            raise

    _safe_update(
        "UPDATE patient_notes SET patient_phone = %s WHERE tenant_id = %s AND patient_phone = ANY(%s)",
        (new_norm, tenant_id, key_list),
    )
    _safe_update(
        "UPDATE patient_documents SET patient_phone = %s WHERE tenant_id = %s AND patient_phone = ANY(%s)",
        (new_norm, tenant_id, key_list),
    )
    _safe_update(
        "UPDATE human_handoffs SET patient_phone = %s WHERE tenant_id = %s AND patient_phone = ANY(%s)",
        (new_norm, tenant_id, key_list),
    )
    _safe_update(
        "UPDATE public_bookings SET patient_phone = %s WHERE tenant_id = %s AND patient_phone = ANY(%s)",
        (new_norm, tenant_id, key_list),
    )
    _safe_update(
        "UPDATE callback_requests SET phone = %s WHERE tenant_id = %s AND phone = ANY(%s)",
        (new_norm, tenant_id, key_list),
    )
    _safe_update(
        "UPDATE appointments SET contact = %s WHERE tenant_id = %s AND contact = ANY(%s)",
        (new_norm, tenant_id, key_list),
    )
    _safe_update(
        "UPDATE patient_questionnaires SET phone = %s WHERE tenant_id = %s AND phone = ANY(%s)",
        (new_norm, tenant_id, key_list),
    )


def _apply_patient_phone_related_updates_sqlite(
    conn: sqlite3.Connection,
    tenant_id: int,
    old_keys: List[str],
    new_norm: str,
) -> None:
    key_list = list(dict.fromkeys(k for k in old_keys if k))
    if not key_list:
        return
    placeholders = ",".join("?" for _ in key_list)

    def _safe_update(sql: str, params: tuple) -> None:
        try:
            conn.execute(sql, params)
        except Exception:
            pass

    _ensure_patient_notes_table(conn)
    _ensure_patient_documents_table(conn)
    _ensure_human_handoffs_table(conn)
    _safe_update(
        f"UPDATE patient_notes SET patient_phone = ? WHERE tenant_id = ? AND patient_phone IN ({placeholders})",
        (new_norm, tenant_id, *key_list),
    )
    _safe_update(
        f"UPDATE patient_documents SET patient_phone = ? WHERE tenant_id = ? AND patient_phone IN ({placeholders})",
        (new_norm, tenant_id, *key_list),
    )
    _safe_update(
        f"UPDATE human_handoffs SET patient_phone = ? WHERE tenant_id = ? AND patient_phone IN ({placeholders})",
        (new_norm, tenant_id, *key_list),
    )
    try:
        conn.execute(
            f"UPDATE public_bookings SET patient_phone = ? WHERE tenant_id = ? AND patient_phone IN ({placeholders})",
            (new_norm, tenant_id, *key_list),
        )
    except Exception:
        pass
    try:
        conn.execute(
            f"UPDATE callback_requests SET phone = ? WHERE tenant_id = ? AND phone IN ({placeholders})",
            (new_norm, tenant_id, *key_list),
        )
    except Exception:
        pass
    try:
        conn.execute(
            f"UPDATE appointments SET contact = ? WHERE tenant_id = ? AND contact IN ({placeholders})",
            (new_norm, tenant_id, *key_list),
        )
    except Exception:
        pass
    try:
        from backend.patient_questionnaire import _ensure_table_sqlite

        _ensure_table_sqlite(conn)
        conn.execute(
            f"UPDATE patient_questionnaires SET phone = ? WHERE tenant_id = ? AND phone IN ({placeholders})",
            (new_norm, tenant_id, *key_list),
        )
    except Exception:
        pass


def change_cabinet_client_phone(tenant_id: int, old_phone: str, new_phone: str) -> Optional[Dict[str, Any]]:
    """Change le numéro identifiant d'une fiche patient et propage aux données liées."""
    profile = get_cabinet_client_by_phone(tenant_id, old_phone)
    if not profile:
        raise PatientPhoneChangeError("not_found")

    old_stored = str(profile.get("phone") or "").strip()
    old_keys = list(dict.fromkeys(_cabinet_client_phone_lookup_keys(old_stored or old_phone)))
    if not old_keys:
        raise PatientPhoneChangeError("not_found")

    new_norm = normalize_phone_number(new_phone)
    if not new_norm or not is_valid_patient_phone(new_phone):
        raise PatientPhoneChangeError("invalid_phone")

    if normalize_phone_number(old_stored or old_phone) == new_norm:
        return profile

    if get_cabinet_client_by_phone(tenant_id, new_norm):
        raise PatientPhoneChangeError("phone_conflict")

    stored_old = old_stored or old_keys[0]
    url = _pg_events_url()
    if url:
        try:
            from backend.pg_pool import pg_connection_for

            with pg_connection_for(url) as conn:
                _ensure_cabinet_clients_table_pg(conn)
                with conn.cursor() as cur:
                    _apply_patient_phone_related_updates_pg(cur, tenant_id, old_keys, new_norm)
                    cur.execute(
                        """
                        UPDATE cabinet_clients
                        SET phone = %s, updated_at = now()
                        WHERE tenant_id = %s AND phone = %s
                        """,
                        (new_norm, tenant_id, stored_old),
                    )
                    if cur.rowcount == 0:
                        conn.rollback()
                        raise PatientPhoneChangeError("not_found")
                conn.commit()
            _reset_cabinet_client_cols_cache()
            try:
                from backend.patient_v2_db import migrate_patient_phone_v2_data

                migrate_patient_phone_v2_data(tenant_id, stored_old, new_norm, old_keys=old_keys)
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "change_cabinet_client_phone v2 migrate failed tenant=%s: %s",
                    tenant_id,
                    exc,
                )
            return get_cabinet_client_by_phone(tenant_id, new_norm)
        except PatientPhoneChangeError:
            raise
        except Exception as exc:
            logging.getLogger(__name__).error(
                "change_cabinet_client_phone pg failed tenant=%s: %s",
                tenant_id,
                exc,
            )
            raise PatientPhoneChangeError("failed") from exc

    conn = get_conn()
    try:
        _ensure_cabinet_clients_table(conn)
        _apply_patient_phone_related_updates_sqlite(conn, tenant_id, old_keys, new_norm)
        cur = conn.execute(
            """
            UPDATE cabinet_clients
            SET phone = ?, updated_at = datetime('now')
            WHERE tenant_id = ? AND phone = ?
            """,
            (new_norm, tenant_id, stored_old),
        )
        if cur.rowcount == 0:
            conn.rollback()
            raise PatientPhoneChangeError("not_found")
        conn.commit()
        try:
            from backend.patient_v2_db import migrate_patient_phone_v2_data

            migrate_patient_phone_v2_data(tenant_id, stored_old, new_norm, old_keys=old_keys)
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "change_cabinet_client_phone v2 migrate failed tenant=%s: %s",
                tenant_id,
                exc,
            )
        return get_cabinet_client_by_phone(tenant_id, new_norm)
    except PatientPhoneChangeError:
        raise
    except Exception as exc:
        logging.getLogger(__name__).error(
            "change_cabinet_client_phone sqlite failed tenant=%s: %s",
            tenant_id,
            exc,
        )
        raise PatientPhoneChangeError("failed") from exc
    finally:
        conn.close()


def get_cabinet_clients_by_phones(tenant_id: int, phones: List[str]) -> Dict[str, Dict[str, Any]]:
    """Retourne les fiches cabinet en lot, indexées par téléphone normalisé E.164."""
    lookup_keys: List[str] = []
    canonical_by_key: Dict[str, str] = {}
    for raw in phones:
        canon = normalize_phone_number(raw or "")
        if not canon:
            continue
        for key in _cabinet_client_phone_lookup_keys(raw or ""):
            lookup_keys.append(key)
            canonical_by_key[key] = canon
    if not lookup_keys:
        return {}
    lookup_keys = list(dict.fromkeys(lookup_keys))

    def _index_rows(rows: List[Any]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            stored = str(row.get("phone") if isinstance(row, dict) else row["phone"] or "").strip()
            canon = normalize_phone_number(stored)
            if not canon:
                continue
            out[canon] = _cabinet_client_row_to_dict(row if isinstance(row, dict) else dict(row))
        return out

    url = _pg_events_url()
    if url:
        try:
            from backend.pg_pool import pg_connection_for

            with pg_connection_for(url) as conn:
                _ensure_cabinet_clients_table_pg(conn)
                cols = _cabinet_client_select_columns_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT {cols}
                        FROM cabinet_clients
                        WHERE tenant_id = %s AND phone = ANY(%s)
                        """,
                        (tenant_id, lookup_keys),
                    )
                    rows = cur.fetchall()
                    return _index_rows(rows)
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "get_cabinet_clients_by_phones pg failed tenant_id=%s: %s",
                tenant_id,
                exc,
            )

    conn = get_conn()
    try:
        _ensure_cabinet_clients_table(conn)
        placeholders = ",".join("?" for _ in lookup_keys)
        rows = conn.execute(
            f"""
            SELECT {_CABINET_CLIENT_COLS_EXTENDED}
            FROM cabinet_clients
            WHERE tenant_id = ? AND phone IN ({placeholders})
            """,
            [tenant_id, *lookup_keys],
        ).fetchall()
        return _index_rows([dict(row) for row in rows])
    finally:
        conn.close()


def _list_cabinet_clients_with_cols(
    tenant_id: int,
    *,
    cols: str,
    limit: int = 200,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Liste les patients/clients d'un tenant (colonnes configurables), triés par dernière mise à jour."""
    _select = """
        SELECT {cols}
        FROM cabinet_clients
        WHERE tenant_id = {ph}
        ORDER BY updated_at DESC
        LIMIT {lph} OFFSET {oph}
    """
    url = _pg_events_url()
    if url:
        try:
            from backend.pg_pool import pg_connection_for
            with pg_connection_for(url) as conn:
                _ensure_cabinet_clients_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        _select.format(cols=cols, ph="%s", lph="%s", oph="%s"),
                        (tenant_id, limit, offset),
                    )
                    return [_cabinet_client_row_to_dict(r) for r in cur.fetchall()]
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "list_cabinet_clients pg failed tenant_id=%s: %s",
                tenant_id,
                exc,
            )

    conn = get_conn()
    try:
        _ensure_cabinet_clients_table(conn)
        rows = conn.execute(
            _select.format(cols=cols, ph="?", lph="?", oph="?"),
            (tenant_id, limit, offset),
        ).fetchall()
        return [_cabinet_client_row_to_dict(dict(r)) for r in rows]
    finally:
        conn.close()


def list_cabinet_clients(tenant_id: int, *, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
    """Liste tous les patients/clients d'un tenant, triés par dernière mise à jour."""
    url = _pg_events_url()
    if url:
        try:
            from backend.pg_pool import pg_connection_for
            with pg_connection_for(url) as conn:
                cols = _cabinet_client_select_columns_pg(conn)
                return _list_cabinet_clients_with_cols(
                    tenant_id, cols=cols, limit=limit, offset=offset,
                )
        except Exception:
            pass
    return _list_cabinet_clients_with_cols(
        tenant_id, cols=_CABINET_CLIENT_COLS_EXTENDED, limit=limit, offset=offset,
    )


def list_cabinet_clients_compact(tenant_id: int, *, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
    """Liste minimale pour la sidebar patient (moins de colonnes, plus rapide)."""
    return _list_cabinet_clients_with_cols(
        tenant_id, cols=_CABINET_CLIENT_COLS_COMPACT, limit=limit, offset=offset,
    )


def _patient_search_tokens(q: str) -> List[tuple]:
    """
    Découpe la requête en tokens (texte ou chiffres) pour une recherche ET logique.
    Ex. « Jean Dupont » → deux tokens texte ; « +33612 » → token chiffres.
    """
    tokens: List[tuple] = []
    for raw in (q or "").split():
        t = raw.strip()
        if len(t) < 2:
            continue
        if "@" in t:
            tokens.append(("text", t.lower()))
            continue
        d = re.sub(r"\D", "", t)
        phoneish = re.sub(r"[\s\+\-\.\(\)]", "", t)
        if phoneish == d and d:
            if len(d) >= 3:
                tokens.append(("digits", d))
            continue
        tokens.append(("text", t.lower()))
    return tokens


def _accent_fold(s: str) -> str:
    """Retire accents/diacritiques pour élargir la recherche sans extension DB."""
    if not s:
        return ""
    try:
        nk = unicodedata.normalize("NFKD", str(s))
        return "".join(c for c in nk if unicodedata.category(c) != "Mn")
    except Exception:
        return str(s)


def _search_cabinet_clients_fallback_wide(tenant_id: int, q: str, *, limit: int) -> List[Dict[str, Any]]:
    """
    Quand la requête SQL stricte (AND sur les mots) ne renvoie rien :
    scorer les fiches en « au moins un » token texte OU chiffre (OR),
    fuzzy léger pour prénom/nom quasi identiques mal orthographiés.
    Balaye au plus `_SCAN` lignes récentes (updated_at DESC).
    """
    import difflib

    q_clean = (q or "").strip()
    tokens = _patient_search_tokens(q_clean)
    if not tokens:
        return []

    _SCAN = 4000
    try:
        pool = list_cabinet_clients(tenant_id, limit=_SCAN, offset=0)
    except Exception:
        pool = []

    q_compact = re.sub(r"\s+", "", _accent_fold(q_clean).lower())

    ranked: List[tuple[int, int, Dict[str, Any]]] = []

    def row_ts(rec: Dict[str, Any]) -> int:
        raw = str(rec.get("updated_at") or rec.get("created_at") or "")
        if not raw:
            return 0
        try:
            return int(datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp())
        except Exception:
            try:
                return int(datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S").timestamp())
            except Exception:
                return 0

    for row in pool:
        phones_digits = re.sub(r"\D", "", str(row.get("phone") or ""))
        nm_raw = " ".join(
            [
                str(row.get("display_name") or ""),
                str(row.get("validated_name") or ""),
                str(row.get("raw_name") or ""),
                str(row.get("email") or ""),
                phones_digits,
            ]
        ).strip()

        nm = _accent_fold(nm_raw).lower()
        nm_compact = re.sub(r"\s+", "", nm)
        tokens_words = sorted({w for w in re.findall(r"[a-z0-9]{2,}", nm) if len(w) >= 2})

        matched = 0
        fuzzy_hits = 0

        for typ, tok in tokens:
            if typ == "digits":
                dg = re.sub(r"\D", "", str(tok))
                if dg and phones_digits and any(p in phones_digits for p in _phone_digit_search_patterns(dg)):
                    matched += 1
            else:
                t = _accent_fold(tok).lower()
                if len(t) < 2:
                    continue
                if t in nm or (phones_digits and t in phones_digits):
                    matched += 1
                    continue

                fuzzy_ok = False
                if len(t) >= 3 and tokens_words:
                    close = difflib.get_close_matches(t, tokens_words, n=1, cutoff=0.78)
                    if close:
                        fuzzy_ok = True
                    elif len(t) >= 4:
                        for w in tokens_words:
                            if abs(len(w) - len(t)) > 5:
                                continue
                            try:
                                if len(t) <= 12 and len(w) <= 12 and difflib.SequenceMatcher(a=t, b=w).ratio() >= 0.78:
                                    fuzzy_ok = True
                                    break
                            except Exception:
                                continue

                if fuzzy_ok:
                    matched += 1
                    fuzzy_hits += 1

        full_bonus = 0
        if len(q_compact) >= 6 and q_compact in nm_compact:
            full_bonus += 4

        if matched == 0 and full_bonus == 0:
            continue

        score = matched * 8 + fuzzy_hits * 4 + full_bonus
        ranked.append((score, row_ts(row), row))

    ranked.sort(key=lambda tup: (-tup[0], -tup[1]))

    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for _sc, _ts, row in ranked:
        k = normalize_phone_number(str(row.get("phone") or ""))
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(row)
        if len(out) >= limit:
            break

    return out[:limit]


def search_cabinet_clients_with_fallback(tenant_id: int, q: str, *, limit: int = 50) -> List[Dict[str, Any]]:
    strict = search_cabinet_clients(tenant_id, q, limit=min(max(limit * 6, limit), 200))
    if strict:
        return strict[:limit]
    return _search_cabinet_clients_fallback_wide(tenant_id, q, limit=limit)


def search_cabinet_clients(tenant_id: int, q: str, *, limit: int = 15) -> List[Dict[str, Any]]:
    """Recherche patients par nom affiché, email ou téléphone (tous tokens doivent matcher)."""
    q_clean = (q or "").strip()
    tokens = _patient_search_tokens(q_clean)
    if not tokens:
        return []

    url = _pg_events_url()
    if url:
        try:
            clause_parts: List[str] = []
            params_pg: List[Any] = []
            for typ, tok in tokens:
                if typ == "text":
                    inner_or: List[str] = []
                    for t_sub in dict.fromkeys((tok, _accent_fold(tok).lower())):
                        if len(t_sub) < 2:
                            continue
                        pat = f"%{t_sub}%"
                        inner_or.append(
                            "(display_name ILIKE %s OR validated_name ILIKE %s OR raw_name ILIKE %s "
                            "OR COALESCE(email,'') ILIKE %s OR phone ILIKE %s)"
                        )
                        params_pg.extend([pat, pat, pat, pat, pat])
                    if inner_or:
                        clause_parts.append("(" + " OR ".join(inner_or) + ")")
                elif typ == "digits":
                    d_patterns = _phone_digit_search_patterns(tok)
                    if not d_patterns:
                        clause_parts.append("FALSE")
                    else:
                        parts_sql = " OR ".join(
                            "(regexp_replace(COALESCE(phone, ''), '\\D', '', 'g') LIKE %s)" for _ in d_patterns
                        )
                        clause_parts.append(f"({parts_sql})")
                        for dp in d_patterns:
                            params_pg.append(f"%{dp}%")

            where_sql = " AND ".join(clause_parts)
            params_pg_final = [tenant_id] + params_pg + [limit]
            from backend.pg_pool import pg_connection_for
            with pg_connection_for(url) as conn:
                _ensure_cabinet_clients_table_pg(conn)
                cols = _cabinet_client_select_columns_pg(conn)
                sql = (
                    f"SELECT {cols} FROM cabinet_clients WHERE tenant_id = %s AND "
                    + where_sql
                    + " ORDER BY updated_at DESC LIMIT %s"
                )
                with conn.cursor() as cur:
                    cur.execute(sql, params_pg_final)
                    return [_cabinet_client_row_to_dict(r) for r in cur.fetchall()]
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "search_cabinet_clients pg failed tenant_id=%s q=%r: %s",
                tenant_id,
                q_clean[:40],
                exc,
            )

    clause_parts_sq: List[str] = []
    params_sq: List[Any] = []
    for typ, tok in tokens:
        if typ == "text":
            inner_bits: List[str] = []
            for t_sub in dict.fromkeys((tok, _accent_fold(tok).lower())):
                if len(t_sub) < 2:
                    continue
                inner_bits.append(
                    "("
                    "LOWER(COALESCE(display_name,'')) LIKE ? ESCAPE '\\' OR "
                    "LOWER(COALESCE(validated_name,'')) LIKE ? ESCAPE '\\' OR "
                    "LOWER(COALESCE(raw_name,'')) LIKE ? ESCAPE '\\' OR "
                    "LOWER(COALESCE(email,'')) LIKE ? ESCAPE '\\' OR "
                    "LOWER(COALESCE(phone,'')) LIKE ? ESCAPE '\\'"
                    ")"
                )
                escaped = t_sub.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                like_pat = f"%{escaped}%"
                params_sq.extend([like_pat, like_pat, like_pat, like_pat, like_pat])
            if inner_bits:
                clause_parts_sq.append("(" + " OR ".join(inner_bits) + ")")
        elif typ == "digits":
            d_patterns = _phone_digit_search_patterns(tok)
            if not d_patterns:
                clause_parts_sq.append("(0 = 1)")
            else:
                phone_flat = (
                    "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE("
                    "COALESCE(phone,''),'+',''),' ',''),'-',''),'.',''),'(',''),')','')"
                )
                bits = [f"({phone_flat} LIKE ? ESCAPE '\\')" for _ in d_patterns]
                clause_parts_sq.append("(" + " OR ".join(bits) + ")")
                for dp in d_patterns:
                    esc_d = dp.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                    params_sq.append(f"%{esc_d}%")

    where_sq = " AND ".join(clause_parts_sq)
    sql_sq = (
        "SELECT "
        + _cols
        + """
        FROM cabinet_clients
        WHERE tenant_id = ?
        AND """
        + where_sq
        + " ORDER BY updated_at DESC LIMIT ?"
    )

    conn = get_conn()
    try:
        _ensure_cabinet_clients_table(conn)
        rows = conn.execute(sql_sq, (tenant_id, *params_sq, limit)).fetchall()
        return [_cabinet_client_row_to_dict(dict(r)) for r in rows]
    finally:
        conn.close()


def upsert_cabinet_client(
    tenant_id: int,
    phone: str,
    *,
    raw_name: Optional[str] = None,
    validated_name: Optional[str] = None,
    source_call_id: Optional[str] = None,
    last_call_id: Optional[str] = None,
    last_booking_start: Optional[str] = None,
    last_booking_end: Optional[str] = None,
    last_booking_motif: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    phone_norm = normalize_phone_number(phone)
    if not phone_norm:
        return None

    clean_raw_name = (raw_name or "").strip()[:160] or None
    clean_validated_name = (validated_name or "").strip()[:160] or None
    display_name = clean_validated_name or clean_raw_name or None
    validation_status = "validated" if clean_validated_name else "pending"
    clean_source_call_id = (source_call_id or "").strip()[:120] or None
    clean_last_call_id = (last_call_id or "").strip()[:120] or None
    clean_booking_start = (last_booking_start or "").strip()[:64] or None
    clean_booking_end = (last_booking_end or "").strip()[:64] or None
    clean_booking_motif = (last_booking_motif or "").strip()[:240] or None

    url = _pg_events_url()
    if url:
        try:

            from backend.pg_pool import pg_connection_for
            with pg_connection_for(url) as conn:
                _ensure_cabinet_clients_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO cabinet_clients (
                            tenant_id, phone, raw_name, validated_name, display_name, validation_status,
                            source_call_id, last_call_id, last_booking_start, last_booking_end, last_booking_motif, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                        ON CONFLICT (tenant_id, phone)
                        DO UPDATE SET
                            raw_name = COALESCE(EXCLUDED.raw_name, cabinet_clients.raw_name),
                            validated_name = COALESCE(EXCLUDED.validated_name, cabinet_clients.validated_name),
                            display_name = COALESCE(EXCLUDED.display_name, cabinet_clients.display_name, cabinet_clients.raw_name),
                            validation_status = CASE
                                WHEN COALESCE(EXCLUDED.validated_name, cabinet_clients.validated_name) IS NOT NULL
                                    AND TRIM(COALESCE(EXCLUDED.validated_name, cabinet_clients.validated_name)) != ''
                                THEN 'validated'
                                ELSE COALESCE(EXCLUDED.validation_status, cabinet_clients.validation_status)
                            END,
                            source_call_id = COALESCE(EXCLUDED.source_call_id, cabinet_clients.source_call_id),
                            last_call_id = COALESCE(EXCLUDED.last_call_id, cabinet_clients.last_call_id),
                            last_booking_start = COALESCE(EXCLUDED.last_booking_start, cabinet_clients.last_booking_start),
                            last_booking_end = COALESCE(EXCLUDED.last_booking_end, cabinet_clients.last_booking_end),
                            last_booking_motif = COALESCE(EXCLUDED.last_booking_motif, cabinet_clients.last_booking_motif),
                            updated_at = now()
                        """,
                        (
                            tenant_id,
                            phone_norm,
                            clean_raw_name,
                            clean_validated_name,
                            display_name,
                            validation_status,
                            clean_source_call_id,
                            clean_last_call_id,
                            clean_booking_start,
                            clean_booking_end,
                            clean_booking_motif,
                        ),
                    )
                    conn.commit()
        except Exception:
            pass

    conn = get_conn()
    try:
        _ensure_cabinet_clients_table(conn)
        conn.execute(
            """
            INSERT INTO cabinet_clients (
                tenant_id, phone, raw_name, validated_name, display_name, validation_status,
                source_call_id, last_call_id, last_booking_start, last_booking_end, last_booking_motif, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, phone)
            DO UPDATE SET
                raw_name = COALESCE(excluded.raw_name, cabinet_clients.raw_name),
                validated_name = COALESCE(excluded.validated_name, cabinet_clients.validated_name),
                display_name = COALESCE(excluded.display_name, cabinet_clients.display_name, cabinet_clients.raw_name),
                validation_status = CASE
                    WHEN COALESCE(excluded.validated_name, cabinet_clients.validated_name) IS NOT NULL
                        AND TRIM(COALESCE(excluded.validated_name, cabinet_clients.validated_name)) != ''
                    THEN 'validated'
                    ELSE COALESCE(excluded.validation_status, cabinet_clients.validation_status)
                END,
                source_call_id = COALESCE(excluded.source_call_id, cabinet_clients.source_call_id),
                last_call_id = COALESCE(excluded.last_call_id, cabinet_clients.last_call_id),
                last_booking_start = COALESCE(excluded.last_booking_start, cabinet_clients.last_booking_start),
                last_booking_end = COALESCE(excluded.last_booking_end, cabinet_clients.last_booking_end),
                last_booking_motif = COALESCE(excluded.last_booking_motif, cabinet_clients.last_booking_motif),
                updated_at = excluded.updated_at
            """,
            (
                tenant_id,
                phone_norm,
                clean_raw_name,
                clean_validated_name,
                display_name,
                validation_status,
                clean_source_call_id,
                clean_last_call_id,
                clean_booking_start,
                clean_booking_end,
                clean_booking_motif,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return get_cabinet_client_by_phone(tenant_id, phone_norm)


def consent_obtained_exists(client_id: int, call_id: str) -> bool:
    """True si consent_obtained déjà persisté pour ce call (idempotence retry)."""
    call_id_norm = (call_id or "").strip()
    if not call_id_norm:
        return False
    try:
        if _should_use_pg_events_dual_write():
            from backend.ivr_events_pg import consent_obtained_exists_pg
            if consent_obtained_exists_pg(client_id, call_id_norm):
                return True
    except Exception:
        pass
    conn = get_conn()
    try:
        _ensure_ivr_tables(conn)
        row = conn.execute(
            "SELECT 1 FROM ivr_events WHERE client_id = ? AND call_id = ? AND event = 'consent_obtained' LIMIT 1",
            (client_id, call_id_norm),
        ).fetchone()
        return row is not None
    except Exception:
        return False
    finally:
        conn.close()


def create_ivr_event(
    client_id: int,
    call_id: str,
    event: str,
    context: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """
    Insertion dans ivr_events (rapport quotidien).
    Dual-write : SQLite + Postgres si USE_PG_EVENTS=true.
    created_at partagé pour idempotence PG (ON CONFLICT DO NOTHING sur retry).
    """
    created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:26]  # microsec
    call_id_norm = call_id or ""

    conn = get_conn()
    try:
        _ensure_ivr_tables(conn)
        conn.execute(
            """INSERT INTO ivr_events (client_id, call_id, event, context, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (client_id, call_id_norm, event, context or None, reason or None, created_at),
        )
        conn.commit()
    finally:
        conn.close()

    # Dual-write Postgres (warning si échec — les dashboards lisent Postgres)
    try:
        if _should_use_pg_events_dual_write():
            from backend.ivr_events_pg import create_ivr_event_pg
            ok = create_ivr_event_pg(
                client_id, call_id_norm, event, context, reason, created_at=created_at
            )
            if not ok:
                logger.warning("ivr_events pg dual-write returned False client_id=%s event=%s call_id=%s",
                               client_id, event, (call_id_norm or "")[:24])
    except Exception as e:
        logger.warning("ivr_events pg dual-write exception client_id=%s event=%s err=%s",
                       client_id, event, str(e)[:100])


def _migrate_sqlite_add_tenant_id(conn: sqlite3.Connection) -> None:
    """Migration: ajoute tenant_id aux tables slots/appointments si absente (DB existantes)."""
    for table, col in [("slots", "tenant_id"), ("appointments", "tenant_id")]:
        try:
            cur = conn.execute(f"PRAGMA table_info({table})")
            if any(r[1] == col for r in cur.fetchall()):
                continue
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} INTEGER NOT NULL DEFAULT 1")
        except Exception:
            pass


def _migrate_sqlite_add_booking_origin(conn: sqlite3.Connection) -> None:
    try:
        cur = conn.execute("PRAGMA table_info(appointments)")
        cols = {r[1] for r in cur.fetchall()}
        if "booking_origin" not in cols:
            conn.execute("ALTER TABLE appointments ADD COLUMN booking_origin TEXT")
    except Exception:
        pass


def _migrate_sqlite_add_google_event_id(conn: sqlite3.Connection) -> None:
    try:
        cur = conn.execute("PRAGMA table_info(appointments)")
        cols = {r[1] for r in cur.fetchall()}
        if "google_event_id" not in cols:
            conn.execute("ALTER TABLE appointments ADD COLUMN google_event_id TEXT")
    except Exception:
        pass


def _migrate_sqlite_add_booking_code(conn: sqlite3.Connection) -> None:
    try:
        cur = conn.execute("PRAGMA table_info(appointments)")
        cols = {r[1] for r in cur.fetchall()}
        if "booking_code" not in cols:
            conn.execute("ALTER TABLE appointments ADD COLUMN booking_code TEXT")
    except Exception:
        pass


def init_db(days: int = 30) -> None:
    conn = get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL DEFAULT 1,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                is_booked INTEGER DEFAULT 0,
                UNIQUE(tenant_id, date, time)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL DEFAULT 1,
                name TEXT NOT NULL,
                contact TEXT NOT NULL,
                contact_type TEXT NOT NULL,
                motif TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(slot_id) REFERENCES slots(id)
            )
        """)
        _migrate_sqlite_add_tenant_id(conn)
        _migrate_sqlite_add_booking_origin(conn)
        _migrate_sqlite_add_google_event_id(conn)
        _migrate_sqlite_add_booking_code(conn)
        _ensure_ivr_tables(conn)
        _ensure_tenants_tables(conn)
        try:
            from backend.patient_v2_db import ensure_patient_v2_schema

            ensure_patient_v2_schema()
        except Exception:
            pass

        # Seed slots (Lundi-Samedi) — tenant_id=1 par défaut
        for day in range(1, days + 1):
            target_date = datetime.now() + timedelta(days=day)
            if target_date.weekday() < 6:  # Lundi-Samedi
                d = target_date.strftime("%Y-%m-%d")
                for t in SLOT_TIMES:
                    conn.execute(
                        "INSERT OR IGNORE INTO slots (tenant_id, date, time) VALUES (1, ?, ?)",
                        (d, t)
                    )

        conn.commit()
    finally:
        conn.close()


def cleanup_old_slots(tenant_id: int = 1) -> None:
    """
    Supprime les slots passés et garantit au moins TARGET_MIN_SLOTS slots futurs
    (lundi-vendredi uniquement). SQLite uniquement. Scopé par tenant_id.
    """
    from backend import config
    config._sqlite_guard("db.cleanup_old_slots")
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        today = datetime.now().strftime("%Y-%m-%d")
        conn.execute("DELETE FROM slots WHERE tenant_id = ? AND date < ?", (tenant_id, today))
        cur = conn.execute(
            "SELECT COUNT(*) as c FROM slots WHERE tenant_id = ? AND date >= ?",
            (tenant_id, today),
        )
        count = int(cur.fetchone()["c"])
        missing = max(0, TARGET_MIN_SLOTS - count)
        if missing == 0:
            conn.commit()
            return
        day_offset = 1
        added = 0
        while added < missing:
            if day_offset > MAX_DAYS_AHEAD:
                break
            target_date = datetime.now() + timedelta(days=day_offset)
            if target_date.weekday() < 6:  # Lundi-Samedi
                d = target_date.strftime("%Y-%m-%d")
                for t in SLOT_TIMES:
                    if added >= missing:
                        break
                    before = conn.total_changes
                    conn.execute(
                        "INSERT OR IGNORE INTO slots (tenant_id, date, time) VALUES (?, ?, ?)",
                        (tenant_id, d, t),
                    )
                    if conn.total_changes > before:
                        added += 1
            day_offset += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def count_free_slots(limit: int = 1000, tenant_id: int = 1) -> int:
    """PG-first puis SQLite. tenant_id pour isolation multi-tenant."""
    from backend import config
    if config.USE_PG_SLOTS:
        try:
            from backend.slots_pg import pg_cleanup_and_ensure_slots, pg_count_free_slots
            pg_cleanup_and_ensure_slots(tenant_id)
            n = pg_count_free_slots(tenant_id)
            if n is not None:
                return n
        except Exception:
            pass
    config._sqlite_guard("db.count_free_slots")
    cleanup_old_slots(tenant_id)
    conn = get_conn()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        cur = conn.execute(
            "SELECT COUNT(*) AS c FROM slots WHERE tenant_id = ? AND is_booked=0 AND date >= ?",
            (tenant_id, today),
        )
        return int(cur.fetchone()["c"])
    finally:
        conn.close()


def list_free_slots(limit: int = 3, pref: Optional[str] = None, tenant_id: int = 1) -> List[Dict]:
    """
    Liste les créneaux libres. PG-first puis SQLite.
    pref: "matin" (avant 12h), "après-midi" (14h-18h), "soir" (>=18h).
    """
    from backend import config
    if config.USE_PG_SLOTS:
        try:
            from backend.slots_pg import pg_cleanup_and_ensure_slots, pg_list_free_slots
            pg_cleanup_and_ensure_slots(tenant_id)
            raw = pg_list_free_slots(tenant_id, limit=limit, pref=pref)
            if raw is not None:
                return [{"id": r["id"], "date": r["date"], "time": r["time"]} for r in raw]
        except Exception:
            pass
    config._sqlite_guard("db.list_free_slots")
    cleanup_old_slots(tenant_id)
    conn = get_conn()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        now_time = datetime.now().strftime("%H:%M")
        time_condition = ""
        if pref == "matin":
            time_condition = " AND time < '12:00'"
        elif pref == "après-midi":
            time_condition = " AND time >= '14:00' AND time < '18:00'"
        elif pref == "soir":
            time_condition = " AND time >= '18:00'"
        cur = conn.execute(
            f"""
            SELECT id, date, time 
            FROM slots 
            WHERE tenant_id = ? AND is_booked=0
              AND (date > ? OR (date = ? AND time >= ?)){time_condition}
            ORDER BY date ASC, time ASC 
            LIMIT ?
            """,
            (tenant_id, today, today, now_time, limit),
        )
        out = []
        for r in cur.fetchall():
            out.append({"id": int(r["id"]), "date": r["date"], "time": r["time"]})
        return out
    finally:
        conn.close()


def find_slot_id_by_datetime(date_str: str, time_str: str, tenant_id: int = 1) -> Optional[int]:
    """
    Trouve l'id d'un slot libre par date et heure (ex: "2026-02-16", "09:00").
    Retourne None si non trouvé ou déjà réservé. SQLite uniquement (pas de branche PG).
    """
    from backend import config
    config._sqlite_guard("db.find_slot_id_by_datetime")
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT id FROM slots WHERE tenant_id = ? AND date=? AND time=? AND is_booked=0 LIMIT 1",
            (tenant_id, date_str[:10], time_str[:5] if time_str else "09:00"),
        )
        row = cur.fetchone()
        return int(row["id"]) if row else None
    finally:
        conn.close()


def ensure_slot_id_by_datetime(date_str: str, time_str: str, tenant_id: int = 1) -> Optional[int]:
    """
    Garantit l'existence d'un slot local pour une date/heure donnée et retourne son id.
    PG-first puis SQLite.
    """
    from backend import config
    if config.USE_PG_SLOTS:
        try:
            from backend.slots_pg import pg_ensure_slot_id_by_datetime

            slot_id = pg_ensure_slot_id_by_datetime(date_str, time_str, tenant_id=tenant_id)
            if slot_id is not None:
                return slot_id
        except Exception:
            pass
    config._sqlite_guard("db.ensure_slot_id_by_datetime")
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO slots (tenant_id, date, time, is_booked) VALUES (?, ?, ?, 0)",
            (tenant_id, date_str[:10], (time_str or "09:00")[:5]),
        )
        cur = conn.execute(
            "SELECT id FROM slots WHERE tenant_id = ? AND date = ? AND time = ? LIMIT 1",
            (tenant_id, date_str[:10], (time_str or "09:00")[:5]),
        )
        row = cur.fetchone()
        conn.commit()
        return int(row["id"]) if row else None
    finally:
        conn.close()


def attach_appointment_google_event_id(
    tenant_id: int,
    google_event_id: str,
    *,
    appointment_id: Optional[int] = None,
    slot_id: Optional[int] = None,
) -> bool:
    """Associe un événement Google à un RDV local (PG-first puis SQLite)."""
    event_id = str(google_event_id or "").strip()
    if not event_id or (not appointment_id and not slot_id):
        return False
    from backend import config

    if config.USE_PG_SLOTS:
        try:
            from backend.slots_pg import pg_attach_google_event_id

            result = pg_attach_google_event_id(
                tenant_id,
                event_id,
                appointment_id=appointment_id,
                slot_id=slot_id,
            )
            if result is not None:
                return result
        except Exception:
            pass

    config._sqlite_guard("db.attach_appointment_google_event_id")
    conn = get_conn()
    try:
        _migrate_sqlite_add_google_event_id(conn)
        if appointment_id:
            cur = conn.execute(
                """
                UPDATE appointments
                SET google_event_id = ?
                WHERE tenant_id = ? AND id = ?
                """,
                (event_id[:256], tenant_id, appointment_id),
            )
        else:
            cur = conn.execute(
                """
                UPDATE appointments
                SET google_event_id = ?
                WHERE tenant_id = ? AND slot_id = ?
                """,
                (event_id[:256], tenant_id, slot_id),
            )
        if cur.rowcount == 0:
            conn.rollback()
            return False
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def book_slot_atomic(
    slot_id: int,
    name: str,
    contact: str,
    contact_type: str,
    motif: str,
    tenant_id: int = 1,
    booking_origin: Optional[str] = None,
    google_event_id: Optional[str] = None,
    booking_code: Optional[str] = None,
) -> bool:
    """
    Book atomique. PG-first puis SQLite.
    Returns False if slot already booked.
    """
    from backend import config
    if config.USE_PG_SLOTS:
        try:
            from backend.slots_pg import pg_book_slot_atomic
            result = pg_book_slot_atomic(
                tenant_id,
                slot_id,
                name,
                contact,
                contact_type,
                motif,
                booking_origin=booking_origin,
                google_event_id=google_event_id,
                booking_code=booking_code,
            )
            if result is not None:
                return result
        except Exception:
            pass
    config._sqlite_guard("db.book_slot_atomic")
    conn = get_conn()
    try:
        _migrate_sqlite_add_booking_origin(conn)
        _migrate_sqlite_add_google_event_id(conn)
        _migrate_sqlite_add_booking_code(conn)
        conn.execute("BEGIN")
        conn.execute(
            "UPDATE slots SET is_booked=1 WHERE id=? AND tenant_id=? AND is_booked=0",
            (slot_id, tenant_id),
        )
        if conn.total_changes == 0:
            conn.rollback()
            return False

        from backend.booking_code import create_unique_booking_code_sqlite

        ge = (google_event_id or "").strip()[:256] or None
        stored_code = (booking_code or "").strip().upper()[:8] or None
        if not stored_code:
            stored_code = create_unique_booking_code_sqlite(conn, tenant_id)
        conn.execute(
            """
            INSERT INTO appointments (
                tenant_id, slot_id, name, contact, contact_type, motif, created_at,
                booking_origin, google_event_id, booking_code
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                slot_id,
                name,
                contact,
                contact_type,
                motif,
                datetime.utcnow().isoformat(),
                booking_origin,
                ge,
                stored_code,
            ),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def find_booking_by_name(name: str, tenant_id: int = 1) -> Optional[Dict]:
    """
    Recherche un RDV par nom. PG-first puis SQLite.
    """
    if not name or not name.strip():
        return None
    from backend import config
    if config.USE_PG_SLOTS:
        try:
            from backend.slots_pg import pg_find_booking_by_name
            r = pg_find_booking_by_name(tenant_id, name.strip())
            if r is not None:
                return r
        except Exception:
            pass
    config._sqlite_guard("db.find_booking_by_name")
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif, s.date, s.time
            FROM appointments a
            JOIN slots s ON s.id = a.slot_id AND s.tenant_id = a.tenant_id
            WHERE a.tenant_id = ? AND LOWER(TRIM(a.name)) = LOWER(TRIM(?))
            ORDER BY a.created_at DESC
            LIMIT 1
            """,
            (tenant_id, name.strip()),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "slot_id": row["slot_id"],
            "name": row["name"],
            "contact": row["contact"],
            "contact_type": row["contact_type"],
            "motif": row["motif"],
            "date": row["date"],
            "time": row["time"],
        }
    finally:
        conn.close()


def cancel_booking_sqlite(booking: Dict, tenant_id: int = 1) -> bool:
    """
    Annule un RDV local : supprime l'appointment et libère le slot. PG-first puis SQLite.
    """
    slot_id = booking.get("slot_id")
    appt_id = booking.get("id")
    from backend import config
    if config.USE_PG_SLOTS:
        try:
            from backend.slots_pg import pg_cancel_booking
            result = pg_cancel_booking(tenant_id, booking)
            if result is not None:
                return result
        except Exception:
            pass
    config._sqlite_guard("db.cancel_booking_sqlite")
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        if slot_id is not None:
            conn.execute("DELETE FROM appointments WHERE slot_id = ? AND tenant_id = ?", (slot_id, tenant_id))
        elif appt_id is not None:
            cur = conn.execute("SELECT slot_id FROM appointments WHERE id = ? AND tenant_id = ?", (appt_id, tenant_id))
            r = cur.fetchone()
            if not r:
                conn.rollback()
                return False
            slot_id = r["slot_id"]
            conn.execute("DELETE FROM appointments WHERE id = ? AND tenant_id = ?", (appt_id, tenant_id))
        else:
            conn.rollback()
            return False
        if conn.total_changes == 0:
            conn.rollback()
            return False
        conn.execute("UPDATE slots SET is_booked = 0 WHERE id = ? AND tenant_id = ?", (slot_id, tenant_id))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reschedule_booking_atomic(appt_id: int, new_slot_id: int, tenant_id: int = 1) -> bool:
    """
    Déplace un RDV local : réserve le nouveau slot, recrée l'appointment, libère l'ancien slot.
    PG-first puis SQLite.
    """
    if not appt_id or not new_slot_id:
        return False
    from backend import config
    if config.USE_PG_SLOTS:
        try:
            from backend.slots_pg import pg_reschedule_booking_atomic
            result = pg_reschedule_booking_atomic(tenant_id, appt_id, new_slot_id)
            if result is not None:
                return result
        except Exception:
            pass

    config._sqlite_guard("db.reschedule_booking_atomic")
    conn = get_conn()
    try:
        _migrate_sqlite_add_booking_origin(conn)
        _migrate_sqlite_add_google_event_id(conn)
        _migrate_sqlite_add_booking_code(conn)
        conn.execute("BEGIN")
        cur = conn.execute(
            """
            SELECT slot_id, name, contact, contact_type, motif, booking_origin, google_event_id
            FROM appointments
            WHERE tenant_id = ? AND id = ?
            """,
            (tenant_id, appt_id),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return False

        old_slot_id = row["slot_id"]
        if int(old_slot_id) == int(new_slot_id):
            conn.rollback()
            return False

        conn.execute(
            "UPDATE slots SET is_booked=1 WHERE id=? AND tenant_id=? AND is_booked=0",
            (new_slot_id, tenant_id),
        )
        if conn.total_changes == 0:
            conn.rollback()
            return False

        from backend.booking_code import create_unique_booking_code_sqlite

        new_code = create_unique_booking_code_sqlite(conn, tenant_id)
        conn.execute(
            """
            INSERT INTO appointments (
                tenant_id, slot_id, name, contact, contact_type, motif, created_at,
                booking_origin, google_event_id, booking_code
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                new_slot_id,
                row["name"],
                row["contact"],
                row["contact_type"],
                row["motif"],
                datetime.utcnow().isoformat(),
                row["booking_origin"],
                row["google_event_id"],
                new_code,
            ),
        )
        conn.execute("DELETE FROM appointments WHERE tenant_id = ? AND id = ?", (tenant_id, appt_id))
        conn.execute("UPDATE slots SET is_booked = 0 WHERE id = ? AND tenant_id = ?", (old_slot_id, tenant_id))

        slot_cur = conn.execute("SELECT date, time FROM slots WHERE id = ? AND tenant_id = ?", (new_slot_id, tenant_id))
        slot_row = slot_cur.fetchone()
        if slot_row:
            new_dt = f"{slot_row['date']}T{slot_row['time']}:00"
            contact = row["contact"]
            if contact:
                conn.execute(
                    "UPDATE cabinet_clients SET last_booking_start = ?, updated_at = ? WHERE tenant_id = ? AND phone = ?",
                    (new_dt, datetime.utcnow().isoformat(), tenant_id, contact),
                )

        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_daily_report_data(client_id: int, date_str: str) -> Dict:
    """
    Métriques IVR pour le rapport quotidien (email).
    Source: ivr_events uniquement (table calls dépréciée: calls_total = COUNT DISTINCT call_id).
    Booked = event 'booking_confirmed' dans ivr_events.

    date_str: "YYYY-MM-DD"
    Fenêtre: [day 00:00:00, day+1 00:00:00) pour éviter les soucis de format ISO.

    Events attendus (à persister depuis l'engine): booking_confirmed, recovery_step,
    intent_router_trigger, anti_loop_trigger, empty_message, transferred_human,
    user_abandon, repeat_used, yes_ambiguous_router.
    """
    conn = get_conn()
    try:
        _ensure_ivr_tables(conn)
        day = date_str[:10]
        start_ts = day + " 00:00:00"

        # 1) Calls total = COUNT(DISTINCT call_id) dans ivr_events (dépréciation table calls)
        cur = conn.execute(
            """SELECT COUNT(DISTINCT COALESCE(NULLIF(TRIM(call_id), ''), 'UNKNOWN')) AS calls_total
               FROM ivr_events
               WHERE client_id = ?
                 AND created_at >= ?
                 AND created_at < datetime(? || ' 00:00:00', '+1 day')""",
            (client_id, start_ts, day),
        )
        row = cur.fetchone()
        calls_total = row["calls_total"] or 0

        # 2) Booked / Transfers / Abandons (ivr_events)
        cur = conn.execute(
            """SELECT COUNT(*) AS booked
               FROM ivr_events
               WHERE client_id = ? AND event = 'booking_confirmed'
                 AND created_at >= ? AND created_at < datetime(? || ' 00:00:00', '+1 day')""",
            (client_id, start_ts, day),
        )
        booked = cur.fetchone()["booked"] or 0

        cur = conn.execute(
            """SELECT COUNT(*) AS transfers
               FROM ivr_events
               WHERE client_id = ? AND event IN ('transfer', 'transferred', 'transfer_human', 'transferred_human')
                 AND created_at >= ? AND created_at < datetime(? || ' 00:00:00', '+1 day')""",
            (client_id, start_ts, day),
        )
        transfers = cur.fetchone()["transfers"] or 0

        cur = conn.execute(
            """SELECT COUNT(*) AS abandons
               FROM ivr_events
               WHERE client_id = ? AND event IN ('abandon', 'hangup', 'user_hangup', 'user_abandon')
                 AND created_at >= ? AND created_at < datetime(? || ' 00:00:00', '+1 day')""",
            (client_id, start_ts, day),
        )
        abandons = cur.fetchone()["abandons"] or 0

        # 3) Santé agent: intent_router / recovery / anti_loop (une requête)
        cur = conn.execute(
            """SELECT
                 SUM(CASE WHEN event = 'intent_router_trigger' THEN 1 ELSE 0 END) AS intent_router_count,
                 SUM(CASE WHEN event = 'recovery_step'         THEN 1 ELSE 0 END) AS recovery_count,
                 SUM(CASE WHEN event = 'anti_loop_trigger'   THEN 1 ELSE 0 END) AS anti_loop_count
               FROM ivr_events
               WHERE client_id = ?
                 AND created_at >= ? AND created_at < datetime(? || ' 00:00:00', '+1 day')""",
            (client_id, start_ts, day),
        )
        r = cur.fetchone()
        intent_router_count = r["intent_router_count"] or 0
        recovery_count = r["recovery_count"] or 0
        anti_loop_count = r["anti_loop_count"] or 0

        # 4) Silences répétés (empty_message >= 2 dans un call)
        cur = conn.execute(
            """SELECT COUNT(*) AS silent_calls
               FROM (
                 SELECT call_id
                 FROM ivr_events
                 WHERE client_id = ? AND event = 'empty_message'
                   AND created_at >= ? AND created_at < datetime(? || ' 00:00:00', '+1 day')
                   AND call_id IS NOT NULL AND call_id != ''
                 GROUP BY call_id
                 HAVING COUNT(*) >= 2
               ) t""",
            (client_id, start_ts, day),
        )
        empty_silence_calls = cur.fetchone()["silent_calls"] or 0

        # 5) Top 3 contexts (recovery_step)
        cur = conn.execute(
            """SELECT COALESCE(context, 'unknown') AS context, COUNT(*) AS cnt
               FROM ivr_events
               WHERE client_id = ? AND event = 'recovery_step'
                 AND created_at >= ? AND created_at < datetime(? || ' 00:00:00', '+1 day')
               GROUP BY COALESCE(context, 'unknown')
               ORDER BY cnt DESC
               LIMIT 3""",
            (client_id, start_ts, day),
        )
        top_contexts = [{"context": row["context"], "count": row["cnt"]} for row in cur.fetchall()]

        # 6) Qualité booking: direct / after recovery / after intent_router
        cur = conn.execute(
            """SELECT COUNT(*) AS direct_booking
               FROM (
                 SELECT DISTINCT e.call_id
                 FROM ivr_events e
                 WHERE e.client_id = ? AND e.event = 'booking_confirmed'
                   AND e.created_at >= ? AND e.created_at < datetime(? || ' 00:00:00', '+1 day')
                   AND e.call_id IS NOT NULL AND e.call_id != ''
                   AND NOT EXISTS (
                     SELECT 1 FROM ivr_events r
                     WHERE r.client_id = e.client_id AND r.call_id = e.call_id AND r.event = 'recovery_step'
                   )
                   AND NOT EXISTS (
                     SELECT 1 FROM ivr_events ir
                     WHERE ir.client_id = e.client_id AND ir.call_id = e.call_id AND ir.event = 'intent_router_trigger'
                   )
               ) t""",
            (client_id, start_ts, day),
        )
        direct_booking = cur.fetchone()["direct_booking"] or 0

        cur = conn.execute(
            """SELECT COUNT(*) AS booking_after_recovery
               FROM (
                 SELECT DISTINCT e.call_id
                 FROM ivr_events e
                 WHERE e.client_id = ? AND e.event = 'booking_confirmed'
                   AND e.created_at >= ? AND e.created_at < datetime(? || ' 00:00:00', '+1 day')
                   AND e.call_id IS NOT NULL AND e.call_id != ''
                   AND EXISTS (
                     SELECT 1 FROM ivr_events r
                     WHERE r.client_id = e.client_id AND r.call_id = e.call_id AND r.event = 'recovery_step'
                   )
               ) t""",
            (client_id, start_ts, day),
        )
        booking_after_recovery = cur.fetchone()["booking_after_recovery"] or 0

        cur = conn.execute(
            """SELECT COUNT(*) AS booking_after_intent_router
               FROM (
                 SELECT DISTINCT e.call_id
                 FROM ivr_events e
                 WHERE e.client_id = ? AND e.event = 'booking_confirmed'
                   AND e.created_at >= ? AND e.created_at < datetime(? || ' 00:00:00', '+1 day')
                   AND e.call_id IS NOT NULL AND e.call_id != ''
                   AND EXISTS (
                     SELECT 1 FROM ivr_events ir
                     WHERE ir.client_id = e.client_id AND ir.call_id = e.call_id AND ir.event = 'intent_router_trigger'
                   )
               ) t""",
            (client_id, start_ts, day),
        )
        booking_after_intent_router = cur.fetchone()["booking_after_intent_router"] or 0

        # Total events (pour footer debug admin)
        cur = conn.execute(
            """SELECT COUNT(*) AS events_count
               FROM ivr_events
               WHERE client_id = ?
                 AND created_at >= ? AND created_at < datetime(? || ' 00:00:00', '+1 day')""",
            (client_id, start_ts, day),
        )
        events_count = cur.fetchone()["events_count"] or 0

        return {
            "calls_total": calls_total,
            "booked": booked,
            "transfers": transfers,
            "abandons": abandons,
            "intent_router_count": intent_router_count,
            "recovery_count": recovery_count,
            "anti_loop_count": anti_loop_count,
            "empty_silence_calls": empty_silence_calls,
            "top_contexts": top_contexts,
            "direct_booking": direct_booking,
            "booking_after_recovery": booking_after_recovery,
            "booking_after_intent_router": booking_after_intent_router,
            "events_count": events_count,
        }
    finally:
        conn.close()
