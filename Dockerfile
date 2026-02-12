FROM python:3.11-slim

WORKDIR /app

# Pas de apt-get : évite broken pipe Railway. Python slim suffit.
# curl non nécessaire (healthcheck HTTP externe).
# scripts/ et migrations/ requis pour run_migration au démarrage.

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY migrations/ ./migrations/
COPY scripts/ ./scripts/
COPY PRD.md SYSTEM_PROMPT.md ARCHITECTURE.md INSTRUCTIONS_CURSOR.md README.md ./

# Créer dossier credentials (vide pour l'instant)
RUN mkdir -p credentials && echo "Credentials seront chargés au runtime"

RUN python -c "from backend.db import init_db; init_db()" || true

EXPOSE 8000

# Railway gère son propre health check, pas besoin de HEALTHCHECK Docker
# HEALTHCHECK désactivé pour éviter conflit avec Railway

# Migrations au démarrage (si DATABASE_URL présent)
# Puis démarrage du serveur
CMD sh -c "echo 'Running migrations...'; python scripts/run_migration.py 007 || true; python scripts/run_migration.py 008 || true; echo 'Starting server...'; exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"
