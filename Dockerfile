FROM python:3.11-slim

WORKDIR /app

# Argument de build pour les credentials (fourni par Railway)
ARG GOOGLE_SERVICE_ACCOUNT_BASE64

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY PRD.md SYSTEM_PROMPT.md ARCHITECTURE.md INSTRUCTIONS_CURSOR.md README.md ./

# Créer dossier credentials (vide pour l'instant)
RUN mkdir -p credentials && echo "Credentials seront chargés au runtime"

RUN python -c "from backend.db import init_db; init_db()" || true

EXPOSE 8000

# Railway gère son propre health check, pas besoin de HEALTHCHECK Docker
# HEALTHCHECK désactivé pour éviter conflit avec Railway

# Script de démarrage qui crée les credentials puis lance uvicorn
CMD sh -c '\
    if [ -n "$GOOGLE_SERVICE_ACCOUNT_BASE64" ]; then \
        echo "$GOOGLE_SERVICE_ACCOUNT_BASE64" | base64 -d > credentials/service-account.json && \
        echo "✅ Google credentials créés au runtime"; \
    fi && \
    uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}'
