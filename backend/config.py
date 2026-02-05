# backend/config.py
from __future__ import annotations
import os
import base64

# --- Cabinet / horaires (RÈGLE 7) ---
# (Pour multi-clients plus tard : passer en config par tenant)
CABINET_TIMEZONE = "Europe/Paris"
CABINET_CLOSING_HOUR = 19
CABINET_CLOSING_MINUTE = 0
TIME_CONSTRAINT_ENABLED = True

# Business
BUSINESS_NAME = "Cabinet Dupont"
TRANSFER_PHONE = "+33 6 00 00 00 00"  # V1 simple (affiché au besoin)

# FAQ / RAG
FAQ_THRESHOLD = 0.80  # score >= 0.80 => match

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

# P2.1 FSM explicite : migration progressive (QUALIF_NAME, WAIT_CONFIRM via fsm2)
USE_FSM2 = os.getenv("USE_FSM2", "false").lower() in ("true", "1", "yes")

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
    "phone": 2,
    "silence": 3,  # RÈGLE 3 : 2 messages distincts + 3e => INTENT_ROUTER
}


# ==============================
# GOOGLE CALENDAR CONFIGURATION
# ==============================

# Variables globales (remplies au startup RUNTIME uniquement)
SERVICE_ACCOUNT_FILE = None
GOOGLE_CALENDAR_ID = None

def load_google_credentials():
    """
    Charge les credentials Google au démarrage RUNTIME.
    À appeler UNIQUEMENT dans @app.on_event("startup").
    Ne JAMAIS appeler au module import.
    """
    global SERVICE_ACCOUNT_FILE, GOOGLE_CALENDAR_ID
    
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
            print(f"📁 Using local credentials: {local_path}")
            return
        raise RuntimeError("❌ GOOGLE_SERVICE_ACCOUNT_BASE64 missing at runtime")
    
    # 3. Décode et écrit le fichier
    try:
        decoded = base64.b64decode(b64)
        path = "/tmp/service-account.json"
        
        with open(path, "wb") as f:
            f.write(decoded)
        
        SERVICE_ACCOUNT_FILE = path
        
        # ✅ Logs sans données sensibles
        print(f"✅ Google credentials loaded at RUNTIME")
        print(f"   Service Account file: {path} ({len(decoded)} bytes)")
        print(f"   Calendar ID set: {bool(GOOGLE_CALENDAR_ID)}")
        
    except Exception as e:
        raise RuntimeError(f"❌ Failed to decode credentials: {e}")

# ⚠️ NE RIEN EXÉCUTER ICI (sera appelé au startup FastAPI)
