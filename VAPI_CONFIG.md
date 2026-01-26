# Configuration Vapi - Assistant Vocal

## First Message (Message d'accueil)

Dans le Dashboard Vapi, configurez le **First Message** :

```
Bonjour Cabinet Dupont, je vous écoute.
```

> **Note** : Remplacez "Cabinet Dupont" par le nom de votre entreprise.

---

## Configuration complète

### 1. Assistant Settings

| Paramètre | Valeur |
|-----------|--------|
| **Name** | Agent Accueil PME |
| **First Message** | `Bonjour Cabinet Dupont, je vous écoute.` |
| **Voice** | Jérémie (French, Paris accent) |
| **Language** | French |
| **Model** | Claude 3.5 Sonnet (ou Custom LLM) |

### 2. Server URL (Webhook)

```
https://votre-domaine.com/api/vapi/webhook
```

Exemple avec ngrok :
```
https://abc123.ngrok-free.app/api/vapi/webhook
```

### 3. Voix recommandée

Pour un accent parisien naturel, utilisez :
- **Provider** : ElevenLabs ou PlayHT
- **Voice** : Jérémie (ou voix française masculine)
- **Style** : Conversational, Casual

---

## Flow de conversation attendu

### Cas 1 : Client bavard (extraction intelligente)
```
🤖 "Bonjour Cabinet Dupont, je vous écoute."
👤 "Bonjour, je suis Jean Dupont, je voudrais un RDV pour un contrôle, plutôt mardi matin"
    ↓ Extraction: nom ✅, motif ✅, pref ✅
🤖 "Parfait Jean Dupont, pour contrôle. Pour vous rappeler, téléphone ou email ?"
👤 "Mon téléphone c'est le 06 12 34 56 78"
🤖 "OK, j'ai trois créneaux pour vous. Le un, c'est mardi 10h. Le deux, mardi 14h. Le trois, mercredi 9h. Dites-moi juste : un, deux ou trois."
👤 "Le un"
🤖 "C'est tout bon Jean Dupont ! Rendez-vous confirmé pour mardi 10h. On vous attend, à très bientôt !"
```

### Cas 2 : Client minimal (flow classique)
```
🤖 "Bonjour Cabinet Dupont, je vous écoute."
👤 "Je voudrais un rendez-vous"
🤖 "C'est à quel nom ?"
👤 "Jean Dupont"
🤖 "Et c'est pour quoi exactement ?"
👤 "Un contrôle"
🤖 "Vous préférez plutôt le matin ou l'après-midi ?"
...
```

### Cas 3 : Question FAQ
```
🤖 "Bonjour Cabinet Dupont, je vous écoute."
👤 "Quels sont vos horaires ?"
🤖 "Nous sommes ouverts du lundi au vendredi de 9h à 18h."
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
