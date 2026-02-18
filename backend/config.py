# backend/config.py
from __future__ import annotations
import logging
import os
import base64

logger = logging.getLogger(__name__)

# --- Cabinet / horaires (RÈGLE 7) ---
# (Pour multi-clients plus tard : passer en config par tenant)
CABINET_TIMEZONE = "Europe/Paris"
CABINET_CLOSING_HOUR = 19
CABINET_CLOSING_MINUTE = 0
TIME_CONSTRAINT_ENABLED = True

# Business
BUSINESS_NAME = "Cabinet Dupont"
TRANSFER_PHONE = "+33 6 00 00 00 00"  # V1 simple (affiché au besoin)
OPENING_HOURS_DEFAULT = "Lundi au vendredi 9h-19h"  # Repli si non défini par tenant (params_json.horaires)

# FAQ / RAG
FAQ_THRESHOLD = 0.80  # score >= 0.80 => match
# Seuil strict pour afficher une réponse FAQ (évite faux positifs type "pizza" → paiement). Pas de liste en dur.
FAQ_STRONG_MATCH_THRESHOLD = 0.90  # n'afficher la FAQ que si score >= ce seuil

# Session
SESSION_TTL_MINUTES = 15
MAX_MESSAGES_HISTORY = 10

# UX / Inputs
MAX_MESSAGE_LENGTH = 500

# Booking
MAX_SLOTS_PROPOSED = 3
CONFIRM_RETRY_MAX = 1  # 1 redemande, puis transfer

# Performance
TARGET_FIRST_RESPONSE_MS = 3000  # contrainte PRD (sans imposer SSE)

# RGPD consent (version pour audit)
CONSENT_VERSION = "2026-02-12_v1"  # format: YYYY-MM-DD_vN

# P2.1 FSM explicite : migration progressive (QUALIF_NAME, WAIT_CONFIRM via fsm2)
USE_FSM2 = os.getenv("USE_FSM2", "false").lower() in ("true", "1", "yes")

# Dual-write ivr_events vers Postgres (DATABASE_URL ou PG_EVENTS_URL)
USE_PG_EVENTS = os.getenv("USE_PG_EVENTS", "false").lower() in ("true", "1", "yes")

# PG-first read pour tenants/config/routing (DATABASE_URL) ; fallback SQLite
USE_PG_TENANTS = os.getenv("USE_PG_TENANTS", "true").lower() in ("true", "1", "yes")

# PG-first pour slots/appointments (local fallback quand pas Google Calendar)
USE_PG_SLOTS = os.getenv("USE_PG_SLOTS", "true").lower() in ("true", "1", "yes")

# P0 Option B: Journal + checkpoints sessions vocales (dual-write Phase 1)
# Si PG down: log WARN, continue (pas de crash)
USE_PG_CALL_JOURNAL = os.getenv("USE_PG_CALL_JOURNAL", "true").lower() in ("true", "1", "yes")

# ==============================
# MULTI-TENANT MODE (fail-closed SQLite)
# ==============================
# Lecture runtime (pas import-time) pour permettre mock en tests.


def is_multi_tenant_mode() -> bool:
    """True si MULTI_TENANT_MODE=true. Utiliser une fonction pour mock facile en test."""
    return os.getenv("MULTI_TENANT_MODE", "false").lower() in ("true", "1", "yes")


def _sqlite_guard(func_name: str) -> None:
    """
    Bloque l'exécution du chemin SQLite en mode multi-tenant.
    À appeler au début de chaque branche SQLite (pas au top-level des fonctions qui routent PG/SQLite).
    """
    if is_multi_tenant_mode():
        logger.critical(
            "[MULTI_TENANT] %s called via SQLite path. Blocked.",
            func_name,
        )
        raise RuntimeError(
            f"[MULTI_TENANT] {func_name} called via SQLite path. "
            "SQLite is disabled in multi-tenant mode. Use PG."
        )


def validate_multi_tenant_config() -> None:
    """À appeler au démarrage de l'app. Lève si mode multi-tenant mais PG slots désactivé."""
    if is_multi_tenant_mode() and not USE_PG_SLOTS:
        raise RuntimeError(
            "[MULTI_TENANT] USE_PG_SLOTS must be True in multi-tenant mode. "
            "Set USE_PG_SLOTS=true (or MULTI_TENANT_MODE=false)."
        )


# ==============================
# TENANT FLAGS (P0)
# ==============================
DEFAULT_TENANT_ID = 1
# Tenant et numéro de démo (vitrine vocale). Règle : DID test → TEST_TENANT_ID uniquement (guard_demo_number_routing).
# TEST_TENANT_ID peut être vide en env (''), int() accepterait pas → fallback DEFAULT_TENANT_ID
TEST_TENANT_ID = int((os.getenv("TEST_TENANT_ID") or "").strip() or str(DEFAULT_TENANT_ID))
TEST_VOCAL_NUMBER = (os.getenv("TEST_VOCAL_NUMBER") or os.getenv("ONBOARDING_DEMO_VOCAL_NUMBER", "+33939240575") or "").strip() or None
DEFAULT_FLAGS = {
    "ENABLE_LLM_ASSIST_START": False,
    "ENABLE_BARGEIN_SLOT_CHOICE": True,
    "ENABLE_SEQUENTIAL_SLOTS": True,
    "ENABLE_NO_FAQ_GUARD": True,
    "ENABLE_YES_AMBIGUOUS_ROUTER": True,
}
# Garde-fou : si True, numéro vocal non routé → log tenant_route_miss + transfert
ENABLE_TENANT_ROUTE_MISS_GUARD = os.getenv("ENABLE_TENANT_ROUTE_MISS_GUARD", "false").lower() in ("true", "1", "yes")

# Numéro de démo vocal (public). Utilisé pour affichage landing ; guard utilise TEST_VOCAL_NUMBER (même valeur).
ONBOARDING_DEMO_VOCAL_NUMBER = (os.getenv("ONBOARDING_DEMO_VOCAL_NUMBER", "+33939240575") or "").strip() or None
if TEST_VOCAL_NUMBER is None:
    TEST_VOCAL_NUMBER = ONBOARDING_DEMO_VOCAL_NUMBER

# ==============================
# CONVERSATIONAL MODE (P0)
# ==============================

# Feature flag for conversational LLM mode
# When enabled, uses natural LLM responses in START state
# When disabled (default), uses deterministic FSM only
CONVERSATIONAL_MODE_ENABLED = os.getenv("CONVERSATIONAL_MODE_ENABLED", "false").lower() in ("true", "1", "yes")

# Canary percentage: 0 = disabled (0%), 1-99 = % of conv_id (hash), 100 = full rollout
# Convention explicite pour éviter en prod : 0 = désactivé (personne n'est éligible)
_raw_canary = int(os.getenv("CONVERSATIONAL_CANARY_PERCENT", "0"))
if _raw_canary < 0:
    _raw_canary = 0
if _raw_canary > 100:
    _raw_canary = 100
CONVERSATIONAL_CANARY_PERCENT = _raw_canary

# Alias pour compatibilité
CANARY_PERCENT = CONVERSATIONAL_CANARY_PERCENT

# Minimum confidence threshold for LLM responses
CONVERSATIONAL_MIN_CONFIDENCE = float(os.getenv("CONVERSATIONAL_MIN_CONFIDENCE", "0.75"))

# Debug Vapi TTS : si True, /chat/completions renvoie "TEST AUDIO 123" pour trancher (endpoint/format)
VAPI_DEBUG_TEST_AUDIO = os.getenv("VAPI_DEBUG_TEST_AUDIO", "false").lower() in ("true", "1", "yes")

# ==============================
# STT (nova-2-phonecall) — seuils et noise
# ==============================
# Surchargables via env (ex: NOISE_CONFIDENCE_THRESHOLD=0.35)
STT_MODEL = os.getenv("STT_MODEL", "nova-2-phonecall")
NOISE_CONFIDENCE_THRESHOLD = float(os.getenv("NOISE_CONFIDENCE_THRESHOLD", "0.35"))
SHORT_TEXT_MIN_CONFIDENCE = float(os.getenv("SHORT_TEXT_MIN_CONFIDENCE", "0.50"))
MIN_TEXT_LENGTH = int(os.getenv("MIN_TEXT_LENGTH", "5"))
NOISE_COOLDOWN_SEC = float(os.getenv("NOISE_COOLDOWN_SEC", "2.0"))
MAX_NOISE_BEFORE_ESCALATE = int(os.getenv("MAX_NOISE_BEFORE_ESCALATE", "3"))

# Crosstalk (barge-in) : fenêtre après envoi réponse assistant pendant laquelle UNCLEAR = ignoré (pas d'escalade)
# TTS peut durer 3–6 s ; si l'utilisateur parle pendant, on reste dans la fenêtre → pas transfert
CROSSTALK_WINDOW_SEC = float(os.getenv("CROSSTALK_WINDOW_SEC", "5.0"))
# Longueur max (car. bruts) pour considérer une entrée UNCLEAR comme crosstalk (ex. "euh", "attendez")
CROSSTALK_MAX_RAW_LEN = int(os.getenv("CROSSTALK_MAX_RAW_LEN", "40"))

# Overlap (user parle juste après envoi réponse agent) : UNCLEAR dans cette fenêtre = pas d'incrément unclear
OVERLAP_WINDOW_SEC = float(os.getenv("OVERLAP_WINDOW_SEC", "1.2"))

# === INTERRUPTION VOCALE (barge-in pendant énonciation des créneaux) ===
VAPI_INTERRUPTION_ENABLED = os.getenv("VAPI_INTERRUPTION_ENABLED", "true").lower() in ("true", "1", "yes")
VAPI_ENDPOINTING_MS = int(os.getenv("VAPI_ENDPOINTING_MS", "200"))  # Détection rapide fin de parole
VAPI_FILLER_INJECTION = os.getenv("VAPI_FILLER_INJECTION", "false").lower() in ("true", "1", "yes")
SLOT_ENUMERATION_TIMEOUT_SEC = int(os.getenv("SLOT_ENUMERATION_TIMEOUT_SEC", "15"))  # Max 15s pour énoncer 3 créneaux

# ==============================
# PHILOSOPHIE UWI : RETRY, PAS TRANSFERT SYSTÉMATIQUE
# ==============================
# Privilégier : reformulation, clarification, plusieurs tentatives par champ.
# Éviter : transfert humain ou raccrochage dès la 1ère incompréhension.
# Après N échecs sur un même champ → INTENT_ROUTER (menu 1/2/3/4), pas transfert direct.
# Transfert uniquement : demande explicite de l'utilisateur (humain, quelqu'un) ou après menu.

# Recovery IVR : limites par contexte (spec test-terrain)
# Après N échecs sur un même champ → escalade INTENT_ROUTER (menu), pas transfert
RECOVERY_LIMITS = {
    "name": 2,
    "slot_choice": 3,
    "phone": 3,  # 3 tentatives pour dicter le numéro (vocal)
    "silence": 3,  # RÈGLE 3 : 2 messages distincts + 3e => INTENT_ROUTER
}


# ==============================
# GOOGLE CALENDAR CONFIGURATION
# ==============================

# Variables globales (remplies au startup RUNTIME uniquement)
SERVICE_ACCOUNT_FILE = None
GOOGLE_CALENDAR_ID = None
# Diagnostic prod : True après load_google_credentials() réussi, sinon False + raison
GOOGLE_CALENDAR_ENABLED = False
GOOGLE_CALENDAR_DISABLE_REASON = "not_loaded"

def load_google_credentials():
    """
    Charge les credentials Google au démarrage RUNTIME.
    À appeler UNIQUEMENT dans @app.on_event("startup").
    Ne JAMAIS appeler au module import.
    """
    global SERVICE_ACCOUNT_FILE, GOOGLE_CALENDAR_ID, GOOGLE_CALENDAR_ENABLED, GOOGLE_CALENDAR_DISABLE_REASON

    # 1. Charge Calendar ID
    GOOGLE_CALENDAR_ID = os.getenv(
        "GOOGLE_CALENDAR_ID",
        "6fd8676f333bda53ea04d852eb72680d33dd567c7f286be401ed46d16b9f8659@group.calendar.google.com"  # Fallback hardcodé
    )

    # 2. Charge Service Account base64
    b64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_BASE64")
    if not b64:
        # Fallback local pour dev
        local_path = "credentials/service-account.json"
        if os.path.exists(local_path):
            SERVICE_ACCOUNT_FILE = local_path
            GOOGLE_CALENDAR_ENABLED = True
            GOOGLE_CALENDAR_DISABLE_REASON = None
            print(f"📁 Using local credentials: {local_path}")
            print(f"   Google Calendar enabled: true")
            return
        GOOGLE_CALENDAR_ENABLED = False
        GOOGLE_CALENDAR_DISABLE_REASON = "GOOGLE_SERVICE_ACCOUNT_BASE64 missing"
        raise RuntimeError("❌ GOOGLE_SERVICE_ACCOUNT_BASE64 missing at runtime")

    # 3. Décode et écrit le fichier
    try:
        decoded = base64.b64decode(b64)
        path = "/tmp/service-account.json"

        with open(path, "wb") as f:
            f.write(decoded)

        SERVICE_ACCOUNT_FILE = path

        # ✅ Logs sans données sensibles + flag pour /debug/config
        GOOGLE_CALENDAR_ENABLED = True
        GOOGLE_CALENDAR_DISABLE_REASON = None
        print(f"✅ Google credentials loaded at RUNTIME")
        print(f"   Service Account file: {path} ({len(decoded)} bytes)")
        print(f"   Calendar ID set: {bool(GOOGLE_CALENDAR_ID)}")
        print(f"   Google Calendar enabled: true")

    except Exception as e:
        GOOGLE_CALENDAR_ENABLED = False
        GOOGLE_CALENDAR_DISABLE_REASON = f"decode_error: {e}"
        raise RuntimeError(f"❌ Failed to decode credentials: {e}")

# ⚠️ NE RIEN EXÉCUTER ICI (sera appelé au startup FastAPI)
