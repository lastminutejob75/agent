#!/bin/bash
# Script de test du webhook via ngrok avec vérifications

echo "🧪 Test du webhook via ngrok"
echo "============================"
echo ""

# Vérifier qu'une URL est fournie
if [ -z "$1" ]; then
    echo "❌ Usage: ./test_ngrok_webhook.sh https://votre-url.ngrok.io"
    echo ""
    echo "💡 Pour obtenir votre URL ngrok :"
    echo "   1. Dans Terminal 2, lancez: ngrok http 8000"
    echo "   2. Copiez l'URL HTTPS affichée (ex: https://abc123xyz.ngrok.io)"
    echo "   3. Relancez ce script avec cette URL"
    exit 1
fi

NGROK_URL="$1"
WEBHOOK_URL="${NGROK_URL}/api/vapi/webhook"

echo "🔍 Vérifications préalables..."
echo ""

# Test 1: Backend local
echo "1️⃣ Test backend local..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✅ Backend local fonctionne"
else
    echo "   ❌ Backend local ne répond pas"
    echo "   → Démarrez avec: make run"
    exit 1
fi

# Test 2: Health check via ngrok
echo ""
echo "2️⃣ Test health check via ngrok..."
health_response=$(curl -s -w "\n%{http_code}" "${NGROK_URL}/api/vapi/health" 2>&1)
http_code=$(echo "$health_response" | tail -n1)
body=$(echo "$health_response" | sed '$d')

if [ "$http_code" = "200" ]; then
    echo "   ✅ Health check OK (status: $http_code)"
    echo "   Response: $body"
else
    echo "   ❌ Health check échoué (status: $http_code)"
    echo "   Response: $body"
    echo ""
    echo "💡 Vérifications :"
    echo "   - ngrok est-il lancé ? (ngrok http 8000)"
    echo "   - L'URL ngrok est-elle correcte ?"
    exit 1
fi

# Test 3: Webhook
echo ""
echo "3️⃣ Test du webhook..."
webhook_response=$(curl -s -w "\n%{http_code}" -X POST "${WEBHOOK_URL}" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "type": "transcript",
      "content": "bonjour"
    },
    "call": {
      "id": "test_call_123"
    }
  }' 2>&1)

http_code=$(echo "$webhook_response" | tail -n1)
body=$(echo "$webhook_response" | sed '$d')

echo "   Status HTTP: $http_code"
echo "   Response: $body"
echo ""

if [ "$http_code" = "200" ] && echo "$body" | grep -q "results"; then
    echo "✅ SUCCESS ! Le webhook fonctionne via ngrok"
    echo ""
    echo "📊 Détails de la réponse :"
    echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
    echo ""
    echo "🎯 Vous pouvez maintenant utiliser cette URL dans Vapi :"
    echo "   ${WEBHOOK_URL}"
    exit 0
else
    echo "❌ ERREUR ! Le webhook n'a pas retourné de résultats"
    echo ""
    echo "💡 Vérifications :"
    echo "   1. Le serveur backend est-il démarré ? (make run)"
    echo "   2. ngrok est-il lancé ? (ngrok http 8000)"
    echo "   3. L'URL ngrok est-elle correcte ?"
    echo "   4. Vérifiez les logs dans Terminal 1 (backend) et Terminal 2 (ngrok)"
    exit 1
fi

