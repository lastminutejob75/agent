#!/bin/bash
# Test complet du webhook Vapi
# Usage: ./test_vapi_complete.sh [ngrok_url]

set -e

NGROK_URL="${1:-http://localhost:8000}"
VAPI_WEBHOOK_URL="${NGROK_URL}/api/vapi/webhook"

echo "🧪 TEST COMPLET WEBHOOK VAPI"
echo "=============================="
echo "URL: $VAPI_WEBHOOK_URL"
echo ""

# Test 1: Health check
echo "✅ Test 1: Health check"
curl -s "${NGROK_URL}/api/vapi/health" | python3 -m json.tool
echo ""

# Test 2: Test endpoint
echo "✅ Test 2: Test endpoint"
curl -s "${NGROK_URL}/api/vapi/test" | python3 -m json.tool
echo ""

# Test 3: Webhook - Message initial (bonjour)
echo "✅ Test 3: Webhook - Message initial"
PAYLOAD1='{
  "message": {
    "type": "user-message",
    "content": "bonjour"
  },
  "call": {
    "id": "test_call_001"
  }
}'

echo "Payload: $PAYLOAD1"
echo "Réponse:"
curl -s -X POST "$VAPI_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD1" | python3 -m json.tool
echo ""

# Test 4: Webhook - Demande de RDV
echo "✅ Test 4: Webhook - Demande de RDV"
PAYLOAD2='{
  "message": {
    "type": "user-message",
    "content": "je veux prendre un rendez-vous"
  },
  "call": {
    "id": "test_call_001"
  }
}'

echo "Payload: $PAYLOAD2"
echo "Réponse:"
curl -s -X POST "$VAPI_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD2" | python3 -m json.tool
echo ""

# Test 5: Webhook - Nom (qualification)
echo "✅ Test 5: Webhook - Nom"
PAYLOAD3='{
  "message": {
    "type": "user-message",
    "content": "Jean Dupont"
  },
  "call": {
    "id": "test_call_001"
  }
}'

echo "Payload: $PAYLOAD3"
echo "Réponse:"
curl -s -X POST "$VAPI_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD3" | python3 -m json.tool
echo ""

# Test 6: Webhook - Confirmation vocale (un/deux/trois)
echo "✅ Test 6: Webhook - Confirmation vocale 'deux'"
PAYLOAD4='{
  "message": {
    "type": "user-message",
    "content": "deux"
  },
  "call": {
    "id": "test_call_001"
  }
}'

echo "Payload: $PAYLOAD4"
echo "Réponse:"
curl -s -X POST "$VAPI_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD4" | python3 -m json.tool
echo ""

# Test 7: Webhook - Email dicté
echo "✅ Test 7: Webhook - Email dicté"
PAYLOAD5='{
  "message": {
    "type": "user-message",
    "content": "jean point dupont arobase gmail point com"
  },
  "call": {
    "id": "test_call_002"
  }
}'

echo "Payload: $PAYLOAD5"
echo "Réponse:"
curl -s -X POST "$VAPI_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD5" | python3 -m json.tool
echo ""

# Test 8: Webhook - Events techniques (ignorés)
echo "✅ Test 8: Webhook - Event technique (doit être ignoré)"
PAYLOAD6='{
  "message": {
    "type": "speech-update",
    "content": "test"
  },
  "call": {
    "id": "test_call_003"
  }
}'

echo "Payload: $PAYLOAD6"
echo "Réponse (doit être ignoré):"
curl -s -X POST "$VAPI_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD6" | python3 -m json.tool
echo ""

echo "✅ Tests terminés !"
echo ""
echo "📞 Pour tester avec un vrai appel :"
echo "1. Vérifiez que ngrok expose bien : $NGROK_URL"
echo "2. Configurez cette URL dans Vapi comme Server URL"
echo "3. Appelez le numéro Twilio configuré dans Vapi"
echo "4. Parlez à l'assistant vocal !"
