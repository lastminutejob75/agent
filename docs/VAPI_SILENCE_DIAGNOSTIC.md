# Diagnostic silence vocal Vapi — checklist de correction

## Cause identifiée

- **Custom LLM** (`/api/vapi/chat/completions`) ne renvoie pas toujours une réponse "parlable" à temps.
- Le prompt / la policy pousse à appeler un **function_tool** à chaque tour.
- Le tool est en **async: true** → Vapi envoie le tool-call, **n’attend pas** le résultat → aucun texte pour le TTS → HANG puis silence / timeout.

---

## Contrat d’intégration (ce que Vapi doit lire)

**Mode Custom LLM** (`POST /api/vapi/chat/completions`) :

- Vapi doit lire **`choices[0].message.content`** (format OpenAI-like).
- Le backend renvoie aussi `content` à la racine et `choices[0].text` pour compatibilité.
- **Streaming :** si Vapi est en mode streaming, il attend du **SSE** (chunks `chat.completion.chunk`). Ne pas casser le format des chunks.
- **Non-streaming :** Vapi attend un JSON **chat.completion** (id, object, created, model, choices, usage).

➡️ **Objectif :** si on modifie le body côté backend, ne pas casser ces champs / formats.

*“Format OpenAI” = contrat de payload (structure d’API), pas dépendance au service OpenAI.*

---

## Deux causes backend qui peuvent faire silence (même si l’engine est OK)

### 1) Webhook 404 — grave pour le diagnostic (pas toujours la cause du silence)

Le **Server URL** webhook sert à recevoir les events Vapi (status-update, end-of-call-report, conversation-update, etc.). Si ça répond **404**, Vapi continue souvent l’appel mais on perd tout le reporting → on est aveugle pour diagnostiquer.

**À faire :** s’assurer que cette URL répond en **200** (ex. `POST https://<ton-domaine>/api/vapi/webhook`).

**Erreurs classiques :**
- mauvais service Railway (`agent-production-c246` vs `uwiagent-production`)
- mauvais path (`/api/vapi/webhook` ≠ `/api/vapi` ≠ `/api/vapi/voice`)
- route déclarée en GET seulement (Vapi envoie en **POST**)
- proxy / basePath qui modifie le chemin

**Fix minimal :** une route **POST** qui renvoie **200** (le backend a déjà `POST /api/vapi/webhook` ; si 404, corriger l’URL dans Vapi : domaine, path, base path). Dès que Railway affiche des hits POST 200 sur cette route, le câblage est bon.

---

### 2) Streaming SSE — peut **causer** le silence

En mode Custom LLM, Vapi peut être configuré de 2 façons :

| Mode | Ce que le backend doit renvoyer |
|------|----------------------------------|
| **Non-streaming** | JSON `chat.completion` ; Vapi lit `choices[0].message.content`. |
| **Streaming SSE** | `Content-Type: text/event-stream`, body en lignes `data: ...` jusqu’à `data: [DONE]`. |

**Si Vapi attend du SSE et qu’on renvoie du JSON** → Vapi ne “voit” pas de tokens → **silence / hang**.

**Côté backend :** l’endpoint `/api/vapi/chat/completions` gère déjà les deux :
- si `payload.stream === true` → réponse en **SSE** (StreamingResponse, `text/event-stream`) ;
- sinon → JSON `chat.completion` via `_chat_completion_response`.

**Côté Vapi :** si l’option “streaming” est activée, il faut que le backend reçoive bien `stream: true` (déjà le cas). Sinon, désactiver le streaming dans l’assistant pour forcer le JSON.

**Garde-fous backend (anti-régression) :**
- **Détection stream robuste** : `_parse_stream_flag(payload)` — bool, string "true"/"false"/"1"/"0", int 1/0 (évite `bool("false") == True`).
- **Point de sortie unique** : `_make_chat_response(call_id, text, is_streaming)` — tous les chemins (nominal, LockTimeout, except) passent par là → SSE si stream, sinon JSON.
- **Guard** : si on appelle `_chat_completion_response(..., _stream_requested=True)` par erreur, log `[STREAM_MISMATCH_GUARD]`.
- **Tests** : `tests/test_vapi_chat_completions_streaming.py` (nominal SSE, SSE sur exception, SSE sur LockTimeout, stream=false → JSON). Curl prod : `scripts/curl_vapi_stream.sh` (BASE_URL=… après deploy).

---

### Diagnostic express (trancher en ~60 secondes)

1. Mettre **`VAPI_DEBUG_TEST_AUDIO=true`** (Railway), déployer.
2. Passer **1 appel**, dire n’importe quoi.
3. **Interprétation :**
   - **Tu entends “TEST AUDIO 123”** → le contrat (stream/JSON) et le câblage TTS sont bons ; le silence venait d’ailleurs (contenu, chemin, tool async, etc.).
   - **Silence** → Vapi ne lit pas notre réponse (souvent : il attend du SSE et reçoit du JSON, ou mauvais champ, ou mauvais endpoint).
4. **Après le test :** remettre **`VAPI_DEBUG_TEST_AUDIO=false`** (ou retirer la variable).

---

## Stabilisation en 5 étapes (sans rajouter 50 couches)

### Étape 1 — Stopper le 404 webhook (≈2 min)

**But :** valider le câblage + récupérer les events Vapi (end-of-call-report, status, etc.).

Le backend expose déjà `POST /api/vapi/webhook`. Si Vapi reçoit 404, corriger dans l’assistant l’**URL exacte** (domaine Railway, path `/api/vapi/webhook`). Vérifier dans Railway : des hits **POST 200** sur cette route = URL bonne.

### Étape 2 — Verrouiller le contrat Custom LLM : SSE **ou** JSON, pas entre-deux

Le silence en START vient souvent de : Vapi attend du **streaming SSE** et reçoit du **JSON**, ou lit un champ différent.

- **Option la plus safe :** répondre en **SSE** (compat max). Même en “non-streaming”, beaucoup de clients consomment le premier chunk. Le backend fait déjà du SSE quand `payload.stream === true`.
- **Si tu restes en JSON :** `Content-Type: application/json`, texte dans **`choices[0].message.content`** (prioritaire), idéalement aussi **`choices[0].text`** et **`content`** à la racine (déjà le cas).

### Étape 3 — Test “au couteau” sans Vapi : curl

Avant d’appeler Vapi, tester l’endpoint.

**Si SSE attendu :**
```bash
curl -iN https://TON_DOMAIN/api/vapi/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"test"}]}'
```
Vérifier : header **`Content-Type: text/event-stream`**, lignes **`data: {...}`** puis **`data: [DONE]`**.

**Si JSON attendu :**
```bash
curl -is https://TON_DOMAIN/api/vapi/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"test"}]}'
```
Vérifier : JSON avec **`choices[0].message.content`**.

### Étape 4 — Dans Vapi : 2 checks qui tuent 80 % des silences

1. **Tool async = false** (sinon le tool-call “mange” la réponse).
2. **ToolChoice = auto** (jamais `required`).

Puis test **TEST AUDIO 123** : si tu n’entends rien → mismatch streaming/format/endpoint ; si tu entends → on repasse au texte réel.

### Étape 5 — Pourquoi tout a cassé (site + BDD)

- Nouveaux chemins (multi-tenant, call_id, locks, PG codec, etc.) → plus de latence / réponses vides.
- Vapi est impitoyable : pas de texte “parlable” au bon format à temps → hang/silence.
- Migration SQLite → Postgres peut casser la persistance (champ non sérialisé, reconstruction, lock timeout) → réponses vides ou incohérentes.

**Prévention :** contrats figés + tests d’intégration (pas “moins de code”).

---

## Prévention (éviter que ça recasse à chaque modif)

Sans LLM ni grosse refacto :

1. **Contrat figé** pour `/chat/completions` (SSE ou JSON) + **test curl en CI** (au moins vérifier 200 + body non vide ou stream valide).
2. **Healthcheck Vapi :** un script qui appelle `/chat/completions` (attendre un texte, ex. “TEST AUDIO 123” si flag) et `/api/vapi/webhook` (attendre 200).
3. **Test E2E minimal :** POST transcript “je voudrais un rdv” → vérifier que la réponse contient un texte non vide.

---

## Symptôme → cause probable

| Symptôme | Cause probable | Où vérifier |
|----------|----------------|-------------|
| Silence après que l’utilisateur a parlé | Tool `async: true` | Tools → function_tool |
| Silence dès le hello / first message | firstMessage / mode TTS | Assistant settings |
| HANG à 5 s puis coupure | Timeout tool ou LLM trop court | Timeout tool + logs Vapi |
| Webhooks en 404 | Mauvaise Server URL | serverUrl + logs Railway |

---

## 1) Tool function_tool → mettre async: false

**Où :** Vapi Dashboard → Tools → ouvrir le tool `function_tool`

**À changer :**
- **Async / Run asynchronously** → **OFF** (donc `async: false`)
- **Timeout** → valeur réaliste (ex. **10–20 s**) pour le debug  
  (si 3–5 s + cold start Railway, on peut croire que ça bug encore)

**Pourquoi :** sinon Vapi déclenche l’outil mais n’attend pas la réponse ⇒ pas de texte à dire ⇒ silence / HANG.

---

## 2) Enlever “tool obligatoire à chaque message”

Deux endroits possibles selon la config Vapi :

### A) Dans le prompt système

Chercher un texte du type :
- “MANDATORY: call this tool for EVERY user message”
- ou “always call function_tool”

**Remplacer par** une règle du type :
- “Call tools only when you need to perform an action: booking, cancel, modify, FAQ lookup. Otherwise answer normally.”

### B) Dans la policy / tool choice

- **Tool Choice :** `auto` / `required` / `none`
- **Mettre `auto`**, jamais `required`.

---

## 3) Message d’attente pendant un tool-call

Selon le setup Vapi, peut s’appeler :
- “Thinking message”
- “Interim message”
- “While running tool, say…”

**Mettre** un texte court (vocal-friendly), ex. :
- “Un instant, je regarde ça…”

Évite l’effet “blanc” quand le tool met 1–2 secondes.

---

## 4) Corriger les 404 webhooks (Server URL)

**Où :** Assistant → Settings / Webhooks / **Server URL**

Une seule URL doit répondre en **200** (pas 404).

**Erreurs classiques :**
- mauvais domaine (`uwiagent-production` vs `agent-production`)
- mauvais chemin (`/api/vapi/webhook` vs `/api/vapi` vs `/api/vapi/voice`)
- base path ajouté par Railway / proxy

**Test :** ouvrir l’URL du webhook (ex. avec `/health` si dispo) ou regarder les logs Railway au moment où Vapi envoie un event → la requête doit arriver.

---

## 5) Validation : 3 appels

Faire exactement ces 3 tests :

1. “Je voudrais un rendez-vous”
2. “Je veux annuler un rendez-vous”
3. “Transfert” puis “Je veux parler à un conseiller”

**Succès attendu :**
- plus de HANG
- l’assistant répond après chaque phrase
- tool-calls visibles et résultat utilisé

---

## Checklist de santé (après chaque modif Vapi)

À faire après chaque changement de config Vapi pour éviter la rechute :

1. [ ] Un appel simple avec `VAPI_DEBUG_TEST_AUDIO=true` fait dire “TEST AUDIO 123”.
2. [ ] Tool **async = false**.
3. [ ] **ToolChoice = auto** (jamais required).
4. [ ] **Server URL** webhook répond **200** (pas 404).
5. [ ] Dans les logs Vapi : on voit **tool result** + **assistant message**.
6. [ ] Temps total avant la première réponse < seuil acceptable (ex. 5–10 s selon infra).

➡️ Transforme ce doc en **process** de validation, pas seulement en diagnostic.

---

## Diagnostic express (trancher en 60 secondes)

1. Mettre **VAPI_DEBUG_TEST_AUDIO=true** (backend), déployer.
2. Faire **1 appel** (dire n’importe quoi).
3. **Si tu entends “TEST AUDIO 123”** → contrat (stream/JSON) et câblage TTS sont bons ; le silence venait du contenu ou du flux.
4. **Si silence** → Vapi ne lit pas la réponse (souvent : il attend du SSE et reçoit du JSON, ou mauvais champ, ou mauvais endpoint).

---

## 6 valeurs pour clore le bug à 100 %

**Ne rien changer côté Vapi tant que ces 6 valeurs n’ont pas été validées.** On sort du mode “patch”, on passe en mode “stabilisation”.

Remplir le bloc ci-dessous depuis le dashboard Vapi, puis l’envoyer pour obtenir en 1 message :
- **Config saine** → ça doit marcher
- **Incohérence précise** → exactement quoi corriger
- **Architecture instable** → quoi simplifier

**À remplir et envoyer :**

```
Tool async = ?
Tool timeout = ?
Tool serverUrl = ?

Assistant toolChoice = ?
Assistant streaming = oui / non ?
Assistant webhook serverUrl = ?
```

---

## Preuve en prod (pas seulement le doc)

*“C’est à jour” = Cursor parle du fichier local, pas d’un fait vérifiable côté Vapi/Railway. Il faut passer de “doc propre” à “preuve en prod”.*

### Les 3 valeurs qui déterminent 90 % du bug silence

| # | Valeur | Conséquence |
|---|--------|-------------|
| 1 | **Streaming Vapi (Custom LLM) : ON ou OFF ?** | Si **ON** → Vapi attend du **SSE** (`text/event-stream` + `data: ...` + `[DONE]`). Si **OFF** → Vapi accepte du **JSON** (`chat.completion`) avec `choices[0].message.content`. **Si Vapi est ON et que le backend renvoie du JSON → silence quasi garanti.** |
| 2 | **URL exacte du Custom LLM** appelée par Vapi | Confirmer que Vapi appelle bien la route qui répond (ex. `.../api/vapi/chat/completions` et pas `.../api/vapi` sans le path). |
| 3 | **Content-Type réel** renvoyé par le backend | À sortir avec `curl -i` : **SSE** = `Content-Type: text/event-stream` ; **JSON** = `Content-Type: application/json`. |

### Méthode “preuve” (à faire maintenant)

**A) Test direct backend (sans Vapi)**

1. Tester l’endpoint LLM **exact** (celui configuré dans Vapi) :
   ```bash
   curl -iN "https://TON_URL/api/vapi/chat/completions" \
     -H "Content-Type: application/json" \
     -d '{"messages":[{"role":"user","content":"test"}]}'
   ```
   - Tu vois **`text/event-stream`** + lignes **`data:`** + **`[DONE]`** → SSE OK.
   - Tu vois **`application/json`** → réponse non-streaming.

2. Tester le webhook :
   ```bash
   curl -is "https://TON_URL/api/vapi/webhook" -X POST -H "Content-Type: application/json" -d '{}'
   ```
   - **404** → URL webhook / route encore fausse.
   - **200** → OK.

**B) Test Vapi “TEST AUDIO 123”**

- Si le backend renvoie “TEST AUDIO 123” et que **tu n’entends rien** → Vapi ne lit pas ce flux (mauvaise URL / mauvais mode / mauvais champ / **mismatch streaming**).
- Si **tu l’entends** → backend + format OK ; ensuite on retire le flag.

### Tool async=false ne suffit pas si le streaming est mauvais

Le diagnostic sur `async=true` est bon (ça peut “manger” la réponse), mais **même en async=false** :
- si Vapi attend du **SSE** et reçoit du **JSON** → silence ;
- si Vapi lit un champ différent (rare) → silence.

### Scénario le plus probable

**Vapi Custom LLM attend du SSE ; l’endpoint répond en JSON (non-streaming).**  
→ Vapi “hang” / silence même si on renvoie du texte.

**Correction qui règle tout :** forcer **SSE** sur `/chat/completions` (au moins pour les appels Vapi), ou garder JSON et **désactiver le streaming** dans l’assistant Vapi.

### Verdict en 2 minutes

Coller les **3 valeurs** (streaming ON/OFF, URL LLM exacte, Content-Type observé au curl) → réponse exacte :
- **“mismatch streaming → il faut SSE”**, ou
- **“mauvaise URL”**, ou
- **“format OK, problème tool/pipeline”**.

---

## À exécuter maintenant (copier-coller)

La prochaine étape n’est plus “écrire”, c’est **exécuter la preuve**. Cursor ne sait pas si c’est vrai en prod ; on tranche avec **3 faits mesurés**.

### 1) Mesurer le Content-Type du LLM (Railway)

Remplacer `TON_DOMAINE` par le domaine **exact** configuré dans Vapi pour le Custom LLM.

```bash
curl -iN "https://TON_DOMAINE/api/vapi/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"test audio"}]}' | head -n 20
```

**Noter :**
- le header **`Content-Type: ...`**
- si tu vois des lignes **`data: ...`** (SSE) ou un **JSON** direct

### 2) Vérifier si le webhook répond (lever le 404)

```bash
curl -is "https://TON_DOMAINE/api/vapi/webhook" \
  -X POST -H "Content-Type: application/json" -d '{}' | head -n 20
```

**Noter :** `HTTP/1.1 200` ou `404`.

### 3) Dans Vapi : récupérer Streaming + URL exacte

Dans la config du provider **Custom LLM** :
- **Streaming :** ON ou OFF (ou “SSE streaming enabled” / “stream”).
- **URL exacte** du Custom LLM (celle que Vapi appelle réellement).

### Interprétation immédiate

Coller ces **3 lignes** (texte brut) pour obtenir le verdict sans ajouter de code :

```
Streaming Vapi = ON / OFF
URL LLM exacte = (copie de l’URL configurée dans Vapi)
Content-Type observé au curl = ... (+ "je vois data:" oui/non)
```

**Règles :**
- **Streaming ON** + **Content-Type = application/json** → **mismatch** ⇒ soit désactiver le streaming dans Vapi, soit répondre en SSE côté backend.
- **Streaming OFF** + **Content-Type = text/event-stream** → **mismatch inverse** ⇒ soit activer le streaming, soit répondre en JSON.
- **URL Vapi** ≠ **URL curl testée** ≠ **URL réellement appelée** → **mauvaise route** ⇒ silence.

**Piège fréquent :** beaucoup testent `.../api/vapi` alors que Vapi appelle `.../api/vapi/chat/completions` (ou l’inverse). **Si l’URL exacte n’est pas identique au caractère près, le curl ne prouve rien.**

**Exemple réel (config Composer/Vapi) :** si **Custom LLM URL** = `https://.../api/vapi` (sans `/chat/completions`), le backend ne reçoit pas les requêtes sur le bon handler → 404 ou mauvaise route → silence. La bonne URL est **`.../api/vapi/chat/completions`**.

Verdict possible : **“streaming mismatch”**, **“mauvaise URL”**, ou **“format OK → tool/pipeline”**.

---

## Pour avancer maintenant (sans screenshot) — 3 infos qui tranchent

Coller ces **3 infos** (texte brut) pour savoir quoi corriger exactement :

1. **Dans Vapi Custom LLM :** streaming **ON** ou **OFF** (si tu vois l’option).
2. **URL exacte** appelée pour le LLM (celle qui reçoit le transcript user).
3. **Content-Type** que le backend renvoie sur `/chat/completions` (logs Railway ou `curl -i`).

Avec ça, on tranche immédiatement : **“Vapi attend SSE”** vs **“mauvais champ JSON”** vs **“mauvais endpoint”**.

---

## Ce qu’il faut envoyer pour “clique ici, puis là” au pixel près

Envoyer une **capture** (ou copier/coller texte) de :

1. **Tool function_tool :** async, timeout, serverUrl, response mapping (s’il existe)
2. **Assistant :** modèle (custom LLM), tool choice (auto/required), prompt système (la partie “mandatory”)

**Même juste les valeurs** (sans screenshot) suffit, par exemple :

```
Tool async=true / timeout=5 / serverUrl=...
Assistant toolChoice=required / prompt contient "MANDATORY…"
```

Réponse possible : liste exacte des champs à modifier + valeurs recommandées.
