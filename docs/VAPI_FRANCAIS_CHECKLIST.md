# Checklist — Assistant en français (plus d’anglais)

Si l’assistant parle en anglais ou dit « there was an error », vérifier **dans le dashboard Vapi** les points suivants. Le backend renvoie toujours du français ; l’anglais vient de la config Vapi.

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

## 6. Webhook et Tool URL

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

Après modification, **sauvegarder** l’assistant et **retester un appel**. Si tu entends encore de l’anglais, c’est en général le **First Message** ou le **Model** (pas Custom LLM) qu’il faut corriger en priorité.
