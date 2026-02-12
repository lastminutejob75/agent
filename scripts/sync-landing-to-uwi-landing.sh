#!/bin/bash
# Sync landing/ vers uwi-landing (pour uwiapp.com)
# Usage: ./scripts/sync-landing-to-uwi-landing.sh
# À lancer après push sur agent si uwiapp.com déploie encore depuis uwi-landing.
set -e

REPO_AGENT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_LANDING="${REPO_LANDING:-$REPO_AGENT/uwi-landing}"
LANDING_URL="https://github.com/lastminutejob75/uwi-landing.git"

echo "🔄 Sync landing/ → uwi-landing"
echo "   Source: $REPO_AGENT/landing"
echo "   Target: $REPO_LANDING"
echo ""

# Cloner ou mettre à jour uwi-landing
if [ ! -d "$REPO_LANDING" ]; then
  echo "📥 Clonage uwi-landing..."
  git clone "$LANDING_URL" "$REPO_LANDING"
  cd "$REPO_LANDING"
else
  cd "$REPO_LANDING"
  git fetch origin
  git checkout main
  git pull origin main || true
fi

# Copier landing/ (exclure node_modules, .git, dist)
echo "📂 Copie landing/..."
rsync -av --delete \
  --exclude 'node_modules' \
  --exclude '.git' \
  --exclude 'dist' \
  --exclude '.env' \
  --exclude '*.log' \
  "$REPO_AGENT/landing/" "$REPO_LANDING/"

# Commit si changements
if git diff --quiet && git diff --staged --quiet; then
  echo "✅ Aucun changement (déjà à jour)"
  exit 0
fi

git add -A
git status
git commit -m "sync: mise à jour depuis agent/landing" || true
git push origin main

echo ""
echo "✅ Sync terminé. uwiapp.com sera mis à jour au prochain déploiement Vercel."
