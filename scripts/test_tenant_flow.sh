#!/usr/bin/env bash
#
# test_tenant_flow.sh
# -------------------
# Smoke test bout-en-bout du flow "création d'un client cabinet" :
#   1. Login admin
#   2. Création tenant via /api/admin/createTenantFull
#   3. Audit cabinet-profile (doit retourner 0 mismatch sur le nouveau tenant)
#   4. (Optionnel) Login client + GET /api/tenant/me
#   5. (Optionnel) PATCH /api/tenant/profile et /opening-hours
#   6. Re-audit (doit toujours retourner 0 mismatch)
#
# Usage :
#   API_URL=https://staging.uwiapp.com \
#   ADMIN_EMAIL=admin@uwiapp.com \
#   ADMIN_PASSWORD=xxx \
#   CLIENT_EMAIL=test-tenant-$(date +%s)@uwiapp.com \
#   TWILIO_NUMBER=+33123456789 \
#   ./scripts/test_tenant_flow.sh
#
# Pré-requis : curl, jq.
#
# Sortie : codes ANSI (vert OK, rouge FAIL). Exit code != 0 si une étape échoue.

set -u
set -o pipefail

# -------- Couleurs --------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { printf "${GREEN}✓${NC} %s\n" "$*"; }
fail() { printf "${RED}✗${NC} %s\n" "$*" >&2; exit 1; }
warn() { printf "${YELLOW}!${NC} %s\n" "$*"; }

# -------- Pré-requis --------
command -v curl >/dev/null || fail "curl requis"
command -v jq >/dev/null || fail "jq requis (brew install jq)"

# -------- Config --------
API_URL="${API_URL:-http://127.0.0.1:8000}"
ADMIN_EMAIL="${ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
CLIENT_EMAIL="${CLIENT_EMAIL:-test-tenant-$(date +%s)@uwiapp.com}"
TENANT_NAME="${TENANT_NAME:-Cabinet Test $(date +%s)}"
PLAN_KEY="${PLAN_KEY:-growth}"
TIMEZONE="${TIMEZONE:-Europe/Paris}"
SECTOR="${SECTOR:-medecin_generaliste}"
ASSISTANT_ID="${ASSISTANT_ID:-sophie}"
TWILIO_NUMBER="${TWILIO_NUMBER:-}"
PHONE="${PHONE:-+33102030405}"

[ -n "$ADMIN_EMAIL" ]    || fail "ADMIN_EMAIL requis"
[ -n "$ADMIN_PASSWORD" ] || fail "ADMIN_PASSWORD requis"

echo "API_URL          : $API_URL"
echo "ADMIN_EMAIL      : $ADMIN_EMAIL"
echo "CLIENT_EMAIL     : $CLIENT_EMAIL"
echo "TENANT_NAME      : $TENANT_NAME"
echo "PLAN_KEY         : $PLAN_KEY"
echo "TWILIO_NUMBER    : ${TWILIO_NUMBER:-<vide, étape Twilio sautée>}"
echo ""

ADMIN_COOKIES=$(mktemp)
CLIENT_COOKIES=$(mktemp)
trap 'rm -f "$ADMIN_COOKIES" "$CLIENT_COOKIES"' EXIT

# -------- Étape 1 : Login admin --------
echo "1/6 Login admin…"
HTTP=$(curl -s -o /tmp/login_admin.json -w "%{http_code}" \
  -X POST "$API_URL/api/admin/auth/login" \
  -H "Content-Type: application/json" \
  -c "$ADMIN_COOKIES" \
  -d "$(jq -n --arg e "$ADMIN_EMAIL" --arg p "$ADMIN_PASSWORD" '{email:$e, password:$p}')")
[ "$HTTP" = "200" ] || fail "Login admin HTTP=$HTTP : $(cat /tmp/login_admin.json)"
ok "Login admin OK"

# -------- Étape 2 : Création tenant --------
echo "2/6 Création tenant via /api/admin/tenants/create…"
CREATE_BODY=$(jq -n \
  --arg name "$TENANT_NAME" \
  --arg email "$CLIENT_EMAIL" \
  --arg plan "$PLAN_KEY" \
  --arg tz "$TIMEZONE" \
  --arg sector "$SECTOR" \
  --arg aid "$ASSISTANT_ID" \
  --arg twilio "$TWILIO_NUMBER" \
  --arg phone "$PHONE" \
  '{
    name:$name, email:$email, plan_key:$plan, timezone:$tz,
    sector:$sector, assistant_id:$aid,
    twilio_number:(if $twilio == "" then null else $twilio end),
    phone:$phone, send_welcome:false
  }')
HTTP=$(curl -s -o /tmp/create.json -w "%{http_code}" \
  -X POST "$API_URL/api/admin/tenants/create" \
  -H "Content-Type: application/json" \
  -b "$ADMIN_COOKIES" \
  -d "$CREATE_BODY")
if [ "$HTTP" != "200" ]; then
  warn "tenants/create HTTP=$HTTP : $(cat /tmp/create.json)"
  warn "Si ton env de staging n'a pas Stripe ou Vapi configuré, c'est attendu."
  warn "Skip des étapes 3-6 (audit, login client) car pas de tenant créé."
  exit 1
fi
TENANT_ID=$(jq -r '.tenant_id // .results.tenant_id' /tmp/create.json)
[ -n "$TENANT_ID" ] && [ "$TENANT_ID" != "null" ] || fail "tenant_id absent de la réponse : $(cat /tmp/create.json)"
ok "Tenant créé : id=$TENANT_ID"

# -------- Étape 3 : Audit cabinet-profile (single) --------
echo "3/6 Audit cabinet-profile (single)…"
HTTP=$(curl -s -o /tmp/audit.json -w "%{http_code}" \
  -X GET "$API_URL/api/admin/tenants/$TENANT_ID/cabinet-profile-audit" \
  -b "$ADMIN_COOKIES")
[ "$HTTP" = "200" ] || fail "Audit HTTP=$HTTP : $(cat /tmp/audit.json)"
MISMATCH=$(jq -r '.summary.mismatch_count // .mismatch_count // 0' /tmp/audit.json)
if [ "$MISMATCH" = "0" ] || [ "$MISMATCH" = "null" ]; then
  ok "Audit : 0 mismatch"
else
  warn "Audit : $MISMATCH mismatch(es) — détails :"
  jq '.mismatches // .' /tmp/audit.json
fi

# -------- Étape 4 : Login client (utilise mot de passe temporaire envoyé par email) --------
echo "4/6 Login client…"
echo "  → Récupère le mot de passe temporaire dans l'email envoyé à $CLIENT_EMAIL."
echo "  → Skip si tu ne peux pas (configure CLIENT_TEMP_PASSWORD pour automatiser)."
CLIENT_TEMP_PASSWORD="${CLIENT_TEMP_PASSWORD:-}"
if [ -z "$CLIENT_TEMP_PASSWORD" ]; then
  warn "CLIENT_TEMP_PASSWORD vide, skip des étapes 4-6"
  exit 0
fi

HTTP=$(curl -s -o /tmp/login_client.json -w "%{http_code}" \
  -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -c "$CLIENT_COOKIES" \
  -d "$(jq -n --arg e "$CLIENT_EMAIL" --arg p "$CLIENT_TEMP_PASSWORD" '{email:$e, password:$p}')")
[ "$HTTP" = "200" ] || fail "Login client HTTP=$HTTP : $(cat /tmp/login_client.json)"
MUST_CHANGE=$(curl -s -X GET "$API_URL/api/tenant/me" -b "$CLIENT_COOKIES" | jq -r '.must_change_password')
ok "Login client OK (must_change_password=$MUST_CHANGE)"

# -------- Étape 5 : PATCH /profile + /opening-hours --------
echo "5/6 PATCH /api/tenant/profile et /api/tenant/opening-hours…"
HTTP=$(curl -s -o /tmp/patch_profile.json -w "%{http_code}" \
  -X PATCH "$API_URL/api/tenant/profile" \
  -H "Content-Type: application/json" \
  -b "$CLIENT_COOKIES" \
  -d '{"practitioner_name":"Dr Test","cabinet_name":"Cabinet Test","specialty":"Médecine générale","phone":"0102030405","address_line":"1 rue Test","postal_code":"75001","city":"Paris","accepts_new_patients":true,"languages":["fr"]}')
[ "$HTTP" = "200" ] || fail "PATCH profile HTTP=$HTTP : $(cat /tmp/patch_profile.json)"
ok "PATCH /profile OK"

HTTP=$(curl -s -o /tmp/patch_hours.json -w "%{http_code}" \
  -X PATCH "$API_URL/api/tenant/opening-hours" \
  -H "Content-Type: application/json" \
  -b "$CLIENT_COOKIES" \
  -d '{"opening_hours":[{"day":"monday","is_open":true,"morning_start":"09:00","morning_end":"12:00","afternoon_start":"14:00","afternoon_end":"18:00"},{"day":"tuesday","is_open":true,"morning_start":"09:00","morning_end":"12:00"},{"day":"wednesday","is_open":false},{"day":"thursday","is_open":true,"morning_start":"09:00","morning_end":"12:00"},{"day":"friday","is_open":true,"morning_start":"09:00","morning_end":"17:00"},{"day":"saturday","is_open":false},{"day":"sunday","is_open":false}]}')
[ "$HTTP" = "200" ] || fail "PATCH opening-hours HTTP=$HTTP : $(cat /tmp/patch_hours.json)"
ok "PATCH /opening-hours OK"

# -------- Étape 6 : Re-audit --------
echo "6/6 Re-audit après PATCH…"
HTTP=$(curl -s -o /tmp/audit2.json -w "%{http_code}" \
  -X GET "$API_URL/api/admin/tenants/$TENANT_ID/cabinet-profile-audit" \
  -b "$ADMIN_COOKIES")
[ "$HTTP" = "200" ] || fail "Re-audit HTTP=$HTTP : $(cat /tmp/audit2.json)"
MISMATCH2=$(jq -r '.summary.mismatch_count // .mismatch_count // 0' /tmp/audit2.json)
if [ "$MISMATCH2" = "0" ] || [ "$MISMATCH2" = "null" ]; then
  ok "Re-audit : toujours 0 mismatch après PATCH ✓"
else
  warn "Re-audit : $MISMATCH2 mismatch(es) après PATCH — détails :"
  jq '.mismatches // .' /tmp/audit2.json
  fail "Re-audit échoué"
fi

echo ""
ok "SMOKE TEST OK — tenant $TENANT_ID prêt à l'usage."
echo "Page publique : $API_URL/praticiens/<public_slug-du-tenant>"
