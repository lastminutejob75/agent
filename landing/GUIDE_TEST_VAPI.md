# 🎤 Guide de Test - Assistant Vocal Vapi

## ✅ Checklist de Configuration

- [x] Backend tourne (`make run`)
- [x] ngrok tourne (`ngrok http 8000`)
- [x] URL ngrok copiée
- [x] Numéro Twilio importé dans Vapi
- [x] Server URL configuré dans Vapi
- [x] Assistant attaché au numéro
- [x] Save cliqué
- [x] Test webhook curl OK
- [x] Prêt pour appel !

---

## 🧪 Tests Locaux (Avant Appel Réel)

### 1. Vérifier que le backend tourne

```bash
curl http://localhost:8000/health
```

**Réponse attendue :**
```json
{
  "status": "ok",
  "streams": 0,
  "free_slots": 10
}
```

### 2. Tester l'endpoint Vapi Health

```bash
curl http://localhost:8000/api/vapi/health
```

**Réponse attendue :**
```json
{
  "status": "ok",
  "service": "vapi",
  "message": "Vapi webhook is ready"
}
```

### 3. Tester l'endpoint Vapi Test

```bash
curl http://localhost:8000/api/vapi/test
```

**Réponse attendue :**
```json
{
  "status": "ok",
  "test_response": "Bonjour ! Comment puis-je vous aider ?",
  "message": "Vapi backend is working correctly"
}
```

### 4. Tester le webhook avec ngrok

**Remplacer `YOUR_NGROK_URL` par votre URL ngrok :**

```bash
./test_vapi_complete.sh https://YOUR_NGROK_URL.ngrok-free.app
```

Ou manuellement :

```bash
# Test message initial
curl -X POST https://YOUR_NGROK_URL.ngrok-free.app/api/vapi/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "type": "user-message",
      "content": "bonjour"
    },
    "call": {
      "id": "test_call_001"
    }
  }'
```

**Réponse attendue :**
```json
{
  "results": [
    {
      "type": "say",
      "text": "Bonjour ! Comment puis-je vous aider ?"
    }
  ]
}
```

---

## 📞 Test avec Appel Réel

### Scénario 1 : Demande de RDV Simple

1. **Appelez le numéro Twilio configuré dans Vapi**
2. **Dites :** "Bonjour, je voudrais prendre un rendez-vous"
3. **L'assistant devrait :**
   - Répondre en français
   - Demander votre nom et prénom
   - Demander le motif
   - Demander votre préférence de créneau
   - Demander votre contact (email ou téléphone)
   - Proposer 3 créneaux
   - Attendre votre confirmation : "un", "deux" ou "trois"

### Scénario 2 : Confirmation Vocale

1. **Après avoir reçu les 3 créneaux**
2. **Dites :** "deux" ou "oui deux" ou "le deuxième"
3. **L'assistant devrait :**
   - Confirmer le créneau sélectionné
   - Terminer la conversation

### Scénario 3 : Email Dicté

1. **Quand l'assistant demande votre contact**
2. **Dites :** "jean point dupont arobase gmail point com"
3. **L'assistant devrait :**
   - Parser automatiquement : `jean.dupont@gmail.com`
   - Continuer avec la proposition de créneaux

### Scénario 4 : FAQ

1. **Dites :** "Quels sont vos horaires ?"
2. **L'assistant devrait :**
   - Répondre avec la FAQ correspondante
   - Ajouter "Source : FAQ_HORAIRES" (ou l'ID de la FAQ)

---

## 🔍 Format Payload Vapi

Vapi envoie des payloads au format suivant :

```json
{
  "message": {
    "type": "user-message",  // ou "speech-update", "function-call-result", "hang"
    "content": "transcript de l'utilisateur"
  },
  "call": {
    "id": "unique_call_id"
  }
}
```

**Types de messages ignorés :**
- `speech-update` : Mises à jour de transcription (ignoré)
- `function-call-result` : Résultats de fonctions (ignoré)
- `hang` : Fin d'appel (ignoré)

**Type traité :**
- `user-message` : Message utilisateur final (traité)

---

## 📤 Format Réponse Vapi

Le webhook doit retourner :

```json
{
  "results": [
    {
      "type": "say",
      "text": "Réponse de l'assistant"
    }
  ]
}
```

**En cas d'erreur :**
```json
{
  "results": [
    {
      "type": "say",
      "text": "Désolé, une erreur s'est produite. Je vous transfère."
    }
  ]
}
```

---

## 🐛 Debugging

### Vérifier les logs du backend

```bash
# Les logs devraient afficher :
# - "Vapi webhook received: {payload}"
# - "Processing call_id=..., transcript='...'"
# - "Responding to Vapi: ..."
```

### Vérifier les logs ngrok

```bash
# Dans le terminal ngrok, vous verrez les requêtes HTTP
```

### Vérifier les logs Vapi

- Allez dans le dashboard Vapi
- Ouvrez les logs de l'appel
- Vérifiez les requêtes webhook et les réponses

---

## ⚠️ Problèmes Courants

### 1. "Backend non accessible"

**Solution :**
```bash
# Vérifier que le backend tourne
make run

# Vérifier le port
lsof -i :8000
```

### 2. "ngrok ERR_NGROK_105" (authentication failed)

**Solution :**
```bash
# Configurer l'authtoken ngrok
ngrok config add-authtoken YOUR_AUTHTOKEN
```

### 3. "Webhook timeout" dans Vapi

**Solution :**
- Vérifier que ngrok expose bien le port 8000
- Vérifier que l'URL dans Vapi est correcte (avec `/api/vapi/webhook`)
- Vérifier que le backend répond rapidement (< 3s)

### 4. "Réponse vide" de l'assistant

**Solution :**
- Vérifier les logs du backend
- Vérifier que la DB contient des slots disponibles
- Vérifier que la DB contient des FAQ

---

## 📊 Métriques de Succès

- ✅ Réponse en < 3 secondes
- ✅ Transcription correcte (Vapi)
- ✅ Parsing vocal correct (un/deux/trois)
- ✅ Email dicté parsé correctement
- ✅ Confirmation de RDV réussie
- ✅ Pas d'erreurs dans les logs

---

## 🚀 Prochaines Étapes

1. **Tester tous les scénarios** ci-dessus
2. **Vérifier les logs** pour chaque appel
3. **Ajuster les prompts** si nécessaire
4. **Améliorer le parsing vocal** si besoin
5. **Ajouter plus de tests** pour edge cases

---

## 📝 Notes

- Le `call_id` de Vapi est utilisé comme `conversation_id` dans le backend
- Chaque appel = nouvelle session (TTL 15 minutes)
- Les messages vocaux sont traités avec `channel="vocal"`
- Les instructions sont adaptées au canal vocal (ex: "Dites un, deux ou trois")

---

**Bon test ! 🎤**
