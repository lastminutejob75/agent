# backend/config.py
from __future__ import annotations
import os
import base64

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
    GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
    
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
