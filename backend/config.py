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

# Variables globales (initialisées au startup)
SERVICE_ACCOUNT_FILE = None
GOOGLE_CALENDAR_ID = os.getenv(
    "GOOGLE_CALENDAR_ID",
    "6fd8676f333bda53ea04d852eb72680d33dd567c7f286be401ed46d16b9f8659@group.calendar.google.com"
)

def load_google_credentials():
    """
    Charge les credentials Google au démarrage de l'app.
    À appeler UNIQUEMENT dans @app.on_event("startup").
    
    Multi-worker safe: chaque worker exécute son propre startup
    et écrit son propre /tmp/service-account.json
    """
    global SERVICE_ACCOUNT_FILE
    
    b64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_BASE64")
    if not b64:
        # Mode local - essayer fichier credentials/
        local_path = "credentials/service-account.json"
        if os.path.exists(local_path):
            SERVICE_ACCOUNT_FILE = local_path
            print(f"📁 Using local Google credentials: {local_path}")
            return
        
        print("⚠️ GOOGLE_SERVICE_ACCOUNT_BASE64 not set - Calendar disabled")
        SERVICE_ACCOUNT_FILE = None
        return
    
    # Décoder et créer le fichier
    try:
        decoded = base64.b64decode(b64)
        path = "/tmp/service-account.json"
        
        with open(path, "wb") as f:
            f.write(decoded)
        
        SERVICE_ACCOUNT_FILE = path
        print(f"✅✅✅ GOOGLE CALENDAR CONNECTED FROM BASE64 ✅✅✅")
        print(f"✅ Service Account file: {path} ({len(decoded)} bytes)")
        
    except Exception as e:
        print(f"❌❌❌ ERROR DECODING GOOGLE_SERVICE_ACCOUNT_BASE64 ❌❌❌")
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        SERVICE_ACCOUNT_FILE = None

# Pour compatibilité avec l'ancien code
GOOGLE_SERVICE_ACCOUNT_FILE = SERVICE_ACCOUNT_FILE  # Sera None jusqu'au startup
