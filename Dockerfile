FROM python:3.11-slim

WORKDIR /app

# Pas de apt-get : évite broken pipe Railway. Python slim suffit.
# run_migration.py dans backend/ (pas besoin de scripts/)

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY migrations/ ./migrations/
COPY PRD.md SYSTEM_PROMPT.md ARCHITECTURE.md INSTRUCTIONS_CURSOR.md README.md ./

# Créer dossier credentials (vide pour l'instant)
RUN mkdir -p credentials && echo "Credentials seront chargés au runtime"

RUN python -c "from backend.db import init_db; init_db()" || true

EXPOSE 8000

# Railway gère son propre health check, pas besoin de HEALTHCHECK Docker
# HEALTHCHECK désactivé pour éviter conflit avec Railway

# Migrations en arrière-plan pour que /health réponde vite (healthcheck Railway)
# Uvicorn démarre immédiatement ; migrations s'exécutent en parallèle
CMD sh -c "echo 'Starting server (migrations in background)...'; (python -m backend.run_migration 005 || true; python -m backend.run_migration 003 || true; python -m backend.run_migration 004 || true; python -m backend.run_migration 006 || true; python -m backend.run_migration 007 || true; python -m backend.run_migration 008 || true; python -m backend.run_migration 008_call_sessions_messages_checkpoints.sql || true; echo 'Migrations done') & exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"
