#!/bin/bash
# Sync landing/ (agent repo) → uwi-landing (uwiapp.com)
# Usage: ./scripts/sync_landing_to_uwiapp.sh
# Prérequis: agent repo à jour, accès push sur uwi-landing

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LANDING_SRC="$REPO_ROOT/landing"
SYNC_DIR="${SYNC_DIR:-/tmp/uwi-landing-sync}"
UWI_LANDING_REPO="${UWI_LANDING_REPO:-https://github.com/lastminutejob75/uwi-landing.git}"

echo "🔄 SYNC landing → uwi-landing (uwiapp.com)"
echo "=========================================="
echo "Source: $LANDING_SRC"
echo "Target: $UWI_LANDING_REPO"
echo ""

# Vérifier que landing/ existe
if [ ! -d "$LANDING_SRC/src" ]; then
  echo "❌ $LANDING_SRC/src introuvable"
  exit 1
fi

# Clone ou update uwi-landing
if [ -d "$SYNC_DIR" ]; then
  echo "📂 Mise à jour $SYNC_DIR..."
  cd "$SYNC_DIR"
  git fetch origin
  git checkout main
  git pull origin main || true
else
  echo "📥 Clone uwi-landing..."
  git clone "$UWI_LANDING_REPO" "$SYNC_DIR"
  cd "$SYNC_DIR"
  git checkout main
fi

# Fichiers/dossiers à copier (frontend uniquement)
echo ""
echo "📋 Copie des fichiers..."
rsync -av --delete "$LANDING_SRC/src/" "$SYNC_DIR/src/"
mkdir -p "$SYNC_DIR/public"
[ -d "$LANDING_SRC/public" ] && rsync -av --delete "$LANDING_SRC/public/" "$SYNC_DIR/public/"

for f in index.html package.json package-lock.json vite.config.js tailwind.config.js postcss.config.js vercel.json netlify.toml .env.example .gitignore .vercelignore .nvmrc .node-version; do
  [ -f "$LANDING_SRC/$f" ] && cp "$LANDING_SRC/$f" "$SYNC_DIR/$f"
done

# Nettoyer fichiers backend résiduels
rm -rf "$SYNC_DIR/backend" "$SYNC_DIR/api" "$SYNC_DIR/tests" 2>/dev/null || true

# Statut
echo ""
echo "📊 Modifications:"
git status --short

if [ -z "$(git status --porcelain)" ]; then
  echo ""
  echo "✅ Aucune modification (déjà à jour)"
  exit 0
fi

# Commit et push
echo ""
if [[ "$1" == "-y" ]] || [[ "$1" == "--yes" ]]; then
  DO_PUSH=1
else
  read -p "Commit et push vers uwi-landing ? (y/N) " -n 1 -r
  echo
  [[ $REPLY =~ ^[Yy]$ ]] && DO_PUSH=1
fi
if [[ -n "$DO_PUSH" ]]; then
  git add -A
  git commit -m "chore: sync from agent (landing/)"
  git push origin main
  echo ""
  echo "✅ Sync terminé. uwiapp.com déploiera automatiquement."
else
  echo "Annulé. Modifications dans $SYNC_DIR"
fi
