# Mode Conversationnel P0 — Guide d'activation

Ce document explique comment activer et configurer le mode conversationnel LLM "naturel" pour l'agent UWi.

## Principe

Le mode conversationnel permet des réponses plus naturelles via LLM, tout en garantissant la sécurité:
- **Placeholders** : Le LLM n'écrit jamais de faits en clair (horaires, prix, adresse)
- **Validation stricte** : Rejet si chiffres, symboles monétaires, mots interdits
- **Fallback FSM** : En cas d'échec, retour au comportement déterministe

## Activation

### Via variables d'environnement

```bash
# Activer le mode conversationnel
export CONVERSATIONAL_MODE_ENABLED=true

# Rollout canary : 0 = disabled (0%), 1-99 = % du trafic, 100 = full (convention explicite, évite piège prod)
export CONVERSATIONAL_CANARY_PERCENT=100

# Optionnel: seuil de confiance (défaut: 0.75)
export CONVERSATIONAL_MIN_CONFIDENCE=0.80
```

### Dans .env

```env
CONVERSATIONAL_MODE_ENABLED=true
CONVERSATIONAL_CANARY_PERCENT=100
CONVERSATIONAL_MIN_CONFIDENCE=0.75
```

**Convention canary (noir sur blanc)** :
- `CONVERSATIONAL_CANARY_PERCENT=0` => **désactivé** (0 % du trafic, personne n'est éligible au mode conversationnel).
- `CONVERSATIONAL_CANARY_PERCENT=100` => **100 %** (rollout complet).
- `1` à `99` => pourcentage du trafic (bucket stable par `conv_id` via SHA256).

### Railway / Production

Dans les variables d'environnement Railway:
1. `CONVERSATIONAL_MODE_ENABLED` = `true`
2. `CONVERSATIONAL_CANARY_PERCENT` = `100` (full) ou `10` (10% du trafic pour test)

## Scope P0

Le mode conversationnel P0 est actif **uniquement dans l'état START**.

| État | Comportement |
|------|--------------|
| START | LLM conversationnel (si activé) |
| QUALIF_NAME, QUALIF_MOTIF, etc. | FSM déterministe |
| WAIT_CONFIRM | FSM déterministe |
| Tous les autres | FSM déterministe |

## Sécurité

### Ce que le LLM peut faire
- Générer des salutations naturelles
- Utiliser des placeholders: `{FAQ_HORAIRES}`, `{FAQ_ADRESSE}`, `{FAQ_TARIFS}`
- Extraire des entités (nom, motif)
- Router vers booking, FAQ, ou transfert

### Ce que le LLM NE PEUT PAS faire
- Écrire des chiffres (heures, prix, numéros)
- Mentionner des mots factuels (ouvert, fermé, prix, tarif, rue, etc.)
- Donner des conseils médicaux
- Promettre des disponibilités

### Validation automatique

Chaque réponse LLM est validée avant envoi:

```
[Réponse LLM] → Validation JSON → Validation contenu → Remplacement placeholders → [Réponse finale]
                     ↓                    ↓
                  Échec?               Échec?
                     ↓                    ↓
              Fallback FSM         Fallback FSM
```

## Exemples de conversations

### Exemple 1: Question horaires (FAQ via placeholder)

```
User: Bonjour, vous êtes ouverts quand ?

LLM génère:
{
  "response_text": "Bonjour ! {FAQ_HORAIRES} Puis-je vous aider pour autre chose ?",
  "next_mode": "FSM_FAQ",
  "confidence": 0.92
}

Réponse finale (après remplacement):
"Bonjour ! Le cabinet est ouvert du lundi au vendredi de 9h à 18h. Puis-je vous aider pour autre chose ?"
```

### Exemple 2: Demande de rendez-vous (routing vers booking)

```
User: Je voudrais prendre rendez-vous

LLM génère:
{
  "response_text": "Bien sûr, je serais ravi de vous aider ! C'est à quel nom ?",
  "next_mode": "FSM_BOOKING",
  "confidence": 0.95
}

→ State passe à QUALIF_NAME
→ Suite gérée par FSM booking
```

### Exemple 3: Question hors scope (fallback)

```
User: Vous servez de la pizza ?

LLM génère:
{
  "response_text": "Je suis désolé, nous sommes un cabinet médical et non un restaurant.",
  "next_mode": "FSM_FALLBACK",
  "confidence": 0.88
}

→ Réponse envoyée, state reste START
```

### Exemple 4: Réponse rejetée (contient chiffre)

```
User: C'est combien la consultation ?

LLM génère (INVALIDE):
{
  "response_text": "La consultation coûte 25 euros",
  "next_mode": "FSM_FAQ",
  "confidence": 0.9
}

→ REJETÉ (contient "25")
→ Fallback vers FSM
→ FSM retourne: clarification ou FAQ standard
```

## Tests

```bash
# Exécuter les tests P0
pytest tests/test_conversational_p0_start.py -v

# Tests spécifiques
pytest tests/test_conversational_p0_start.py::TestValidationRejection -v
pytest tests/test_conversational_p0_start.py::TestPlaceholders -v
```

## Monitoring

### Logs à surveiller

```python
# Réponse LLM acceptée
INFO [conv_id] Routing to FSM_BOOKING

# Réponse LLM rejetée
WARNING [conv_id] LLM response rejected: contains_digits
WARNING [conv_id] LLM response rejected: forbidden_word:ouvert
WARNING [conv_id] LLM response rejected: low_confidence:0.4

# Fallback déclenché
INFO [conv_id] LLM response rejected, falling back to FSM
```

### Métriques recommandées

- Taux d'acceptation LLM vs fallback
- Distribution des raisons de rejet
- Temps de réponse LLM vs FSM
- Satisfaction utilisateur (si mesurable)

## Rollback

Pour désactiver immédiatement:

```bash
export CONVERSATIONAL_MODE_ENABLED=false
# ou supprimer la variable
```

Le système retourne automatiquement au comportement FSM déterministe.

## Architecture des fichiers

```
backend/
├── conversational_engine.py  # Wrapper engine
├── llm_conversation.py       # Interface LLM
├── response_validator.py     # Validation stricte
├── placeholders.py           # Système placeholders
├── cabinet_data.py           # Données cabinet
└── config.py                 # Feature flags
```

## Évolutions P1+

- Extension à POST_FAQ
- Mode conversationnel dans qualification (avec contraintes)
- A/B testing intégré
- Métriques de conversion
