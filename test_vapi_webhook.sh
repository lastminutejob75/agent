#!/bin/bash
# Script de test pour le webhook Vapi

echo "🧪 Test du webhook Vapi"
echo "======================="
echo ""

# Vérifier qu'une URL est fournie
if [ -z "$1" ]; then
    echo "📝 Usage: ./test_vapi_webhook.sh https://votre-url.ngrok.io"
    echo ""
    echo "💡 Pour obtenir votre URL ngrok :"
    echo "   1. Dans un terminal, lancez: ngrok http 8000"
    echo "   2. Copiez l'URL HTTPS affichée"
    echo "   3. Relancez ce script avec cette URL"
    exit 1
fi

NGROK_URL="$1"
WEBHOOK_URL="${NGROK_URL}/api/vapi/webhook"

echo "🔍 Test du webhook Vapi..."
echo "   URL: ${WEBHOOK_URL}"
echo ""

# Test 1: Health check d'abord
echo "1️⃣ Vérification du health check..."
health_response=$(curl -s "${NGROK_URL}/api/vapi/health")
if echo "$health_response" | grep -q "ok"; then
    echo "   ✅ Health check OK"
else
    echo "   ❌ Health check échoué"
    echo "   Response: $health_response"
    exit 1
fi

echo ""

# Test 2: Webhook avec message "bonjour"
echo "2️⃣ Test du webhook avec message 'bonjour'..."
webhook_response=$(curl -s -X POST "${WEBHOOK_URL}" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "type": "transcript",
      "content": "bonjour"
    },
    "call": {
      "id": "test_call_123"
    }
  }')

echo "   Response: $webhook_response"
echo ""

# Vérifier que la réponse contient "results"
if echo "$webhook_response" | grep -q "results"; then
    echo "✅ SUCCESS ! Le webhook fonctionne correctement"
    echo ""
    echo "📊 Détails de la réponse :"
    echo "$webhook_response" | python3 -m json.tool 2>/dev/null || echo "$webhook_response"
    exit 0
else
    echo "❌ ERREUR ! Le webhook n'a pas retourné de résultats"
    echo ""
    echo "💡 Vérifications :"
    echo "   1. Le serveur backend est-il démarré ? (make run)"
    echo "   2. ngrok est-il lancé ? (ngrok http 8000)"
    echo "   3. L'URL ngrok est-elle correcte ?"
    exit 1
fi

