#!/bin/bash
# Tests E2E Stripe — exécuter avec ADMIN_API_TOKEN et TENANT_ID depuis Railway
# Usage: ADMIN_API_TOKEN=xxx TENANT_ID=1 ./scripts/run-stripe-e2e-tests.sh

set -e
BASE_URL="${STRIPE_E2E_BASE_URL:-https://agent-production-c246.up.railway.app}"
TENANT_ID="${TENANT_ID:-1}"
TOKEN="${ADMIN_API_TOKEN}"

if [ -z "$TOKEN" ]; then
  echo "❌ ADMIN_API_TOKEN requis. Exemple:"
  echo "   ADMIN_API_TOKEN=ton_token TENANT_ID=1 $0"
  exit 1
fi

echo "=== TEST 1 — Checkout Growth ==="
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/admin/tenants/$TENANT_ID/stripe-checkout" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plan_key":"growth"}')
HTTP_CODE=$(echo "$RESP" | tail -n1)
BODY=$(echo "$RESP" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ HTTP 200"
  CHECKOUT_URL=$(echo "$BODY" | grep -o '"checkout_url":"[^"]*"' | cut -d'"' -f4)
  if [ -n "$CHECKOUT_URL" ]; then
    echo "✅ checkout_url: $CHECKOUT_URL"
    echo ""
    echo "→ Ouvre cette URL pour vérifier les 2 lignes Stripe (149€ + Metered) et compléter le paiement."
  else
    echo "❌ checkout_url non trouvé dans la réponse"
  fi
else
  echo "❌ HTTP $HTTP_CODE"
  echo "$BODY"
fi

echo ""
echo "=== TEST 2 — Vérifier tenant_billing (Postgres) ==="
echo "Exécute manuellement après paiement:"
echo "  SELECT tenant_id, plan_key, stripe_subscription_id, stripe_metered_item_id"
echo "  FROM tenant_billing WHERE tenant_id='$TENANT_ID';"
echo ""

echo "=== TEST 3 — Push usage ==="
RESP2=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/admin/jobs/push-daily-usage" \
  -H "Authorization: Bearer $TOKEN")
HTTP_CODE2=$(echo "$RESP2" | tail -n1)
BODY2=$(echo "$RESP2" | sed '$d')

if [ "$HTTP_CODE2" = "200" ]; then
  echo "✅ HTTP 200"
  echo "$BODY2"
else
  echo "❌ HTTP $HTTP_CODE2"
  echo "$BODY2"
fi

echo ""
echo "=== Fin des tests ==="
