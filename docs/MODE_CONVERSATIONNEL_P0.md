# Mode conversationnel P0 (START)

Réponses naturelles en état **START** via LLM, tout en restant production-safe : le LLM n’écrit jamais de faits en clair (horaires, adresse, tarifs, etc.) et utilise des **placeholders** remplacés par les réponses officielles (FAQ / prompts). En cas de rejet (chiffres, placeholder inconnu, confiance faible) → fallback FSM inchangée.

## Activation

- **Variable d’environnement** : `CONVERSATIONAL_MODE_ENABLED=true`
- **Canary** : `CANARY_PERCENT=0` → 100 % des conversations si activé ; `1` à `99` → pourcentage des `conv_id` (hash stable).

Exemple `.env` :

```bash
CONVERSATIONAL_MODE_ENABLED=true
CANARY_PERCENT=0
```

Par défaut le mode est **désactivé** (`false`).

## Comportement

- **Uniquement en état START** (et éventuellement POST_FAQ plus tard). Le booking (QUALIF_NAME, slots, etc.) reste 100 % FSM.
- **Strong intents** (annuler, modifier, transfert, abandon) → FSM direct, LLM non appelé.
- **Réponse LLM** : JSON avec `response_text` (sans chiffres, €, horaires/prix/adresse en clair), `next_mode` (FSM_BOOKING | FSM_FAQ | FSM_TRANSFER | FSM_FALLBACK), `extracted`, `confidence`.
- **Placeholders autorisés** : `{FAQ_HORAIRES}`, `{FAQ_ADRESSE}`, `{FAQ_TARIFS}`, `{FAQ_ACCES}`, `{FAQ_CONTACT}`. Remplacement après validation, avant envoi à l’utilisateur.
- **Seuil de confiance** : 0,75 ; en dessous → fallback FSM.

## Exemples de conversations (P0)

### 1) Demande hors sujet (ex. pizza)

- **User** : « Vous faites des pizzas ? »
- **LLM** (si activé) peut proposer une réponse polie sans fait (redirection cabinet / RDV). Si la réponse est rejetée (placeholder inconnu, etc.) → **fallback FSM** (clarification ou transfert selon le flow existant).

### 2) Horaires

- **User** : « Vous êtes ouverts quand ? »
- **LLM** peut renvoyer un texte du type : « Voici les infos : {FAQ_HORAIRES}. Souhaitez-vous prendre rendez-vous ? » avec `next_mode=FSM_FAQ`.
- L’app remplace `{FAQ_HORAIRES}` par la réponse officielle (ex. « Nous sommes ouverts du lundi au vendredi, de 9h à 18h. ») → **réponse naturelle + fait contrôlé**.

### 3) Prise de RDV

- **User** : « Bonjour, je voudrais un rendez-vous. »
- **LLM** peut renvoyer une phrase d’accueil + « Souhaitez-vous prendre rendez-vous ? Donnez-moi votre nom. » avec `next_mode=FSM_BOOKING`, `extracted` optionnel (ex. nom si compris).
- L’app envoie ce texte puis passe en **QUALIF_NAME** (FSM booking) pour la suite.

## Fichiers principaux

| Fichier | Rôle |
|--------|------|
| `backend/cabinet_data.py` | Données cabinet, mapping placeholder → faq_id |
| `backend/placeholders.py` | Liste des placeholders autorisés, `replace_placeholders()` |
| `backend/response_validator.py` | Validation JSON + contenu (pas de chiffres/€/mots interdits) |
| `backend/llm_conversation.py` | `ConvResult`, client LLM, `complete_conversation()` |
| `backend/conversational_engine.py` | Orchestration START : strong intent → FSM ; sinon LLM → validation → placeholders → FSM selon `next_mode` |
| `backend/config.py` | `CONVERSATIONAL_MODE_ENABLED`, `CANARY_PERCENT` |
| `backend/routes/voice.py` | Choix engine via `_get_engine(call_id)` (canary + flag) |
| `tests/test_conversational_p0_start.py` | Tests P0 (natural+booking, FAQ placeholder, rejets, strong intent, low confidence) |

## Tests

```bash
pytest tests/test_conversational_p0_start.py -v
```

Pour vérifier la non-régression FSM :

```bash
pytest tests/test_engine.py tests/test_prd_scenarios.py -v
```
