# Configuration Vapi - Assistant Vocal

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
🤖 "Parfait, bonne journée !"
```

### FLOW C : Annulation (3% des appels)
```
🤖 "Bonjour Cabinet Dupont, vous appelez pour un rendez-vous ?"
👤 "Non, je veux annuler mon rendez-vous"
🤖 "Pas de problème. C'est à quel nom ?"
👤 "Jean Dupont"
🤖 "Vous avez un rendez-vous lundi 27 janvier à 9h. Je l'annule ?"
👤 "Oui"
🤖 "C'est fait, votre rendez-vous est annulé. Bonne journée !"
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
🤖 "Pas de problème. Vous avez une question ou vous souhaitez prendre rendez-vous ?"
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
