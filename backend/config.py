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

# Google Calendar Service Account
if os.getenv("GOOGLE_SERVICE_ACCOUNT_BASE64"):
    # Production (Railway) : décoder depuis base64
    try:
        decoded = base64.b64decode(os.getenv("GOOGLE_SERVICE_ACCOUNT_BASE64"))
        service_account_path = "/tmp/service-account.json"
        
        with open(service_account_path, "wb") as f:
            f.write(decoded)
        
        GOOGLE_SERVICE_ACCOUNT_FILE = service_account_path
        print(f"✅ Google Service Account loaded from base64 → {service_account_path}")
    except Exception as e:
        print(f"⚠️ Warning: Could not decode GOOGLE_SERVICE_ACCOUNT_BASE64: {e}")
        GOOGLE_SERVICE_ACCOUNT_FILE = None
else:
    # Local : fichier dans credentials/
    GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE",
        "credentials/service-account.json"
    )

# Calendar ID
GOOGLE_CALENDAR_ID = os.getenv(
    "GOOGLE_CALENDAR_ID",
    "6fd8676f333bda53ea04d852eb72680d33dd567c7f286be401ed46d16b9f8659@group.calendar.google.com"
)
