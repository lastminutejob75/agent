# Configuration Vapi - Assistant Vocal

## Snippet de configuration (API / Dashboard)

Pour un agent fluide avec **interruptions** et **validations rapides** ("Oui !" = premier créneau), utilisez une config de ce type :

```json
{
  "name": "UWI Booking Agent",
  "model": {
    "provider": "openai",
    "model": "gpt-4",
    "messages": [
      {
        "role": "system",
        "content": "<SYSTEM_PROMPT avec business_name=[NOM_BUSINESS]>"
      }
    ],
    "temperature": 0.7,
    "maxTokens": 150
  },
  "voice": {
    "provider": "11labs",
    "voiceId": "21m00Tcm4TlvDq8ikWAM",
    "stability": 0.5,
    "similarityBoost": 0.75,
    "interruptible": true,
    "fillerInjectionEnabled": false
  },
  "transcriber": {
    "provider": "deepgram",
    "model": "nova-2",
    "language": "fr",
    "smartFormat": true,
    "endpointing": 200,
    "interimResults": true
  },
  "firstMessage": "Bonjour, {business_name}, je peux vous aider ?",
  "endCallMessage": "Au revoir et bonne journée !",
  "endCallPhrases": ["au revoir", "bonne journée", "merci au revoir"],
  "serverUrl": "https://ton-backend.railway.app/webhook/vapi",
  "serverUrlSecret": "ton_secret_webhook"
}
```

### Points critiques

| Paramètre | Valeur | Rôle |
|-----------|--------|------|
| **voice.interruptible** | `true` | Permet à l'utilisateur de couper la parole (barge-in) ; essentiel pour "Oui !" pendant l'énumération des créneaux. |
| **voice.fillerInjectionEnabled** | `false` | Évite les "euh" pendant les interruptions. |
| **transcriber.endpointing** | `200` | Détection rapide de fin de parole (ms). |
| **transcriber.interimResults** | `true` | Réactivité en temps réel. |
| **model.maxTokens** | `150` | Réponses courtes, adaptées au vocal. |

Remplacez `serverUrl` et `serverUrlSecret` par vos valeurs (Railway, Vercel, etc.).

### Test rapide après déploiement

Scénario à valider :

```
Agent : "Voici les créneaux : Vendredi 5 à 14h, dites 1. Sam—"
Toi  : "Oui !"
→ L'agent doit répondre : "Parfait ! Je réserve vendredi 5 à 14h. Votre nom ?"
```

Si l'agent redemande "un, deux ou trois" ou clarifie au lieu de prendre le premier créneau, vérifier : `interruptible: true`, SYSTEM_PROMPT (section "DÉTECTION DES VALIDATIONS RAPIDES") et le handler WAIT_CONFIRM côté backend.

---

## First Message (Message d'accueil)

Dans le Dashboard Vapi, configurez le **First Message** :

```
Bonjour Cabinet Dupont, vous appelez pour un rendez-vous ?
```

> **Note** : Remplacez "Cabinet Dupont" par le nom de votre entreprise.
> Cette question directe permet d'orienter rapidement l'appel (OUI → booking, NON → question/autre).

---

## Configuration complète

### 1. Assistant Settings

| Paramètre | Valeur |
|-----------|--------|
| **Name** | Agent Accueil PME |
| **First Message** | `Bonjour Cabinet Dupont, vous appelez pour un rendez-vous ?` |
| **Voice** | Jérémie (French, Paris accent) |
| **Language** | French |
| **Model** | Custom LLM (recommandé) |

**Prompt / System instructions** : pour un ton **médical professionnel** (sans "Nickel", "Super", ton décontracté), utiliser le prompt décrit dans **[docs/VAPI_PROMPT_ASSISTANT.md](docs/VAPI_PROMPT_ASSISTANT.md)**.

### 2. Server URL (Webhook)

```
https://votre-domaine.com/api/vapi/webhook
```

Exemple avec ngrok :
```
https://abc123.ngrok-free.app/api/vapi/webhook
```

### 3. Reconnaissance du numéro (caller ID)

Le backend utilise le **numéro de l’appelant** pour :
- Proposer en vocal : *« Votre numéro est bien le 06 12 34 56 78 ? »* (sans le redemander),
- Alimenter la mémoire client et les rapports.

**Où c’est fait :**
- **Webhook** (`/api/vapi/webhook`) : Vapi envoie `assistant.started` et `status-update` avec **`message.call.customer.number`**. Le backend persiste ce numéro en session dès réception (pour que les requêtes Chat Completions, qui ne reçoivent pas `call`, aient quand même `session.customer_phone`).
- Extraction : `backend/tenant_routing.py` → `extract_customer_phone_from_vapi_payload(payload)` — chemins **webhook** : `message.call.customer.number`, `message.customer.number` ; chemins **Chat Completions** : `call.customer.number`, `call.from`, etc.
- Utilisation : `backend/routes/voice.py` (webhook → persistance ; chat/completions → lecture session), puis `backend/engine.py` en QUALIF_CONTACT / CONTACT_CONFIRM.

**Si le numéro n’apparaît plus (diagnostic) :**
1. **Logs à regarder (Railway / stdout) :**
   - `CUSTOMER_PHONE_RECOGNITION` : `has_number` (true/false), `payload_has_call`, `call_has_customer`, `call_has_from`, `call_keys` (liste des clés dans `payload.call`). Si `has_number: false` et `payload_has_call: false` → Vapi n’envoie pas l’objet `call` dans le webhook Custom LLM.
   - `[CALLER_ID] persisted_on_greeting` : le numéro a été persisté au premier tour (greeting).
   - `[QUALIF] no_caller_id → QUALIF_CONTACT` : on demande le numéro car `session.customer_phone` est vide (numéro absent du payload ou non persisté).
2. **Causes possibles :** (1) Le numéro n’est pas envoyé par Vapi/Twilio (numéro masqué, config provider, ou payload Custom LLM sans `call`). (2) Le numéro est envoyé mais on ne le persistait pas au premier tour → désormais on persiste au greeting si présent. (3) Session rechargée sans `customer_phone` → vérifier que `session_store` sauvegarde bien `customer_phone` (SQLite/pickle).
3. **Côté Vapi / provider :** s’assurer que le webhook reçoit bien `call.customer.number` ou `call.from` (Twilio/Vonage envoie le caller ID selon la doc du provider).

### 4. Voix recommandée

Pour un accent parisien naturel, utilisez :
- **Provider** : ElevenLabs ou PlayHT
- **Voice** : Jérémie (ou voix française masculine)
- **Style** : Conversational, Casual

---

## Flows de conversation

### FLOW A : Rendez-vous (80% des appels)
```
🤖 "Bonjour Cabinet Dupont, vous appelez pour un rendez-vous ?"
👤 "Oui"
🤖 "C'est à quel nom ?"
👤 "Jean Dupont"
🤖 "Parfait Jean. C'est pour quoi ?"
👤 "Une consultation"
🤖 "OK. Plutôt le matin ou l'après-midi ?"
👤 "Le matin"
🤖 "OK, j'ai trois créneaux pour vous. Le un, c'est lundi 27 à 9h. Le deux, mardi 28 à 10h. Le trois, mercredi 29 à 11h. Dites-moi juste : un, deux ou trois."
👤 "Le premier"
🤖 "Parfait. Votre numéro de téléphone ?"
👤 "06 12 34 56 78"
🤖 "Nickel. Rendez-vous confirmé lundi 27 à 9h pour Jean. Vous recevrez un SMS de confirmation. Bonne journée !"
```

### FLOW B : Question / FAQ (15% des appels)
```
🤖 "Bonjour Cabinet Dupont, vous appelez pour un rendez-vous ?"
👤 "Non, je voudrais savoir vos horaires"
🤖 "Nous sommes ouverts du lundi au vendredi, de 9h à 18h. Je peux vous aider pour autre chose ?"
👤 "Non merci"
🤖 "Parfait. Bonne journée."
```

### FLOW C : Annulation (3% des appels)
```
🤖 "Bonjour Cabinet Dupont, vous appelez pour un rendez-vous ?"
👤 "Non, je veux annuler mon rendez-vous"
🤖 "D'accord. À quel nom est le rendez-vous, s'il vous plaît ?"
👤 "Jean Dupont"
🤖 "Vous avez un rendez-vous lundi 27 janvier à 9h. Souhaitez-vous que je l'annule ?"
👤 "Oui"
🤖 "Votre rendez-vous est annulé. Bonne journée."
```

### FLOW D : Modification (2% des appels)
```
🤖 "Bonjour Cabinet Dupont, vous appelez pour un rendez-vous ?"
👤 "Je voudrais déplacer mon rendez-vous"
🤖 "Pas de souci. C'est à quel nom ?"
👤 "Jean Dupont"
🤖 "Vous avez un rendez-vous lundi 27 janvier à 9h. Vous voulez le déplacer ?"
👤 "Oui"
🤖 "OK, j'ai annulé l'ancien. Plutôt le matin ou l'après-midi pour le nouveau ?"
→ Reprend le flow de booking
```

### FLOW E : Cas flou
```
🤖 "Bonjour Cabinet Dupont, vous appelez pour un rendez-vous ?"
👤 "Euh... je sais pas"
🤖 "D'accord. Avez-vous une question ou souhaitez-vous prendre rendez-vous ?"
👤 "Prendre rendez-vous"
→ FLOW A
```

### FLOW F : Transfert humain
```
🤖 "Bonjour Cabinet Dupont, vous appelez pour un rendez-vous ?"
👤 "C'est pour mes résultats d'analyses"
🤖 "Je comprends. Je vais vous mettre en relation avec quelqu'un qui pourra mieux vous aider. Un instant."
→ TRANSFERT
```

---

## Test de configuration

### 1. Vérifier le health check
```bash
curl https://votre-domaine.com/api/vapi/health
```

Réponse attendue :
```json
{
  "status": "ok",
  "service": "vapi",
  "message": "Vapi webhook is ready"
}
```

### 2. Tester le webhook
```bash
curl -X POST https://votre-domaine.com/api/vapi/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "message": {"type": "user-message", "content": "je voudrais un rdv"},
    "call": {"id": "test_123"}
  }'
```

---

## Troubleshooting

### Le bot ne répond pas
1. Vérifier que le Server URL est correct dans Vapi
2. Vérifier que le serveur est accessible (ngrok, railway, vercel)
3. Vérifier les logs : `docker logs agent-accueil-pme`

### L'extraction ne fonctionne pas
L'extraction est **conservatrice** : si le pattern n'est pas clair, l'agent redemande.

Patterns reconnus :
- Nom : "je suis [prénom nom]", "c'est [prénom nom]"
- Motif : "contrôle", "douleur", "ordonnance", "vaccin", etc.
- Préférence : "matin", "après-midi", "lundi", "mardi matin"

### La voix n'est pas naturelle
Vérifiez que vous utilisez une voix française avec accent parisien.
Recommandé : ElevenLabs "Jérémie" ou similaire.
