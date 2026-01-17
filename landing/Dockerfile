FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY PRD.md SYSTEM_PROMPT.md ARCHITECTURE.md INSTRUCTIONS_CURSOR.md README.md ./

RUN python -c "from backend.db import init_db; init_db()" || true

EXPOSE 8000

# Railway gère son propre health check, pas besoin de HEALTHCHECK Docker
# HEALTHCHECK désactivé pour éviter conflit avec Railway

CMD sh -c "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"
