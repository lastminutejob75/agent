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

# Railway : utiliser le script qui lit PORT depuis l'env (même port que le healthcheck)
CMD ["python", "-m", "backend.railway_run"]
