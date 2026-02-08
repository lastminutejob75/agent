# Métriques P0 canary (mode conversationnel START)

Définition des métriques minimales pour mesurer l’impact du mode conversationnel en prod, et comment les calculer à partir des logs.

## Log structuré émis

À chaque passage dans le chemin canary en **START** (décision LLM ou non), le backend émet un log :

- **Message** : `conv_p0_start`
- **Champs** (dans `extra` ou équivalent selon ton stack) :
  - `conv_id`
  - **`reason`** (enum, clé pour le diagnostic) :
    - `LLM_OK` : LLM a produit un JSON valide + validateur OK → décision prise
    - `LOW_CONF` : LLM a répondu mais confidence < seuil
    - `INVALID_JSON` : réponse LLM invalide (parse JSON)
    - `VALIDATION_REJECTED` : validateur a refusé (chiffres, placeholders interdits, etc.)
    - `LLM_ERROR` : exception lors de l’appel LLM
    - `STRONG_INTENT` : routage FSM direct (CANCEL/MODIFY/TRANSFER/etc.), pas d’appel LLM
  - `next_mode` : présent seulement si `reason=LLM_OK` → `FSM_BOOKING` | `FSM_FAQ` | `FSM_FALLBACK` | `FSM_TRANSFER`
  - `llm_used` : `true` seulement si `reason=LLM_OK`
  - `confidence` : score (arrondi), présent si LLM a répondu (LLM_OK ou LOW_CONF)
  - `start_turn` : numéro du tour (1 = premier message)

### Exemples de lignes (sans texte user)

**Décision OK → booking :**
```
conv_p0_start conv_id=abc123 reason=LLM_OK next_mode=FSM_BOOKING llm_used=True confidence=0.86 start_turn=1
```

**Seuil trop strict :**
```
conv_p0_start conv_id=xyz789 reason=LOW_CONF confidence=0.72 start_turn=1
```

**Validateur a refusé la sortie LLM :**
```
conv_p0_start conv_id=def456 reason=VALIDATION_REJECTED start_turn=2
```

**Intent forte → FSM direct :**
```
conv_p0_start conv_id=ghi012 reason=STRONG_INTENT start_turn=1
```

Avec un agrégateur (Datadog, Grafana, etc.), filtrer sur le message `conv_p0_start` et grouper par `reason` et/ou `next_mode`.

---

## Métriques minimales (P0 START)

### 1. Taux FSM_FALLBACK en START

- **Définition** : parmi les décisions où le LLM a répondu correctement (`reason=LLM_OK`), part où `next_mode == "FSM_FALLBACK"`.
- **Objectif** : **↓** net vs avant (ou vs baseline sans canary).
- **Signal** : LLM inutile ou trop frileux si le taux reste élevé.

**Calcul** (sur une fenêtre 24–48 h) :

```
taux_fallback = count(next_mode = "FSM_FALLBACK") / count(reason = "LLM_OK")
```

---

### 2. Taux FSM_BOOKING après passage en START

- **Définition** : part des décisions START où `next_mode == "FSM_BOOKING"` (dont phrases mixtes type « pizza + rdv »).
- **Objectif** : **↑** (c’est le gain principal du routage RDV prioritaire).
- **Signal** : le LLM envoie bien vers la prise de RDV au lieu de fallback.

**Calcul** :

```
taux_booking = count(next_mode = "FSM_BOOKING") / count(reason = "LLM_OK")
```

---

### 3. Taux TRANSFERRED depuis START

- **Définition** : part des décisions START où `next_mode == "FSM_TRANSFER"`.
- **Objectif** : **↓** ou stable.
- **Signal** : si ça monte fort → prompt trop flou ou trop verbeux, ou cas limites mal gérés.

**Calcul** :

```
taux_transferred = count(next_mode = "FSM_TRANSFER") / count(reason = "LLM_OK")
```

---

### 4. Nombre moyen de tours avant QUALIF_NAME

- **Définition** : pour les conv qui passent en booking, nombre moyen de messages utilisateur avant d’atteindre `QUALIF_NAME`.
- **Objectif** : **↓** (fluidité : moins de tours = meilleure UX).
- **Signal** : phrases mixtes ou réponses claires en 1 tour = `start_turn` 1.

**Calcul** : parmi les logs `conv_p0_start` avec `next_mode == "FSM_BOOKING"` :

```
moyenne_tours_avant_qualif = mean(start_turn) where next_mode = "FSM_BOOKING"
```

---

### 5. (Optionnel) LLM utilisé et répartition par next_mode

- **Définition** : pour chaque décision en START, `llm_used = true` et répartition des `next_mode`.
- **Objectif** : vérifier que le LLM sert bien (BOOKING / FAQ) et pas seulement à du FSM_FALLBACK.
- **Calcul** : tableau ou graphique `next_mode` vs volume sur la fenêtre.

---

## Synthèse

| Métrique                         | Calcul (depuis conv_p0_start)              | Objectif  |
|----------------------------------|--------------------------------------------|-----------|
| Taux FSM_FALLBACK en START       | count(FSM_FALLBACK) / count(LLM_OK)        | ↓         |
| Taux FSM_BOOKING                 | count(FSM_BOOKING) / count(LLM_OK)         | ↑         |
| Taux TRANSFERRED depuis START    | count(FSM_TRANSFER) / count(LLM_OK)         | ↓ ou stable |
| Tours moyens avant QUALIF_NAME   | mean(start_turn) where FSM_BOOKING          | ↓         |
| Répartition next_mode            | count par next_mode                        | LLM utile → BOOKING/FAQ |

Avec ces métriques, en **24–48 h** tu peux juger si le mode conv vaut le coup et orienter l’audit du prompt (pourquoi tel fallback, tel transfert, tel booking raté).

---

## Canary propre : 5% → 20% → 100%

L’infra le permet déjà. Exemple de réglage :

- `CONVERSATIONAL_MODE_ENABLED=true`
- `CONVERSATIONAL_CANARY_PERCENT=5` (puis 20, puis 100)
- `CONVERSATIONAL_MIN_CONFIDENCE=0.75`

**Après 24–48 h à 5 % :**

- Si **FSM_FALLBACK baisse** et **FSM_BOOKING monte** → passer à **20 %**.
- Sinon → audit prompt ciblé avec les logs (surtout `reason`), pas au feeling.

---

## Lecture rapide des métriques (quoi conclure)

| Observation | Interprétation | Action |
|-------------|----------------|--------|
| FSM_FALLBACK ↑ + **LOW_CONF** ↑ | Seuil trop haut ou prompt trop “timide” | Baisser un peu le seuil ou renforcer le prompt (routing RDV) |
| FSM_FALLBACK ↑ + **VALIDATION_REJECTED** ↑ | Prompt pousse à écrire mots interdits / placeholders multiples / trop long | Audit prompt + validateur (règles trop strictes ?) |
| **FSM_BOOKING** ↓ alors que les intents RDV existent | Règle “RDV first” pas assez appliquée ou validateur trop strict sur phrases RDV | Renforcer ROUTING PRIORITY dans le prompt |
| **INVALID_JSON** ↑ | Sortie LLM mal formée (format, markdown, etc.) | Prompt “JSON only, single line” + éventuellement température |

---

## Alertes simples (décider “go 20 %” vs “audit prompt”)

À mettre en place (même à la main sur les logs) :

1. **Go 20 %** :  
   Sur la fenêtre (ex. 24 h), parmi les logs `reason=LLM_OK` :  
   - `count(next_mode=FSM_FALLBACK) / count(reason=LLM_OK)` **en baisse** vs baseline, **et**  
   - `count(next_mode=FSM_BOOKING) / count(reason=LLM_OK)` **en hausse**.

2. **Audit prompt** :  
   - Taux `reason=LOW_CONF` > X % (ex. 15–20 %) → regarder les `confidence` et le seuil.  
   - Taux `reason=VALIDATION_REJECTED` > Y % (ex. 10 %) → regarder quelles sorties sont refusées.  
   - Taux `reason=LLM_OK` et `next_mode=FSM_FALLBACK` élevé alors que beaucoup de messages sont “rdv” → renforcer la règle RDV dans le prompt.
