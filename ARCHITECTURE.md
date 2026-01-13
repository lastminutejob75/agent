# Architecture Technique V1 — Agent IA Accueil & RDV

## 1) Vue d'ensemble (composants)

### Frontend (vanilla)
- Widget chat (HTML/CSS/JS)
- Envoi messages (POST)
- Réception streaming (SSE)

### Backend (FastAPI)
- API Chat + SSE
- Moteur conversation (FSM / "engine")
- Guardrails (longueur, langue, spam, 2 tours max, formats)
- Gestion session (TTL 15 min, 10 messages)
- Outils : FAQ matcher (rapidfuzz), slots (SQLite), booking

### DB (SQLite)
- FAQ (id, question, answer)
- Slots (date, time, booked)
- Appointments (slot_id, name, contact, motif)

### Human transfer (V1)
- "transfert" = état final + message standard OU silencieux (spam/insultes)

---

## 2) Diagramme de flux (data flow)
```
User → Widget → POST /chat
Backend crée conversation_id + initialise session state
Widget ouvre GET /stream/{conversation_id} (SSE)
Backend pousse chunk partial immédiat (UX)

Backend exécute pipeline déterministe :
1. Edge-case gate (vide / trop long / langue / spam)
2. Session gate (timeout 15 min → reset message exact)
3. FAQ match (rapidfuzz score)
   - score ≥ 80 → réponse FAQ (copie exacte + Source: FAQ_ID)
   - score < 80 → intent booking ? sinon "pas de silence" → question qualif / transfert selon compteur
4. Booking flow (si "rdv/rendez/dispo" détecté +/ou après qualification complète)
   - propose 3 slots → attend "oui 1/2/3" ou "1/2/3"
   - si non conforme → redemande 1 fois, puis transfert
   - si conforme → book SQLite → confirmation

Backend envoie chunk final
Backend cleanup (streams + pending_slots + conv_state)
```

---

## 3) Modules backend (responsabilités claires)

### backend/main.py
- FastAPI app
- StaticFiles mount /frontend
- Endpoints : POST /chat, GET /stream/{id}, GET /health
- Push SSE (push_json)
- Cleanup (STREAMS, PENDING_SLOTS, CONV_STATE)

### backend/engine.py
- Cœur déterministe : applique le prompt/PRD, sans "intelligence libre"
- handle_message(conv_id, text) -> list[events]
- applique l'ordre : edge-cases → session → faq → booking/qualif → transfer
- gère qualif_count, pending_slots, pending_step

### backend/guards.py
- detect_language_fr(text)
- is_spam_or_abuse(text)
- validate_length(text, max=500)
- validate_reply_format_yesN(text)
- validate_qualif_format(step, answer)
- Règle : si doute → transfer

### backend/tools_faq.py
- search_faq(text) -> {match: bool, score: float, faq_id: str, answer: str}
- rapidfuzz + seuil 80
- renvoie l'ID FAQ pour traçabilité
- IMPORTANT : réponse = copie exacte du champ answer

### backend/tools_booking.py
- get_slots(limit=3) -> slots[]
- book_slot(slot_id, name, contact, motif) -> bool
- stocke pending_slots en mémoire par conv_id
- transaction safe + anti double booking

### backend/session.py
- SessionStore (in-memory dict V1)
- champs : last_seen_at, messages (max 10), qualif_count, qualif_data, pending_slots, pending_stage
- méthodes : touch(conv_id), is_expired(conv_id, ttl=15min), append_message(role,text)

### backend/db.py
- init_db()
- CRUD slots/appointments
- FAQ load/seed

---

## 4) États de conversation (FSM minimale, conforme PRD)

### States
- START
- FAQ_ANSWERED
- QUALIF_NAME
- QUALIF_MOTIF
- QUALIF_PREF
- QUALIF_CONTACT
- BOOKING_PROPOSED (pending slots)
- WAIT_CONFIRM (attend "oui 1/2/3")
- CONFIRMED
- TRANSFERRED
- ENDED

### Transitions clés
- Si message vide / >500 / langue / spam → TRANSFERRED (ou message exact puis end)
- Si FAQ match ≥80 → FAQ_ANSWERED → end
- Si booking intent + qualif incomplète → commence QUALIF
- Si booking intent + qualif complète → propose slots → WAIT_CONFIRM
- Si confirm invalide 1 fois → redemande → sinon transfer

---

## 5) API Contract (events SSE)

### SSE payload JSON
```json
{"type":"partial","text":"..."}  // optionnel
{"type":"final","text":"..."}    // toujours
{"type":"transfer","reason":"low_confidence"}  // optionnel
```

### Règles
- Ne jamais envoyer deux final
- Toujours terminer par final sauf "spam silent transfer"

---

## 6) Contraintes UX (implémentées côté front)
- placeholder input : "Posez votre question ou demandez un RDV…"
- compteur caractères (max 500)
- "Agent IA d'accueil" visible
- bouton "Parler à un humain"

---

## 7) Déploiement (Docker single container)

### Objectif V1
- un seul container
- pas de services externes

### Dockerfile
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY frontend/ ./frontend/
RUN python -c "from backend.db import init_db; init_db()"
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 8) File tree final (Cursor-ready)
```
agent-accueil-pme/
  PRD.md
  SYSTEM_PROMPT.md
  ARCHITECTURE.md
  backend/
    main.py
    engine.py
    session.py
    guards.py
    tools_faq.py
    tools_booking.py
    db.py
    config.py
    prompts.py
  frontend/
    index.html
    widget.js
    widget.css
  tests/
    test_prompt_compliance.py
    test_engine.py
    test_api_sse.py
  requirements.txt
  Dockerfile
  docker-compose.yml
  README.md
```
