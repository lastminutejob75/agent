# CLAUDE.md — Guide pour Assistants IA

Ce document explique la structure, les conventions et les workflows du projet **UWi Agent** - un agent IA d'accueil et prise de rendez-vous pour PME.

---

## Apercu du Projet

**UWi Agent** est un agent conversationnel multicanal (web, vocal, WhatsApp) qui:
- Repond aux questions frequentes (FAQ)
- Qualifie les demandes clients
- Prend des rendez-vous (Google Calendar ou SQLite)
- Transfere a un humain quand le cadre est depasse

### Principe Fondamental

> **La fiabilite prime sur l'intelligence.**

L'agent est **contraint, pas creatif**:
- N'invente jamais de reponses
- Suit un processus deterministe (FSM)
- Transfere au moindre doute
- Utilise uniquement les messages definis dans `prompts.py`

---

## Architecture Technique

### Stack

| Composant | Technologie |
|-----------|-------------|
| Backend | FastAPI (Python 3.11) |
| Base de donnees | SQLite |
| RAG/FAQ | rapidfuzz (lexical, seuil 80%) |
| Frontend Widget | HTML/CSS/JS vanilla + SSE |
| Landing Page | React 18 + Vite + Tailwind |
| Calendar | Google Calendar API (fallback SQLite) |
| Voice | Vapi webhook |
| SMS/WhatsApp | Twilio |

### Canaux Supportes

1. **Web Widget** - Chat avec streaming SSE
2. **Vocal (Vapi)** - IVR telephonique
3. **WhatsApp** - Via Twilio
4. **Bland** - Plateforme IA vocale

---

## Structure du Projet

```
agent/
├── backend/                 # Code serveur Python
│   ├── main.py             # FastAPI app, startup, routes
│   ├── engine.py           # Coeur conversationnel (pipeline deterministe)
│   ├── prompts.py          # TOUS les messages utilisateur (source unique)
│   ├── guards.py           # Validation inputs (langue, spam, longueur)
│   ├── fsm.py              # Machine a etats finie (transitions)
│   ├── session.py          # Dataclasses session
│   ├── session_store_sqlite.py  # Persistence sessions
│   ├── tools_faq.py        # Matching FAQ avec rapidfuzz
│   ├── tools_booking.py    # Gestion slots et reservations
│   ├── google_calendar.py  # API Google Calendar
│   ├── entity_extraction.py # Extraction entites (nom, motif, etc.)
│   ├── client_memory.py    # Memoire client en session
│   ├── reports.py          # Rapports quotidiens automatiques
│   ├── config.py           # Configuration et constantes
│   ├── db.py               # Init SQLite, CRUD
│   ├── routes/             # Handlers par canal
│   │   ├── voice.py        # Webhook Vapi
│   │   ├── whatsapp.py     # Webhook WhatsApp
│   │   └── bland.py        # Webhook Bland
│   └── models/             # Dataclasses partages
│       └── message.py      # ChannelMessage, AgentResponse
├── frontend/               # Widget chat web
│   ├── index.html
│   ├── widget.js           # Logique SSE, messages
│   └── widget.css
├── landing/                # Landing page React
│   ├── src/                # Composants React
│   └── app/                # Routes Next.js (webhooks)
├── tests/                  # Tests pytest
│   ├── test_engine.py      # Logique engine
│   ├── test_prompt_compliance.py  # Conformite messages/PRD
│   ├── test_prd_scenarios.py      # 10 scenarios validation
│   ├── test_api_sse.py     # API et streaming
│   └── ...
├── PRD.md                  # Specification produit (contractuel)
├── SYSTEM_PROMPT.md        # Regles comportementales agent
├── ARCHITECTURE.md         # Architecture technique
├── PRODUCTION_GRADE_SPEC_V3.md  # Spec deploiement prod
└── requirements.txt        # Dependances Python
```

---

## Modules Cles et Responsabilites

### `backend/engine.py` (Coeur)

Pipeline deterministe de traitement:
1. Edge-case gate (vide, trop long, langue, spam)
2. Session gate (timeout 15 min)
3. FAQ match (rapidfuzz >= 80%)
4. Intent detection (booking, annulation, etc.)
5. Qualification flow (nom → motif → preference → contact)
6. Slot proposal (3 creneaux)
7. Confirmation
8. Transfert humain si necessaire

**Fonction principale:** `Engine.handle_message(conv_id, text) -> list[Event]`

### `backend/prompts.py` (Messages)

**Source unique de verite** pour tous les messages utilisateur.

```python
# Exemple de constantes
MSG_EMPTY_MESSAGE = "Je n'ai pas recu votre message. Pouvez-vous reessayer ?"
MSG_TOO_LONG = "Votre message est trop long. Pouvez-vous resumer ?"
MSG_FRENCH_ONLY = "Je ne parle actuellement que francais."
MSG_TRANSFER = "Je vous mets en relation avec un humain pour vous aider."
```

**Regle:** Ne JAMAIS hardcoder de messages dans `engine.py` - toujours importer de `prompts.py`.

### `backend/fsm.py` (Etats)

Machine a etats finie avec transitions whitelist:

```
START → QUALIF_NAME → QUALIF_MOTIF → QUALIF_PREF → QUALIF_CONTACT → WAIT_CONFIRM → CONFIRMED
                ↓           ↓            ↓             ↓              ↓
            TRANSFERRED  AIDE_MOTIF  TRANSFERRED   TRANSFERRED    TRANSFERRED
```

**Etats terminaux:** `CONFIRMED`, `TRANSFERRED`

### `backend/guards.py` (Validation)

Fonctions de validation des inputs:
- `detect_language_fr(text)` - Detecte si francais
- `is_spam_or_abuse(text)` - Detecte spam/insultes
- `validate_length(text, max=500)` - Verifie longueur
- `validate_reply_format_yesN(text)` - Valide "oui 1/2/3"
- `clean_vocal_name(text)` - Nettoie transcription vocale

**Regle:** Si doute → transfert humain.

### `backend/config.py` (Configuration)

```python
BUSINESS_NAME = "Cabinet Dupont"
FAQ_THRESHOLD = 0.80      # Match FAQ >= 80%
SESSION_TTL_MINUTES = 15  # Timeout session
MAX_MESSAGE_LENGTH = 500  # Max caracteres
MAX_SLOTS_PROPOSED = 3    # Creneaux proposes
CONFIRM_RETRY_MAX = 1     # Redemande avant transfert
```

---

## Commandes de Developpement

### Installation

```bash
make install              # Cree venv, installe deps, init DB
# ou manuellement:
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Lancer le serveur

```bash
make run                  # uvicorn avec reload
# ou:
uvicorn backend.main:app --reload
```

### Tests

```bash
make test                 # Tous les tests
make test-compliance      # Tests conformite PRD
make test-engine          # Tests engine uniquement
make test-api             # Tests API SSE

# Pytest direct:
pytest tests/ -v
pytest tests/test_engine.py -v
pytest tests/test_prd_scenarios.py -v
```

### Docker

```bash
make docker               # docker compose up --build
```

### Nettoyage

```bash
make clean                # Supprime caches et DB
```

---

## Variables d'Environnement

### Production (Railway)

| Variable | Description |
|----------|-------------|
| `GOOGLE_SERVICE_ACCOUNT_BASE64` | Service Account JSON encode base64 |
| `GOOGLE_CALENDAR_ID` | ID du calendrier cible |
| `PORT` | Port d'ecoute (defaut: 8000) |
| `TWILIO_ACCOUNT_SID` | Credentials Twilio |
| `TWILIO_AUTH_TOKEN` | Token Twilio |
| `TWILIO_PHONE_NUMBER` | Numero expediteur |
| `TELEGRAM_BOT_TOKEN` | Bot Telegram (rapports) |
| `TELEGRAM_CHAT_ID` | Chat destination rapports |

### Developpement Local

Placer le fichier `credentials/service-account.json` pour Google Calendar.

---

## Conventions et Regles Critiques

### 1. Messages Utilisateur

**TOUJOURS** utiliser `prompts.py`:
```python
# BON
from backend.prompts import MSG_TRANSFER
return Event(text=MSG_TRANSFER)

# MAUVAIS - Ne jamais faire
return Event(text="Je vous transfere a un humain")
```

### 2. Transitions FSM

Toujours valider les transitions:
```python
from backend.fsm import validate_transition

if not validate_transition(current_state, new_state):
    raise InvalidTransitionError(...)
```

### 3. Pas de Creativite

L'agent ne doit JAMAIS:
- Inventer des reponses
- Reformuler les messages standard
- Interpreter au-dela du scope FAQ
- Prendre des decisions sans confirmation

### 4. Transfert au Moindre Doute

```python
# Si score FAQ < 80% apres 2 tours → transfert
# Si format invalide apres 1 redemande → transfert
# Si langue non francaise → transfert
# Si spam/insultes → transfert silencieux
```

### 5. Format Reponse FAQ

```
[Reponse factuelle]

Source : FAQ_ID
```

### 6. Confirmation Obligatoire

Aucune action (RDV, annulation) sans confirmation explicite:
```
Creneaux disponibles :
1. Mardi 15/01 - 10:00
2. Mardi 15/01 - 14:00
3. Jeudi 16/01 - 16:00

Repondez par 'oui 1', 'oui 2' ou 'oui 3' pour confirmer.
```

---

## API Endpoints

### Web

| Endpoint | Methode | Description |
|----------|---------|-------------|
| `/chat` | POST | Envoie message chat |
| `/stream/{conv_id}` | GET | Stream SSE reponses |
| `/health` | GET | Health check |
| `/debug/slots` | GET | Debug slots disponibles |

### Webhooks

| Endpoint | Methode | Canal |
|----------|---------|-------|
| `/api/vapi/webhook` | POST | Vapi (vocal) |
| `/api/whatsapp/webhook` | POST | WhatsApp |
| `/api/bland/webhook` | POST | Bland |

### Format SSE

```json
{"type": "partial", "text": "..."}
{"type": "final", "text": "..."}
{"type": "transfer", "reason": "low_confidence"}
```

---

## Tests - Scenarios PRD Obligatoires

Les 10 scenarios de validation (`test_prd_scenarios.py`):

1. FAQ "horaires" → reponse exacte + Source
2. Message vide → MSG_EMPTY_MESSAGE
3. Message > 500 chars → MSG_TOO_LONG
4. "Hello" (anglais) → MSG_FRENCH_ONLY
5. Booking complet → 3 slots → confirmation
6. Booking format invalide → redemande → transfert
7. Hors FAQ x2 → transfert
8. Session 15 min → MSG_SESSION_EXPIRED
9. Insulte → transfert silencieux
10. Temps reponse < 3s

---

## Deploiement

### Railway (Production)

1. Variables env configurees (voir section ci-dessus)
2. Calendrier Google partage avec Service Account
3. Health check sur `/health`
4. Keep-alive loop (30s) pour eviter cold start

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY frontend/ ./frontend/
EXPOSE 8000
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

---

## Fichiers de Reference

| Document | Contenu |
|----------|---------|
| `PRD.md` | Specification produit, regles absolues |
| `SYSTEM_PROMPT.md` | Comportement agent, triggers transfert |
| `ARCHITECTURE.md` | Architecture technique, FSM, API |
| `PRODUCTION_GRADE_SPEC_V3.md` | Spec deploiement, NFRs |
| `VAPI_CONFIG.md` | Configuration Vapi vocal |
| `GOOGLE_CALENDAR_SETUP.md` | Setup Google Calendar |

---

## Erreurs Courantes a Eviter

### Ne PAS faire

1. **Hardcoder des messages** - Utiliser `prompts.py`
2. **LLM pour routage** - Utiliser FSM deterministe
3. **Reponse creative** - Copie exacte des FAQ
4. **Ignorer les guards** - Toujours valider inputs
5. **Action sans confirmation** - Toujours demander "oui X"
6. **Transition invalide FSM** - Verifier whitelist
7. **Credentials en dur** - Utiliser variables env
8. **Session infinie** - Respecter TTL 15 min
9. **Historique illimite** - Max 10 messages

### A TOUJOURS faire

1. **Transfert si doute** - Mieux vaut transferer que se tromper
2. **Logs structures** - conv_id, state, intent
3. **Tests apres modif** - `make test`
4. **Fallback SQLite** - Si Google Calendar indisponible
5. **Validation formats** - Email, telephone, "oui 1/2/3"

---

## Recovery et Compteurs

Le systeme utilise des compteurs de recovery progressifs:

- `off_topic_count` - Hors sujet consecutifs
- `invalid_format_count` - Formats invalides
- `clarification_count` - Demandes de clarification

Apres N echecs → transfert automatique.

Voir `AJOUT_COMPTEURS_RECOVERY.md` pour details.

---

## Workflow Git

```bash
# Branche de travail
git checkout -b feature/nom-feature

# Commits atomiques
git commit -m "fix(engine): correction detection intent booking"

# Tests avant push
make test

# Push
git push -u origin feature/nom-feature
```

### Prefixes commits

- `feat:` - Nouvelle fonctionnalite
- `fix:` - Correction bug
- `docs:` - Documentation
- `test:` - Ajout/modification tests
- `refactor:` - Refactoring sans changement fonctionnel

---

## Support et Debug

### Logs utiles

```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"[{conv_id}] state={state} intent={intent}")
logger.error(f"[{conv_id}] Exception: {e}", exc_info=True)
```

### Endpoints debug

- `GET /health` - Sante service
- `GET /debug/slots` - Slots disponibles (dev only)
- `GET /api/vapi/health` - Sante webhook Vapi

---

*Ce document est la reference pour tout assistant IA travaillant sur ce projet.*
