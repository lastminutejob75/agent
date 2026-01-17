# Intégration Vapi avec Next.js sur Vercel

## 📋 Structure

```
app/
  api/
    health/
      route.ts          # GET /api/health
    vapi/
      health/
        route.ts        # GET /api/vapi/health
      test/
        route.ts        # GET /api/vapi/test
      webhook/
        route.ts        # POST /api/vapi/webhook
lib/
  vapi.ts               # Utilitaires Vapi (parse, build, handle)
```

## 🚀 Installation

```bash
# Installer les dépendances Next.js
npm install next@14 react@18 react-dom@18 uuid @types/uuid typescript

# Ou utiliser package-nextjs.json
cp package-nextjs.json package.json
npm install
```

## ⚙️ Configuration

### Variables d'environnement

Créer `.env.local` :

```bash
# Mode de réponse Vapi
VAPI_MODE=simple  # ou "tool"
```

### Modes Vapi

**MODE simple** (par défaut) :
```json
{
  "say": "Bonjour. Souhaitez-vous prendre un rendez-vous ?",
  "text": "Bonjour. Souhaitez-vous prendre un rendez-vous ?",
  "endCall": false
}
```

**MODE tool** :
```json
{
  "say": "Bonjour. Souhaitez-vous prendre un rendez-vous ?",
  "text": "Bonjour. Souhaitez-vous prendre un rendez-vous ?",
  "endCall": false,
  "data": {
    "action": "say",
    "confidence": 1.0
  }
}
```

## 🧪 Tests Manuels

### 1. Health Check
```bash
curl http://localhost:3000/api/vapi/health
```

### 2. Test Endpoint
```bash
curl http://localhost:3000/api/vapi/test
```

### 3. Webhook Test
```bash
curl -X POST "http://localhost:3000/api/vapi/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "type": "user-message",
      "content": "Je veux un rendez-vous"
    },
    "call": {
      "id": "test_call_123",
      "from": "+33123456789"
    }
  }'
```

## 📞 Configuration Vapi

Dans votre dashboard Vapi :

**Server URL :**
```
https://votre-projet.vercel.app/api/vapi/webhook
```

**Méthode :** `POST`

**Headers :**
```
Content-Type: application/json
```

## 🔍 Logs

Les logs incluent :
- `request_id` : UUID unique par requête
- `callId` : ID de l'appel Vapi
- `inputText` : Texte utilisateur (tronqué à 100 chars)
- `duration_ms` : Durée totale de la requête
- `handler_ms` : Durée du traitement

Exemple :
```
[abc123] Vapi webhook received { callId: 'call_123', messageType: 'user-message' }
[abc123] Parsed payload { callId: 'call_123', inputText: 'Je veux un rendez-vous' }
[abc123] Response sent { action: 'say', duration_ms: 45, handler_ms: 12 }
```

## ⚡ Performance

- **Timeout soft** : Si `handleVapiTurn` prend > 800ms, retourne transfert
- **Réponses < 1 seconde** : Objectif atteint avec logique simple
- **Pas de SSE** : Endpoints HTTP courts uniquement

## 🎯 Logique V1 (Vocal)

L'assistant gère :
- **Input vide** → "Je n'ai pas bien entendu. Pouvez-vous répéter ?"
- **Intent RDV** (rdv, rendez-vous, disponible, créneau) → Question qualification (nom/prénom)
- **Hors scope** (prix, conseils médicaux, symptômes) → Transfert humain
- **Par défaut** → Question de clarification

Réponses en vouvoiement, courtes, sans emojis.

## 🚀 Déploiement Vercel

1. **Push sur GitHub** (déjà fait)
2. **Vercel détecte automatiquement** Next.js
3. **Variables d'environnement** :
   - Dans Vercel Dashboard → Settings → Environment Variables
   - Ajouter `VAPI_MODE=simple` (ou `tool`)

4. **URL obtenue** :
   ```
   https://votre-projet.vercel.app/api/vapi/webhook
   ```

## 📊 Endpoints Disponibles

- `GET /api/health` - Health check général
- `GET /api/vapi/health` - Health check Vapi
- `GET /api/vapi/test` - Exemples payload/réponse
- `POST /api/vapi/webhook` - Webhook principal Vapi

## ✅ Checklist

- [x] Structure Next.js App Router
- [x] Endpoints `/app/api/vapi/*`
- [x] Logique `handleVapiTurn()` dans `/lib/vapi.ts`
- [x] Support 2 modes (simple/tool) via `VAPI_MODE`
- [x] Logs avec `request_id`
- [x] Timeout soft (800ms)
- [x] Tests manuels documentés
- [x] Réponses < 1 seconde
- [x] Pas de SSE (HTTP court uniquement)
