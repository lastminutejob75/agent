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

# Créer credentials depuis build arg
RUN mkdir -p credentials && \
    if [ -n "$GOOGLE_SERVICE_ACCOUNT_BASE64" ]; then \
        echo "$GOOGLE_SERVICE_ACCOUNT_BASE64" | base64 -d > credentials/service-account.json && \
        echo "✅ Google credentials créés au build"; \
    else \
        echo "⚠️ Pas de credentials Google - mode fallback SQLite"; \
    fi

RUN python -c "from backend.db import init_db; init_db()" || true

EXPOSE 8000

# Railway gère son propre health check, pas besoin de HEALTHCHECK Docker
# HEALTHCHECK désactivé pour éviter conflit avec Railway

CMD sh -c "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"
