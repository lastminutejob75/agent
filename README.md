# Agent IA d'Accueil & Prise de RDV (V1)

Agent d'accueil 24/7 pour PME : FAQ strict + qualification + prise de RDV (slots DB), avec transferts humains fail-safe.

## Documents de vérité
- `PRD.md` : scope + règles produit (contractuel)
- `SYSTEM_PROMPT.md` : loi comportementale (formulations exactes)
- `ARCHITECTURE.md` : architecture technique V1 (validée)
- `INSTRUCTIONS_CURSOR.md` : instructions d'implémentation
- `backend/prompts.py` : single source of truth des messages
- `tests/test_prompt_compliance.py` : non-régression strict wording

## Stack (V1)
- Backend : FastAPI
- DB : SQLite
- Front : HTML/CSS/JS vanilla + SSE
- Déploiement : Docker single container

Interdit (V1) : React/Vue, Postgres, Supabase/Firebase, LangChain/LlamaIndex, OAuth agenda réel, multi-tenant.

## Démarrage (local)

### 1) Installer
```bash
python -m venv .venv
source .venv/bin/activate  # mac/linux
# .venv\Scripts\activate   # windows
pip install -r requirements.txt
```

### 2) Initialiser la DB
```bash
python -c "from backend.db import init_db; init_db()"
```

### 3) Lancer
```bash
uvicorn backend.main:app --reload
```

### 4) Ouvrir
- UI : http://localhost:8000/frontend/
- Health : http://localhost:8000/health
- Debug slots : http://localhost:8000/debug/slots

## Tests
```bash
pytest tests/test_prompt_compliance.py -v
pytest tests/ -v
```

## Critères de validation V1 (obligatoires)

Le V1 est validé si :

1. FAQ "horaires" → réponse exacte + Source : FAQ_HORAIRES
2. Message vide → message exact
3. Message > 500 chars → message exact
4. Anglais → "Je ne parle actuellement que français."
5. Booking → propose 3 slots → "oui 2" → confirmation + DB booked
6. Booking non conforme ("je prends mercredi") → redemande 1 fois → transfert
7. Hors FAQ x2 → transfert
8. Session TTL 15 min → message exact
9. Insulte/spam → transfert silencieux
10. Temps réponse < 3s

## Docker
```bash
docker build -t agent-accueil:v1 .
docker run -p 8000:8000 agent-accueil:v1
```

## Règle d'or

Aucune string user-facing ne doit apparaître hors de `backend/prompts.py`.  
Toute modification wording => MAJ tests + validation PRD.
# uwiagent
