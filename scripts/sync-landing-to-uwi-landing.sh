#!/bin/bash
# DÉPRÉCIÉ — uwiapp.com doit déployer depuis lastminutejob75/agent (Root Directory = landing).
# Ce script n'est conservé qu'en secours si un ancien projet Vercel pointe encore sur uwi-landing.
# Usage: ./scripts/sync-landing-to-uwi-landing.sh
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

# Copier uniquement ce dont Vercel a besoin (aligné sur .github/workflows/sync-landing.yml)
echo "📂 Copie src/, public/, config..."
SRC="$REPO_AGENT/landing"
DST="$REPO_LANDING"
rm -rf "$DST/src" && cp -r "$SRC/src" "$DST/"
mkdir -p "$DST/public"
[ -d "$SRC/public" ] && rm -rf "$DST/public" && cp -r "$SRC/public" "$DST/"
for f in index.html package.json package-lock.json vite.config.js tailwind.config.js postcss.config.js vercel.json netlify.toml .env.example .gitignore .nvmrc .node-version .vercelignore; do
  [ -f "$SRC/$f" ] && cp "$SRC/$f" "$DST/$f"
done

# Supprimer les dossiers/fichiers non nécessaires pour Vercel (backend, api, tests...)
echo "🧹 Nettoyage fichiers obsolètes..."
cd "$REPO_LANDING"
for dir in api app backend frontend lib tests; do [ -d "$dir" ] && rm -rf "$dir"; done
rm -f __init__.py config.py db.py engine.py fsm.py google_calendar.py guards.py main.py prompts.py session.py tools_booking.py tools_faq.py vapi.py 2>/dev/null || true
rm -f *.md Dockerfile docker-compose.yml Makefile next.config.js pyproject.toml requirements.txt 2>/dev/null || true
rm -f test_*.py apply_patch.sh apply_uwi_landing_patch.sh download_patch_from_github.sh extract_and_push_uwi_landing.sh install_ngrok.sh setup_google_calendar.sh test_ngrok.sh test_ngrok_webhook.sh test_vapi_complete.sh test_vapi_webhook.sh 2>/dev/null || true

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
