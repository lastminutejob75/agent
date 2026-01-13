# INSTRUCTIONS CURSOR — Agent IA Accueil & RDV (V1)

Tu dois implémenter ce projet en respectant STRICTEMENT :

1) PRD.md (scope + règles produit)
2) SYSTEM_PROMPT.md (comportement agent)
3) ARCHITECTURE.md (modules + file tree)

## CONTEXTE CRITIQUE
- Projet GREENFIELD autonome.
- Ne pas réutiliser de legacy.
- Ne pas généraliser.
- Fiabilité > intelligence.

## CONTRAINTES ABSOLUES
- Toutes les formulations user-facing dans `backend/prompts.py` (AUCUNE string hardcodée ailleurs).
- Pipeline déterministe dans `backend/engine.py` : edge-cases → session gate → FAQ match → booking/qualif → transfer.
- Aucune créativité dans les réponses.
- RAG lexical strict via rapidfuzz, seuil 80%.
- Réponses FAQ = COPIE EXACTE de la FAQ + "Source : FAQ_ID".
- Confirmation RDV acceptée uniquement :
  - "oui 1" / "oui 2" / "oui 3" (insensible à la casse)
  - ou "1"/"2"/"3"
  Toute autre forme → redemander UNE fois, puis transfer.
- Session :
  - TTL 15 min
  - conserver 10 derniers messages
- Message max 500 caractères.

## STACK IMPOSÉE (V1)
- Backend : FastAPI
- DB : SQLite
- Front : HTML/CSS/JS vanilla + SSE
- Déploiement : Docker single container

Interdit : React/Vue, Postgres, Supabase/Firebase, LangChain/LlamaIndex, orchestrateur complexe.

## ORDRE D'IMPLÉMENTATION

Phase 1 (core) :
1. backend/config.py
2. backend/prompts.py
3. backend/session.py
4. backend/guards.py
5. backend/tools_faq.py
6. backend/engine.py

Phase 2 :
7. backend/db.py
8. backend/tools_booking.py
9. backend/main.py (SSE + StaticFiles + cleanup)

Phase 3 (tests) :
10. tests/test_prompt_compliance.py (égalité stricte)
11. tests/test_engine.py
12. tests/test_api_sse.py

Phase 4 (frontend) :
13. frontend/widget.js (validation 500 chars + compteur)
14. frontend/index.html
15. frontend/widget.css

## RÈGLE DE REFUS
Si une demande sort du scope PRD (ex: OAuth agenda réel, multi-tenant, WhatsApp, CRM réel, etc.) :
- REFUSER
- indiquer "Out of scope V1" et proposer "V2".

## OBJECTIF LIVRABLE
Un V1 fonctionnel :
- FAQ répondue avec Source
- Booking : propose 3 slots → confirme strict → book SQLite
- Edge cases : vide/long/langue/spam → comportements exacts
- Streaming SSE stable (POST /chat + GET /stream/{id})

## CHECKLIST DE VALIDATION (AVANT COMMIT)

### Phase 1 - Core
- [ ] `backend/prompts.py` : tous messages centralisés
- [ ] `backend/engine.py` : pipeline déterministe
- [ ] `backend/guards.py` : validations strictes
- [ ] `backend/tools_faq.py` : copie exacte FAQ

### Phase 2 - API
- [ ] `backend/main.py` : SSE ferme proprement
- [ ] `backend/tools_booking.py` : parsing strict "oui N"
- [ ] `backend/db.py` : transactions atomiques

### Phase 3 - Tests
- [ ] `tests/test_prompt_compliance.py` : 100% OK
- [ ] `tests/test_engine.py` : cas limites OK
- [ ] `tests/test_api_sse.py` : happy paths OK

### Phase 4 - Frontend
- [ ] `frontend/widget.js` : validation + compteur 500 chars
- [ ] `frontend/widget.js` : reconnexion SSE gérée
- [ ] `frontend/index.html` : indicateur "Agent IA" visible
- [ ] `frontend/widget.css` : distinction claire

### Validation Finale
- [ ] `docker build` OK
- [ ] `docker run` OK
- [ ] Aucune string user-facing hors `prompts.py`
- [ ] Aucun TODO/FIXME/HACK
- [ ] README.md à jour

## COMMANDES DE TEST RAPIDE
```bash
pytest tests/test_prompt_compliance.py -v
pytest tests/ -v
docker build -t agent-accueil:v1 .
docker run -p 8000:8000 agent-accueil:v1
curl http://localhost:8000/health
```

## CRITÈRES DE SUCCÈS V1

**Le V1 est validé si :**

1. ✅ FAQ "Quels sont vos horaires ?" → réponse exacte + "Source : FAQ_HORAIRES"
2. ✅ Message vide → "Je n'ai pas reçu votre message..."
3. ✅ Message 600 chars → "Votre message est trop long..."
4. ✅ "Hello" → "Je ne parle actuellement que français."
5. ✅ Booking complet → 3 slots → "oui 2" → confirmation
6. ✅ Booking "je prends mercredi" → redemande → puis transfert
7. ✅ Question hors FAQ × 2 → transfert
8. ✅ Session 15 min → "Votre session a expiré..."
9. ✅ Insulte → transfert silencieux
10. ✅ Temps de réponse < 3 secondes

**Si l'un de ces 10 cas échoue, le V1 n'est PAS validé.**
