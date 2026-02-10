# Analyse du merge PR #5 (branche Claude → main)

**Merge** : commit `1cc960e` — *Merge pull request #5 from lastminutejob75/claude/claude-md-ml4wgcu42uqd9mpb-lHzo9*  
**Périmètre** : intégration du mode conversationnel P0 (déjà présent sur main) avec ajouts et ajustements de la branche Claude.

---

## 1. Fichiers impactés (diff 561e7c5 → origin/main)

| Fichier | Changements principaux |
|---------|------------------------|
| **backend/config.py** | Nouvelle section « CONVERSATIONAL MODE (P0) », `CONVERSATIONAL_CANARY_PERCENT`, `CONVERSATIONAL_MIN_CONFIDENCE`, alias `CANARY_PERCENT` |
| **backend/cabinet_data.py** | 4 placeholders ajoutés (PAIEMENT, ANNULATION, DUREE), `business_type` « cabinet médical » → « cabinet médical », helpers `get_allowed_placeholders()`, `get_faq_id_for_placeholder()`, `DEFAULT_CABINET_DATA` |
| **backend/placeholders.py** | `ALLOWED_PLACEHOLDERS` étendu (FAQ_PAIEMENT, FAQ_ANNULATION, FAQ_DUREE), `find_placeholders()`, pattern `{FAQ_[A-Z_]+}`, fallback `faq_store.search()` si pas `get_answer_by_faq_id`, `get_placeholder_system_instructions()` |
| **backend/response_validator.py** | Réécriture : `find_placeholders` au lieu de `contains_only_allowed_placeholders`, liste `FORBIDDEN_WORDS` / `MEDICAL_MARKERS` étendue, validation par étapes (placeholders puis texte sans placeholders), `validate_extracted_entities()` |
| **backend/conversational_engine.py** | Lecture de `CONVERSATIONAL_CANARY_PERCENT` au lieu de `CANARY_PERCENT` |
| **backend/llm_conversation.py** | Import du validateur (inchangé fonctionnellement) |
| **docs/CONVERSATIONAL_MODE_P0.md** | **Nouveau** : guide activation (env, canary, confiance), scope P0, sécurité, exemples, monitoring, rollback |

---

## 2. Config (backend/config.py)

- **CONVERSATIONAL_CANARY_PERCENT** : variable principale, env `CONVERSATIONAL_CANARY_PERCENT` (défaut `0`).
- **CANARY_PERCENT** : alias vers `CONVERSATIONAL_CANARY_PERCENT` pour compatibilité.
- **CONVERSATIONAL_MIN_CONFIDENCE** : nouveau, env `CONVERSATIONAL_MIN_CONFIDENCE` (défaut `0.75`).  
  Non utilisé dans `conversational_engine` ni `llm_conversation` (ils utilisent encore `CONV_CONFIDENCE_THRESHOLD = 0.75` en dur). À aligner si on veut un seuil piloté par la config.

**Impact** : nommage plus clair, possibilité future de seuil de confiance par env. Pas de régression si on garde l’alias.

---

## 3. Cabinet & placeholders

- **cabinet_data** : 4 nouveaux placeholders (PAIEMENT, ANNULATION, DUREE) + API (get_allowed_placeholders, get_faq_id_for_placeholder, DEFAULT_CABINET_DATA). Cohérent avec le FAQ store (tools_faq a ces faq_id).
- **placeholders** :  
  - Même liste étendue.  
  - `find_placeholders()` pour l’extraction.  
  - `replace_placeholders` : utilise `get_answer_by_faq_id` si présent, sinon `faq_store.search()` — plus robuste si le store n’a pas `get_answer_by_faq_id`.  
  - `get_placeholder_system_instructions()` pour le prompt système (pas utilisé dans `llm_conversation` actuellement ; utile pour centraliser les consignes).

**Impact** : plus de types de FAQ couverts, remplacement plus résilant. Aucune incohérence détectée avec le FAQ store.

---

## 4. Validator (response_validator.py)

- **Avant** : une seule fonction de validation, refus des mots interdits après retrait des placeholders (via `ALLOWED_PLACEHOLDERS`).
- **Après** :  
  - Utilisation de `find_placeholders()` puis vérification que chaque placeholder trouvé est dans `ALLOWED_PLACEHOLDERS`.  
  - Mots interdits et marqueurs médicaux appliqués sur le texte **sans** les placeholders (évite de refuser à cause du nom du placeholder, ex. FAQ_HORAIRES).  
  - Listes élargies : `FORBIDDEN_WORDS` (heures, coûte, métro, etc.), `MEDICAL_MARKERS` (traitement, médicament, ordonnance, prescription).  
  - `validate_extracted_entities()` pour le champ `extracted` (clés autorisées : name, pref, contact, motif).

**Impact** : validation plus stricte et plus lisible. Comportement sécurité conservé (chiffres, €, mots factuels, conseil médical). Les tests P0 restent valides (ex. rejet de `{FAQ_PIZZA}`).

---

## 5. Conversational engine & canary

- **Seul changement** : `_is_canary()` lit `CONVERSATIONAL_CANARY_PERCENT` au lieu de `CANARY_PERCENT`.
- **Convention canary (fix post-merge)** : `0` = disabled (0%, personne éligible), `1`-`99` = % du trafic, `100` = full rollout. Évite le piège prod où 0 était interprété comme 100%.

---

## 6. Documentation (CONVERSATIONAL_MODE_P0.md)

- **Contenu** : activation (env, .env, Railway), canary, seuil de confiance, scope P0 (START uniquement), sécurité (ce que le LLM peut / ne peut pas faire), schéma validation → fallback, exemples (horaires, RDV, hors scope), monitoring et rollback.
- **Différence avec MODE_CONVERSATIONNEL_P0.md** : CONVERSATIONAL_MODE_P0.md est plus détaillé (exemples JSON, variables CONVERSATIONAL_*), MODE_CONVERSATIONNEL_P0.md plus court. Les deux décrivent le même mode ; à terme on peut fusionner ou faire pointer l’un vers l’autre.

---

## 7. Cohérence globale & points d’attention

| Point | Statut |
|-------|--------|
| Placeholders cabinet_data ↔ placeholders ↔ validator | OK (même liste étendue, même logique) |
| Config canary (CONVERSATIONAL_CANARY_PERCENT / CANARY_PERCENT) | OK (alias + engine lit la nouvelle variable) |
| Seuil de confiance (CONV_CONFIDENCE_THRESHOLD vs CONVERSATIONAL_MIN_CONFIDENCE) | À aligner : config lue nulle part pour l’instant |
| Tests P0 après merge | OK après correction des mocks (CONVERSATIONAL_CANARY_PERCENT) |
| voice.py / _get_engine | Inchangé dans ce diff ; utilise toujours config + _is_canary |

**Recommandations** :

1. **Optionnel** : utiliser `config.CONVERSATIONAL_MIN_CONFIDENCE` dans `llm_conversation` ou `conversational_engine` à la place de `CONV_CONFIDENCE_THRESHOLD` en dur, pour piloter le seuil par env.
2. **Optionnel** : unifier ou croiser les deux docs (CONVERSATIONAL_MODE_P0.md et MODE_CONVERSATIONNEL_P0.md) pour éviter la duplication.
3. Conserver la correction des tests (mocks avec `CONVERSATIONAL_CANARY_PERCENT`) et la committer si ce n’est pas déjà fait sur main.

---

## 8. Résumé

Le merge PR #5 conserve l’architecture P0 (conversational_engine, fallback FSM, validation stricte) et ajoute :

- **Config** : variables dédiées (CONVERSATIONAL_CANARY_PERCENT, CONVERSATIONAL_MIN_CONFIDENCE) et alias.
- **Placeholders** : extension (PAIEMENT, ANNULATION, DUREE), API find/replace plus robuste et instructions système réutilisables.
- **Validator** : refonte plus stricte et lisible, avec validation des entités extraites.
- **Doc** : guide détaillé d’activation et d’usage (CONVERSATIONAL_MODE_P0.md).

Aucune incohérence bloquante ; seul le lien entre `CONVERSATIONAL_MIN_CONFIDENCE` et le code reste à faire si on veut un seuil piloté par l’environnement.
