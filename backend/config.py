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

def get_google_service_account_file():
    """Retourne le chemin du fichier credentials (dynamique, pas caché)."""
    env_base64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_BASE64")
    
    if env_base64:
        # Production (Railway) : décoder depuis base64
        try:
            decoded = base64.b64decode(env_base64)
            service_account_path = "/tmp/service-account.json"
            
            # Écrire le fichier (idempotent)
            with open(service_account_path, "wb") as f:
                f.write(decoded)
            
            return service_account_path
        except Exception as e:
            print(f"❌ Error decoding GOOGLE_SERVICE_ACCOUNT_BASE64: {e}")
            return None
    else:
        # Local : fichier dans credentials/
        return "credentials/service-account.json"

# Initialiser au démarrage (pour les logs)
_init_path = get_google_service_account_file()
if _init_path and "/tmp/" in _init_path:
    print(f"✅✅✅ GOOGLE CALENDAR CONNECTED FROM BASE64 ✅✅✅")
    print(f"✅ Service Account file: {_init_path}")
elif _init_path:
    print(f"📁 Using local service account file: {_init_path}")
else:
    print(f"⚠️ No Google credentials configured")

# Pour compatibilité avec le code existant, créer une variable
GOOGLE_SERVICE_ACCOUNT_FILE = _init_path

# Calendar ID
GOOGLE_CALENDAR_ID = os.getenv(
    "GOOGLE_CALENDAR_ID",
    "6fd8676f333bda53ea04d852eb72680d33dd567c7f286be401ed46d16b9f8659@group.calendar.google.com"
)
