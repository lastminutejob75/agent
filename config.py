# backend/config.py
from __future__ import annotations

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

# Google Calendar
GOOGLE_CALENDAR_ID = ""  # À configurer après création du calendar de test
GOOGLE_SERVICE_ACCOUNT_FILE = "credentials/uwi-agent-service-account.json"

# Performance
TARGET_FIRST_RESPONSE_MS = 3000  # contrainte PRD (sans imposer SSE)
