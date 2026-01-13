#!/bin/bash
# Script de test pour vérifier que ngrok expose bien le backend

echo "🧪 Test de l'exposition ngrok"
echo "=============================="
echo ""

# Vérifier que ngrok est installé
if ! command -v ngrok &> /dev/null; then
    echo "❌ ngrok n'est pas installé"
    echo "   Installez-le depuis https://ngrok.com/download"
    exit 1
fi

# Demander l'URL ngrok
if [ -z "$1" ]; then
    echo "📝 Usage: ./test_ngrok.sh https://votre-url.ngrok.io"
    echo ""
    echo "💡 Pour obtenir votre URL ngrok :"
    echo "   1. Dans un terminal, lancez: ngrok http 8000"
    echo "   2. Copiez l'URL HTTPS affichée"
    echo "   3. Relancez ce script avec cette URL"
    exit 1
fi

NGROK_URL="$1"

echo "🔍 Test de l'endpoint health check..."
echo "   URL: ${NGROK_URL}/api/vapi/health"
echo ""

response=$(curl -s -w "\n%{http_code}" "${NGROK_URL}/api/vapi/health")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

echo "📊 Résultat :"
echo "   Status HTTP: $http_code"
echo "   Response: $body"
echo ""

if [ "$http_code" = "200" ]; then
    echo "✅ SUCCESS ! ngrok expose correctement votre backend"
    echo ""
    echo "🎯 Vous pouvez maintenant utiliser cette URL dans Vapi :"
    echo "   ${NGROK_URL}/api/vapi/webhook"
    exit 0
else
    echo "❌ ERREUR ! Le backend n'est pas accessible via ngrok"
    echo ""
    echo "💡 Vérifications :"
    echo "   1. Le serveur backend est-il démarré ? (make run)"
    echo "   2. ngrok est-il lancé ? (ngrok http 8000)"
    echo "   3. L'URL ngrok est-elle correcte ?"
    exit 1
fi

