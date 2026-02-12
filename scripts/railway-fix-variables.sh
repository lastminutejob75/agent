#!/bin/bash
# Réapplique les variables TWILIO et SMTP sur Railway
# Usage: ./scripts/railway-fix-variables.sh
# Prérequis: railway link (service backend), .env avec les valeurs
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "⚠️  Fichier .env absent. Crée-le ou exécute manuellement :"
  echo ""
  echo "  npx railway variables set TWILIO_ACCOUNT_SID=ACxxxx"
  echo "  npx railway variables set TWILIO_AUTH_TOKEN=xxxx"
  echo "  npx railway variables set TWILIO_PHONE_NUMBER=+33xxxxxxxxx"
  echo "  npx railway variables set SMTP_HOST=smtp.gmail.com"
  echo "  npx railway variables set SMTP_PORT=587"
  echo "  npx railway variables set SMTP_EMAIL=ton@email.com"
  echo "  npx railway variables set SMTP_PASSWORD=ton_mot_de_passe_app"
  echo ""
  echo "Voir: docs/RAILWAY_FIX_VARIABLES_INACTIVES.md"
  exit 1
fi

echo "🔄 Chargement .env et application sur Railway..."
cd "$REPO_ROOT"
set -a
source .env
set +a

vars_set=0
for key in TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_PHONE_NUMBER SMTP_HOST SMTP_PORT SMTP_EMAIL SMTP_PASSWORD; do
  val="${!key}"
  if [ -n "$val" ]; then
    npx --yes @railway/cli variable set "$key=$val" 2>/dev/null && echo "  ✓ $key" && vars_set=$((vars_set + 1))
  fi
done

if [ "$vars_set" -eq 0 ]; then
  echo "⚠️  Aucune variable trouvée dans .env. Vérifie TWILIO_* et SMTP_*"
  exit 1
fi

echo ""
echo "✅ $vars_set variables appliquées. Redéploie : npx railway up"
echo "   Ou : git commit --allow-empty -m 'redeploy' && git push"
