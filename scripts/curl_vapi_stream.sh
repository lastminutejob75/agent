#!/usr/bin/env bash
# Test anti-régression : stream=true → SSE (Content-Type text/event-stream + data: ... + data: [DONE]).
# À lancer après deploy (prod/staging) pour vérifier qu'aucun chemin ne renvoie du JSON.
#
# Usage:
#   ./scripts/curl_vapi_stream.sh
#   BASE_URL=https://agent-production-xxx.up.railway.app ./scripts/curl_vapi_stream.sh

set -e
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
URL="${BASE_URL}/api/vapi/chat/completions"

echo "=== Vapi chat/completions stream=true → doit renvoyer SSE ==="
echo "URL: $URL"
echo ""

curl -iN -sS "$URL" \
  -H "Content-Type: application/json" \
  -d '{
    "stream": true,
    "messages": [{"role": "user", "content": "TEST AUDIO 123"}]
  }' | head -80

echo ""
echo "--- Vérifications attendues ---"
echo "  - HTTP/1.1 200"
echo "  - Content-Type: text/event-stream"
echo "  - Lignes data: {...}"
echo "  - Dernière ligne: data: [DONE]"
