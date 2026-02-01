# Spécification Production-Grade V3 — Agent IA d'accueil & prise de RDV

**Version :** V3  
**Statut :** Spécification technique pour déploiement production  
**Références :** PRD.md, SYSTEM_PROMPT.md, SCRIPT_CONVERSATION_AGENT.md, ARCHITECTURE.md

---

## 1. Périmètre V3

### 1.1 Fonctionnel

- **Canal vocal (Vapi)** : First Message → webhook → engine → réponse TTS.
- **Canal web (widget)** : Chat + SSE (legacy).
- **Prise de RDV** : Qualification (nom, motif, préférence, contact) → proposition 3 créneaux → confirmation → **création dans Google Calendar** (ou fallback SQLite).
- **FAQ** : RAG lexical (rapidfuzz, seuil 80 %) ; réponse factuelle + source.
- **Annulation / modification** : Recherche RDV par nom → confirmation → annulation ou reroute vers nouveau créneau.
- **Transfert humain** : Dès que le cadre est dépassé (no-match FAQ x2, spam, format invalide, etc.).

### 1.2 Hors périmètre V3

- Multi-tenant, CRM, OAuth générique.
- LLM pour routage ou génération libre.
- Canaux autres que vocal (Vapi) et web (widget) — WhatsApp/Bland présents mais non couverts par cette spec.

---

## 2. Exigences non fonctionnelles

### 2.1 Performance

| Métrique | Cible | Mesure |
|----------|--------|--------|
| Première réponse (webhook → premier chunk) | ≤ 3 s | Log / APM |
| Réponse complète (engine) | ≤ 5 s | Log / APM |
| Health check | ≤ 500 ms | GET /health |

### 2.2 Disponibilité

- Service exposé 24/7 (Railway ou équivalent).
- En cas d’indisponibilité Google Calendar : fallback SQLite pour slots/booking sans coupure fonctionnelle.
- Session : persistance SQLite (sessions) pour survivre aux redémarrages.

### 2.3 Sécurité

- Aucun secret en clair dans le code (credentials Google en env : `GOOGLE_SERVICE_ACCOUNT_BASE64`, `GOOGLE_CALENDAR_ID`).
- Validation stricte des entrées : longueur, langue, spam/abus (cf. guards).
- Pas d’exposition de données personnelles dans les logs (masquage calendar_id, pas de téléphone/email en log).

### 2.4 Observabilité

- Logs structurés (au minimum) : `conv_id`, `state`, `intent`, erreurs avec stack.
- Endpoints de diagnostic (optionnels, protégés en prod) : `/health`, `/api/vapi/health` ; pas de dump de secrets.
- Traçabilité : chaque réponse FAQ inclut `Source : FAQ_ID` ; booking log `event_id` et `calendar_id` (tronqué).

---

## 3. Intégrations

### 3.1 Vapi

- **First Message** : défini dans VAPI_CONFIG.md (ex. « Bonjour [Entreprise], vous appelez pour un rendez-vous ? »).
- **Webhook** : POST vers `/api/vapi/webhook` (ou route équivalente selon déploiement).
- **Payload** : extraction `call_id`, `transcript` (user message) ; réponse texte renvoyée pour TTS.
- **Health** : GET `/api/vapi/health` pour vérifier que le service répond.

### 3.2 Google Calendar

- **Credentials** : Service Account JSON encodé en base64 (`GOOGLE_SERVICE_ACCOUNT_BASE64`), décodé au startup et écrit dans `/tmp/service-account.json` (ou chemin configurable).
- **Calendar ID** : `GOOGLE_CALENDAR_ID` (env). Le calendrier cible doit être partagé avec le `client_email` du Service Account avec droit « Modifier les événements ».
- **Opérations** : list events (créneaux libres), insert (création RDV), delete (annulation).
- **Fallback** : si credentials ou calendar ID absents → slots et booking via SQLite (comportement dégradé mais opérationnel).

Référence dépannage : PROBLEME_RAILWAY_GOOGLE_CALENDAR.md.

### 3.3 Persistance

- **Sessions** : SQLite (`session_store_sqlite`) ; TTL 15 min, max 10 messages par conversation.
- **Slots/booking** : Google Calendar prioritaire ; SQLite en fallback.
- **FAQ** : chargées depuis la base (RAG) ; pas de cache obligatoire en V3.

---

## 4. Comportement conversationnel (référence)

Le dialogue strict (états, messages, flows) est décrit dans **SCRIPT_CONVERSATION_AGENT.md**.

Règles critiques :

- Une seule question à la fois.
- Messages issus uniquement de `backend/prompts.py` (aucune chaîne en dur côté engine pour les réponses utilisateur).
- Confirmation explicite avant toute action (RDV, annulation, modification).
- Après 2 tours sans match FAQ → transfert humain.
- Cas limites (vide, trop long, langue, spam) → messages ou transfert définis dans le script.

---

## 5. Gestion des erreurs et fallbacks

| Situation | Comportement |
|-----------|--------------|
| Google Calendar indisponible / 403 | Fallback SQLite si déjà configuré ; sinon transfert + log erreur. |
| Créneau déjà pris (double book) | Message `MSG_SLOT_ALREADY_BOOKED` + transfert. |
| Session expirée | Message `MSG_SESSION_EXPIRED` + reset session. |
| Webhook timeout (Vapi) | Retry côté Vapi ; backend doit répondre dans la cible < 5 s. |
| Exception non gérée dans engine | Log + réponse générique type transfert (éviter 500 nu). |
| Message vide / trop long / langue | Réponses fixes (MSG_EMPTY_MESSAGE, MSG_TOO_LONG, MSG_FRENCH_ONLY). |

---

## 6. Déploiement

### 6.1 Environnement cible

- **Plateforme** : Railway (ou équivalent PaaS).
- **Runtime** : Python 3.11, FastAPI, uvicorn.
- **Build** : Dockerfile (COPY backend, requirements, pas de credentials dans l’image).
- **Variables d’environnement** (runtime) : `GOOGLE_SERVICE_ACCOUNT_BASE64`, `GOOGLE_CALENDAR_ID`, `PORT`, et toute variable métier (ex. `BUSINESS_NAME` si surcharge).

### 6.2 Démarrage

- Chargement des credentials Google **au startup** (`load_google_credentials()` dans `main.py`), pas à l’import.
- Init DB (SQLite) au démarrage ; échec non bloquant pour l’API si mode dégradé accepté.
- Health check disponible dès que l’app écoute.

### 6.3 Santé du service

- `GET /health` (ou `/api/health`) : retourne 200 si l’application répond.
- `GET /api/vapi/health` : 200 si le webhook Vapi est prêt.
- Pas d’exposition de secrets dans les réponses.

---

## 7. Tests et validation

### 7.1 Tests automatisés

- Conformité des messages : `tests/test_prompt_compliance.py` (aligné PRD + SYSTEM_PROMPT).
- Scénarios métier : `tests/test_prd_scenarios.py`, `test_conversations.py` (flows booking, FAQ, transfert).
- Engine : `tests/test_engine.py` (états, intents).
- Guards : validation longueur, langue, contact, slot choice.
- API : health, webhook (payload minimal).

### 7.2 Critères de mise en production

- Tous les tests ci-dessus passent.
- Variables d’environnement production configurées (credentials Google, calendar ID).
- Calendrier partagé avec le Service Account (droit « Modifier les événements »).
- First Message Vapi configuré et URL webhook pointant vers l’environnement déployé.

---

## 8. Documents de référence

| Document | Usage |
|---------|--------|
| PRD.md | Scope produit, règles absolues, KPIs. |
| SYSTEM_PROMPT.md | Règles comportementales de l’agent. |
| SCRIPT_CONVERSATION_AGENT.md | Script de conversation (états, messages, flows). |
| ARCHITECTURE.md | Modules, flux données, FSM. |
| VAPI_CONFIG.md | First Message, flows résumés, config Vapi. |
| PROBLEME_RAILWAY_GOOGLE_CALENDAR.md | Dépannage Google Calendar et Railway. |
| GOOGLE_CALENDAR_SETUP.md | Setup local et credentials. |

---

## 9. Historique

| Version | Date | Modifications |
|---------|------|---------------|
| V3 | — | Spec production-grade : Vapi, Google Calendar, NFRs, déploiement, erreurs, tests. |

---

*Ce document est la spécification de référence pour un déploiement production de l’agent d’accueil & prise de RDV (V3).*
