#!/usr/bin/env bash
# Warm-up Railway avant un test d'appel Vapi (évite cold start → HANG).
# Usage: BASE_URL=https://agent-production-c246.up.railway.app ./scripts/warmup_railway.sh
# Puis appelez immédiatement pendant que le serveur est chaud.

set -e
BASE_URL="${BASE_URL:-https://agent-production-c246.up.railway.app}"

echo "Warm-up: $BASE_URL"
curl -s -o /dev/null -w "  /health → %{http_code} (%{time_total}s)\n" "$BASE_URL/health"
echo "→ Serveur chaud. Passez l’appel Vapi (ou lancez curl_vapi_stream.sh) maintenant."
