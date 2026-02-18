# Checklist — Assistant en français (plus d’anglais)

Si l’assistant parle en anglais ou dit « there was an error », **tout vient de la config Vapi** (le backend ne renvoie que du français). À corriger dans le **dashboard Vapi** uniquement.

---

## En 3 étapes (à faire dans l’ordre)

### Étape 1 — Choisir Custom LLM
- Ouvre ton **Assistant** dans Vapi → onglet **Model** (ou **AI**).
- Tu dois voir un choix du type : **OpenAI** / **Anthropic** / **Custom LLM** (ou **Custom**).
- Sélectionne **Custom LLM** (ou **Custom**).
- Dans **Server URL** (ou **Custom LLM URL**), mets exactement :  
  `https://agent-production-c246.up.railway.app/api/vapi/chat/completions`  
- **Sauvegarde**. Sans ça, Vapi utilise son modèle par défaut (souvent en anglais) et n’appelle jamais ton backend pour les réponses.

### Étape 2 — Premier message en français
- Dans le même Assistant → champ **First Message** (ou **Message d’accueil**).
- **Supprime** tout texte en anglais (ex. "Hello, how can I help?").
- Mets **exactement** :  
  `Bonjour, vous appelez pour un rendez-vous ?`  
- **Sauvegarde**. C’est ce que l’assistant dit dès que l’appel est décroché ; si c’est en anglais, tout le début sera en anglais.

### Étape 3 — Langue de l’assistant
- Cherche un champ **Language** (ou **Langue**) dans les paramètres de l’assistant.
- Mets **French** (ou **Français**).
- Si tu as un **System prompt** / **Instructions** : ajoute en première ligne :  
  `Tu réponds uniquement en français.`  
- **Sauvegarde**.

Ensuite refais un **nouvel appel** (pas juste « reprendre »). Si après ces 3 étapes c’est encore en anglais, envoie une capture d’écran de la page **Model** de ton assistant (sans données sensibles) pour qu’on voie ce qui est sélectionné.

---

## 1. Model = Custom LLM (obligatoire)

- **Dashboard Vapi** → ton **Assistant** → **Model**.
- Choisir **Custom LLM** (pas OpenAI, pas Claude seul).
- **Server URL** doit être :  
  `https://agent-production-c246.up.railway.app/api/vapi/chat/completions`  
  (ou ton URL backend + `/api/vapi/chat/completions`).

Si ce n’est pas Custom LLM, Vapi utilise son propre modèle (souvent en anglais) et ignore tes réponses backend.

---

## 2. First Message (premier message) en français

- **First Message** (message d’accueil au début de l’appel) doit être en français, par exemple :
  ```
  Bonjour, vous appelez pour un rendez-vous ?
  ```
  ou (avec le nom du cabinet) :
  ```
  Bonjour Cabinet Dupont, vous appelez pour un rendez-vous ?
  ```

Si c’est en anglais (« Hello, how can I help? »), le tout premier message sera en anglais.

---

## 3. Language = French

- Dans les paramètres de l’assistant, chercher **Language** (ou équivalent).
- Mettre **French** (ou **Français**).

---

## 4. System instructions / prompt en français

- **System instructions** (ou **System prompt**) : ajouter en tête du prompt :
  ```
  Tu réponds uniquement en français. Never respond in English.
  ```
  Puis le reste du prompt (voir `docs/VAPI_PROMPT_ASSISTANT.md` et `docs/VAPI_PROMPT_BOOKING_STATUS.md`).

---

## 5. Transcriber en français

- **Transcriber** → **Language** : **fr** (ou **French**).  
  Déjà indiqué dans `VAPI_CONFIG.md` ; à confirmer si tu as changé la config.

---

## 6. assistant-request (obligatoire côté backend)

Vapi envoie un event **assistant-request** au webhook au début de l’appel. Si le backend répond **200 avec un body vide** → Vapi considère qu’aucun assistant n’est retourné → fallback anglais / fin d’appel.

**Recommandé (Option A — le plus stable)**  
- Sur **Railway** : ajouter la variable **VAPI_ASSISTANT_ID** = l’ID de l’assistant déjà créé dans le dashboard Vapi (ex. `78dd0e14-337e-40ab-96d9-7dbbe92cdf95`).  
- Le backend répond alors uniquement `{"assistantId": "..."}`. Aucune dépendance Postgres, aucun custom-llm au démarrage ; tu utilises l’assistant déjà configuré en FR (tools, prompt, etc.).

**Fallback (Option B — transient)**  
- Si **VAPI_ASSISTANT_ID** n’est pas défini : le backend renvoie un assistant **transient** avec `firstMessage` en français et Custom LLM. Définir **VAPI_PUBLIC_BACKEND_URL** (ou **APP_BASE_URL**) sur Railway, ex. `https://agent-production-c246.up.railway.app` (sans slash final). Plus fragile (latence, PG, etc.).

**À vérifier après déploiement**  
Dans les webhook logs Vapi : **Assistant Request** → `responseBody` doit contenir `assistantId` ou `assistant` ; dans le call, `assistantId` ne doit plus être null.

---

## 7. Webhook et Tool URL

- **Webhook** : `https://agent-production-c246.up.railway.app/api/vapi/webhook`
- **Tool** (function calling) : `https://agent-production-c246.up.railway.app/api/vapi/tool`

Les trois URLs (Custom LLM, Webhook, Tool) doivent pointer vers le **même** backend Railway.

---

## Résumé

| Où (Vapi) | Paramètre | Valeur |
|-----------|-----------|--------|
| Model | Type | **Custom LLM** |
| Model | Server URL | `https://<backend>/api/vapi/chat/completions` |
| Assistant | First Message | **Français** (ex. « Bonjour, vous appelez pour un rendez-vous ? ») |
| Assistant | Language | **French** |
| System prompt | Première ligne | « Tu réponds uniquement en français. » |
| Transcriber | language | **fr** |
| Backend (Railway) | **VAPI_PUBLIC_BACKEND_URL** ou **APP_BASE_URL** | `https://<ton-backend>.up.railway.app` (pour assistant-request transient) |

Après modification, **sauvegarder** l’assistant et **retester un appel**. Si tu entends encore de l’anglais, c’est en général le **First Message** ou le **Model** (pas Custom LLM) qu’il faut corriger en priorité.
