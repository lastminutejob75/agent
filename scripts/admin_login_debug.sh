#!/usr/bin/env bash
# Test admin login sans passer par le front (isoler env vars / backend).
# Usage:
#   API_URL=https://ton-backend.railway.app ./scripts/admin_login_debug.sh
#   API_URL=https://... ADMIN_EMAIL=ton@email.com ADMIN_PASSWORD=tonmdp ./scripts/admin_login_debug.sh
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  set +a
fi
BASE="${API_URL:-${VITE_UWI_API_BASE_URL}}"
BASE="${BASE%/}"
if [ -z "$BASE" ]; then
  echo "Définir API_URL ou VITE_UWI_API_BASE_URL (ex. https://agent-production-c246.up.railway.app)"
  exit 1
fi

echo "=== 1) GET /api/admin/auth/status (direct Railway) ==="
STATUS=$(curl -s "$BASE/api/admin/auth/status" || true)
echo "$STATUS" | python3 -m json.tool 2>/dev/null || echo "$STATUS"
echo ""

if [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
  echo "=== 2) POST /api/admin/auth/login (email + mot de passe depuis env) ==="
  curl -s -i -X POST "$BASE/api/admin/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}"
  echo ""
else
  echo "=== 2) POST /api/admin/auth/login (à lancer à la main avec ton email/mdp) ==="
  echo "  curl -i -X POST $BASE/api/admin/auth/login \\"
  echo "    -H 'Content-Type: application/json' \\"
  echo "    -d '{\"email\":\"TON_EMAIL\",\"password\":\"TON_MDP\"}'"
  echo ""
  echo "Pour utiliser ce script avec email/mdp :"
  echo "  ADMIN_EMAIL=ton@email.com ADMIN_PASSWORD=tonmdp $0"
fi
