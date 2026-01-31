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

# Calendar ID
GOOGLE_CALENDAR_ID = os.getenv(
    "GOOGLE_CALENDAR_ID",
    "6fd8676f333bda53ea04d852eb72680d33dd567c7f286be401ed46d16b9f8659@group.calendar.google.com"
)

def get_service_account_file():
    """
    Retourne le chemin du fichier credentials.
    Le fichier est créé au build Docker depuis la variable Railway.
    """
    # Le Dockerfile crée credentials/service-account.json au build
    build_path = "credentials/service-account.json"
    if os.path.exists(build_path):
        return build_path
    
    # Fallback : mode local
    local_path = "credentials/service-account.json"
    if os.path.exists(local_path):
        return local_path
    
    return None

# Initialiser au démarrage pour les logs
_init_path = get_service_account_file()
if _init_path and "/tmp/" in _init_path:
    print(f"✅✅✅ GOOGLE CALENDAR CONNECTED FROM BASE64 ✅✅✅")
    print(f"✅ Service Account file: {_init_path}")
elif _init_path:
    print(f"📁 Using local credentials: {_init_path}")
else:
    print(f"⚠️ No Google credentials - using SQLite fallback")
