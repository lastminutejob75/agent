# Diagnostic production : pourquoi des appels s'arrêtent avant CONFIRMED ?

Quand les tests passent mais qu'en prod certains appels n'arrivent pas au RDV confirmé, les causes sont **environnementales** (Vapi, réseau, comportement utilisateur).

---

## 1. Logs ajoutés dans l'engine (Railway)

| Pattern | Signification |
|--------|----------------|
| `[FLOW]` | Début de traitement : conv_id, state, turn_count, début du message user |
| `[STATE_CHANGE]` | Transition vers WAIT_CONFIRM (créneaux proposés) |
| `[SLOTS_SENT]` | Message des créneaux envoyé (longueur + aperçu 200 car.) — utile si TTS coupé |
| `[BOOKING_ATTEMPT]` | Tentative de réservation (conv_id, slot_idx) |
| `[BOOKING_RESULT]` | Résultat : success=True/False (False = créneau déjà pris) |
| `[BOOKING_RETRY]` | Créneau pris → reproposition matin/après-midi (retry 1 ou 2) |
| `[INTERRUPTION]` | Client a choisi un créneau pendant l'énonciation (barge-in positif) |
| `[RDV_CONFIRMED]` | RDV confirmé (conv_id, slot_label, name) |
| `[ANTI_LOOP]` | Anti-boucle déclenchée (turn_count > max_turns) |

### Commandes Railway

```bash
# Derniers flux par conversation
railway logs --tail 200 | grep -E "\[FLOW\]|\[STATE_CHANGE\]|\[BOOKING_|\[RDV_CONFIRMED\]"

# RDV bien confirmés
railway logs --tail 500 | grep "\[RDV_CONFIRMED\]"

# Échecs de réservation (créneau pris)
railway logs --tail 500 | grep "\[BOOKING_RESULT\].*success=False"

# Anti-loop déclenchée
railway logs --tail 500 | grep "\[ANTI_LOOP\]"

# Longueur des messages créneaux (TTS trop long ?)
railway logs --tail 500 | grep "\[SLOTS_SENT\]"
```

---

## 2. Checklist diagnostic

### 2.1 Où s'arrête le flow ?

- **`state=CONFIRMED`** dans les logs → RDV réussi.
- **`[BOOKING_RESULT] success=False`** → Créneau plus disponible entre proposition et confirmation.
- **`[ANTI_LOOP]`** → Trop de tours (par défaut 25) → menu 1/2/3/4.
- **`TRANSFERRED`** sans `[BOOKING_RESULT]`** → Transfert pour autre raison (recovery, intent override).

### 2.2 Vapi : message créneaux coupé ?

- **Symptôme** : l’agent s’arrête après « Voici les créneaux » ou équivalent.
- **Log** : `[SLOTS_SENT] len=...` — si > 300–400 caractères, le TTS peut tronquer ou couper.
- **Vérifier** : dashboard Vapi que la réponse complète est bien reçue.
- **Piste** : raccourcir les labels de créneaux en vocal (ex. « Ven 7 à 14h » au lieu de « Vendredi 07/02 - 14:00 ») si besoin.

### 2.3 Interruptions / intent override

- **Symptôme** : l’utilisateur pose une question (FAQ, adresse) pendant le booking.
- **Log** : `intent_override` ou changement d’état inattendu après un message user.
- **Comportement actuel** : les intents forts (CANCEL, TRANSFER, etc.) préemptent ; une FAQ en WAIT_CONFIRM peut faire sortir du flow. À croiser avec les logs.

### 2.4 Timeout session (15 min)

- **Log** : `SESSION_EXPIRED` ou `session expirée`.
- **Piste** : augmenter le TTL pour le canal vocal (ex. 30 min) dans la config si les appels sont longs.

### 2.5 Créneau pris entre proposition et confirmation

- **Log** : `[BOOKING_RESULT] success=False`, puis `[BOOKING_RETRY]` si retry activé.
- **Comportement** : retry 2× (reproposition matin/après-midi), puis transfert au 3e échec.

### 2.6 Limites recovery

- **name_fails**, **slot_choice_fails**, **phone** : après N échecs → transfert ou INTENT_ROUTER.
- **Log** : `recovery_step`, `filler_detected`, ou compteurs dans les logs métier.
- Ajuster les seuils dans `config.py` ou les constantes du module concerné si les utilisateurs échouent souvent (ex. numéro à 3 tentatives).

---

## 3. Constantes à ajuster si besoin

| Constante | Fichier | Défaut | Piste si problème |
|-----------|---------|--------|--------------------|
| `SESSION_TTL_MINUTES` | config | 15 | 30 pour vocal |
| `MAX_TURNS_ANTI_LOOP` | Session / config | 25 | 40 pour vocal |
| `CONFIRM_RETRY_MAX` | config | 1 | Nombre de retries avant transfert sur choix créneau |
| Recovery (name, slot_choice, phone) | engine / ClarificationMessages | 2–3 | Monter à 3 si trop de transferts |

---

## 4. Plan d’action immédiat

1. **Déployer** les logs (déjà présents dans l’engine).
2. **Sur Railway** : lancer les commandes ci-dessus et noter pour quelques appels :
   - dernier `[FLOW]` / `[STATE_CHANGE]` / `[BOOKING_*]` / `[RDV_CONFIRMED]` ou `TRANSFERRED`,
   - présence de `[ANTI_LOOP]`, `[BOOKING_RESULT] success=False`, `[SLOTS_SENT] len=...`.
3. **Corréler** avec le dashboard Vapi (durée, fin d’appel, dernier message reçu).
4. Selon les résultats : ajuster TTS (longueur message), timeouts, recovery, ou ajouter une reproposition si créneau pris.

---

## 5. Mode d'emploi opérationnel

### 5.1 Déploiement et première analyse

```bash
# Commit + push
git add backend/engine.py backend/prompts.py backend/main.py backend/config.py docs/DIAGNOSTIC_PROD_RDV.md
git commit -m "feat: retry créneau pris, stats bookings, guide diagnostic prod"
git push origin main

# Vérifier le déploiement
railway logs --tail 20
# Tu dois voir les logs [FLOW], [STATE_CHANGE], etc.
```

### 5.2 Phase 1 : Tracer 3 appels complets (15 min)

En live : `railway logs --tail`

**Ce que tu dois voir pour un RDV réussi :**

```
[FLOW] conv_abc123, state=START, turn=0
[STATE_CHANGE] conv_abc123: START → QUALIF_NAME
[FLOW] conv_abc123, state=QUALIF_NAME, turn=1
[STATE_CHANGE] conv_abc123: QUALIF_NAME → QUALIF_PREF
[FLOW] conv_abc123, state=QUALIF_PREF, turn=2
[STATE_CHANGE] conv_abc123: QUALIF_PREF → WAIT_CONFIRM
[SLOTS_SENT] conv_abc123, channel=voice, length=287, msg="Très bien. J'ai trois créneaux..."
[FLOW] conv_abc123, state=WAIT_CONFIRM, turn=3
[BOOKING_ATTEMPT] conv_abc123, slot_idx=1
[BOOKING_RESULT] conv_abc123, success=True
[RDV_CONFIRMED] conv_abc123, slot=vendredi 7 février 14h, name=Jean Dupont
```

### 5.3 Phase 2 : Identifier les abandons (15 min)

**A. Sessions sans CONFIRMED**

```bash
# Lister les conv_id qui ont démarré (dernières 24h)
railway logs --since 24h | grep "\[FLOW\]" | grep "state=START" | cut -d',' -f1

# Pour un conv_id, vérifier si RDV confirmé
railway logs --since 24h | grep "conv_abc123" | grep "\[RDV_CONFIRMED\]"
# Si aucun résultat → RDV non confirmé
```

**B. Dernier état avant abandon**

```bash
railway logs --since 24h | grep "conv_abc123" | grep "\[STATE_CHANGE\]" | tail -1
# Exemple : [STATE_CHANGE] conv_abc123: WAIT_CONFIRM → TRANSFERRED
# → Le client a été transféré pendant la sélection de créneau
```

### 5.4 Phase 3 : Diagnostics ciblés (30 min)

| Diagnostic | Commande | Action si problème |
|------------|----------|---------------------|
| **TTS coupé ?** | `railway logs --since 24h \| grep "\[SLOTS_SENT\]"` | Si length > 400 → version compacte créneaux en vocal |
| **Créneaux déjà pris ?** | `railway logs --since 24h \| grep "\[BOOKING_RESULT\]" \| grep "success=False"` | Retry automatique déjà implémenté (2 max) ; vérifier [BOOKING_RETRY] |
| **Anti-loop ?** | `railway logs --since 24h \| grep "\[ANTI_LOOP\]"` | Augmenter `MAX_TURNS_ANTI_LOOP` (ex. 40) dans config/session |
| **Recovery phone ?** | `railway logs --since 24h \| grep "recovery_limit_reached"` | `RECOVERY_LIMITS["phone"]` passé à 3 dans config |

### 5.5 Dashboard de monitoring

**Endpoint :** `GET /api/stats/bookings`

Retourne pour les dernières 24h (sessions avec `last_seen_at` dans la fenêtre) :

- `total_sessions`, `confirmed_bookings`, `transferred`, `intent_router`
- `conversion_rate` (%), `abandon_rate` (%)

Exemple : `https://ton-backend.railway.app/api/stats/bookings`

### 5.6 Commandes rapides

```bash
# Taux de confirmation (dernière heure)
railway logs --since 1h | grep "\[RDV_CONFIRMED\]" | wc -l

# Sessions totales dernière heure (démarrages)
railway logs --since 1h | grep "\[FLOW\]" | grep "state=START" | wc -l

# Échecs TRANSFERRED pendant booking
railway logs --since 1h | grep "\[STATE_CHANGE\].*TRANSFERRED" | grep -v "CONFIRMED"

# Créneaux pris
railway logs --since 6h | grep "\[BOOKING_RESULT\].*success=False"

# TTS trop longs (length >= 400)
railway logs --since 6h | grep "\[SLOTS_SENT\]" | grep "length=[4-9][0-9][0-9]"
```

### 5.7 Métriques cibles

| Métrique | Cible | Action si < cible |
|----------|-------|--------------------|
| Taux de confirmation | > 70 % | Analyser abandons (phase 2) |
| Créneau pris (False) | < 5 % | Retry déjà en place ; surveiller [BOOKING_RETRY] |
| Anti-loop déclenché | < 2 % | Augmenter MAX_TURNS |
| Recovery phone atteint | < 10 % | Déjà à 3 tentatives |
| TTS > 350 car. | < 20 % | Version compacte créneaux |

### 5.8 Checklist opérationnelle

**Jour J (déploiement)**  
- [ ] Déployer sur Railway  
- [ ] Vérifier que les logs [FLOW] apparaissent  
- [ ] Faire 1 appel test complet  
- [ ] Vérifier dans les logs : [RDV_CONFIRMED] apparaît  
- [ ] Tester `/api/stats/bookings`  

**J+1 (analyse)**  
- [ ] Récupérer les conv_id des 10 derniers appels  
- [ ] Pour chaque conv_id : état final, turn_count, [BOOKING_RESULT] success=False, longueur [SLOTS_SENT]  
- [ ] Identifier le pattern dominant d'échec  
- [ ] Appliquer le fix (retry / TTS court / recovery)  

**J+2 (optimisation)**  
- [ ] Taux de conversion > 70 % ? → OK  
- [ ] < 70 % ? → Analyser les abandons restants  
- [ ] Dashboard /api/stats/bookings utilisé  
- [ ] Alerting si taux < 50 % (optionnel)
