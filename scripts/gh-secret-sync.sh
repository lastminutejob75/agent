#!/bin/bash
# Configure UWI_LANDING_PAT pour le workflow sync-landing
# Usage: ./scripts/gh-secret-sync.sh
# Prérequis: gh CLI installé (make gh-secret-sync ou ./scripts/gh-secret-sync.sh)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GH_BIN="$REPO_ROOT/.bin/gh"

# Utiliser gh du PATH ou .bin local
if command -v gh >/dev/null 2>&1; then
  GH="gh"
elif [ -x "$GH_BIN" ]; then
  GH="$GH_BIN"
  export PATH="$(dirname "$GH_BIN"):$PATH"
else
  echo "❌ gh CLI non trouvé. Installe-le :"
  echo "   brew install gh   # ou voir https://cli.github.com/"
  exit 1
fi

cd "$REPO_ROOT"

# Vérifier auth
if ! $GH auth status 2>/dev/null; then
  echo ""
  echo "🔐 Authentification requise. Lance :"
  echo "   $GH auth login"
  echo ""
  echo "Puis relance : ./scripts/gh-secret-sync.sh"
  exit 1
fi

echo "📦 Configuration de UWI_LANDING_PAT pour lastminutejob75/agent"
echo " (PAT avec repo + workflow pour push sur uwi-landing)"
echo ""
$GH secret set UWI_LANDING_PAT --repo lastminutejob75/agent
