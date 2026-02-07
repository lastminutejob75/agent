#!/usr/bin/env bash
# Lance tout : login → link → variables. À exécuter une fois dans ton terminal.
# Usage: ./scripts/railway-setup.sh   ou   bash scripts/railway-setup.sh

set -e
cd "$(dirname "$0")/.."

echo "=== 1/3 Railway login (une page va s'ouvrir dans le navigateur) ==="
npx railway login

echo ""
echo "=== 2/3 Railway link (choisis ton projet puis le service backend) ==="
npx railway link

echo ""
echo "=== 3/3 Variables (LLM Assist) ==="
npx railway variables set "LLM_ASSIST_ENABLED=true"

if [ -f .env ]; then
  ANTHROPIC_KEY=$(grep '^ANTHROPIC_API_KEY=' .env 2>/dev/null | cut -d= -f2- | tr -d '\r')
  if [ -n "$ANTHROPIC_KEY" ]; then
    npx railway variables set "ANTHROPIC_API_KEY=$ANTHROPIC_KEY"
    echo "ANTHROPIC_API_KEY définie depuis .env"
  else
    echo "Pas de ANTHROPIC_API_KEY dans .env — définis-la à la main :"
    echo "  npx railway variables set ANTHROPIC_API_KEY=sk-ant-..."
  fi
else
  echo "Fichier .env absent — définis la clé à la main :"
  echo "  npx railway variables set ANTHROPIC_API_KEY=sk-ant-..."
fi

echo ""
echo "=== Vérification ==="
npx railway variables

echo ""
echo "OK. Redéploie sur Railway (dashboard ou git push) pour prendre en compte les variables."
