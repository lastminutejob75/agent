#!/usr/bin/env bash
# Protège la branche main sur lastminutejob75/agent (anti force-push, pas de PR obligatoire).
# Prérequis : droits admin sur le dépôt + l'un des deux :
#   • brew install gh && gh auth login
#   • ou variable d'environnement GITHUB_TOKEN (classic : scope "repo", ou fine-grained : Administration write)
set -euo pipefail

OWNER="lastminutejob75"
REPO="agent"
BRANCH="main"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GH_BIN="$REPO_ROOT/.bin/gh"

TOKEN=""
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  TOKEN="$(gh auth token)"
elif [ -x "$GH_BIN" ] && "$GH_BIN" auth status >/dev/null 2>&1; then
  TOKEN="$("$GH_BIN" auth token)"
elif [ -n "${GITHUB_TOKEN:-}" ]; then
  TOKEN="$GITHUB_TOKEN"
else
  echo ""
  echo "❌ Pas de jeton GitHub disponible."
  echo ""
  echo "   Option A (recommandé) :"
  echo "     brew install gh"
  echo "     gh auth login"
  echo "     $0"
  echo ""
  echo "   Option B :"
  echo "     export GITHUB_TOKEN=ghp_xxxx   # token avec droits repo admin"
  echo "     $0"
  echo ""
  exit 1
fi

RESP="$(mktemp)"
HTTP_CODE="$(curl -sS -o "$RESP" -w "%{http_code}" \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/$OWNER/$REPO/branches/$BRANCH/protection" \
  -d "$(cat <<'JSON'
{
  "required_status_checks": null,
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": false,
  "lock_branch": false,
  "allow_fork_syncing": false
}
JSON
)")"

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
  echo "✅ Branche $BRANCH protégée sur $OWNER/$REPO (HTTP $HTTP_CODE)"
  echo "   • force push : interdit"
  echo "   • suppression de branche : interdit"
  echo "   • PR obligatoire : non (push direct sur main toujours possible)"
  echo "   • admins : pas de contournement (enforce_admins)"
  echo ""
  echo "ℹ️  Supprime manuellement sur GitHub toute règle inutile dont le motif est « uwi » :"
  echo "   https://github.com/$OWNER/$REPO/settings/branches"
  rm -f "$RESP"
  exit 0
fi

echo "❌ Échec (HTTP $HTTP_CODE). Réponse API :"
cat "$RESP"
echo ""
rm -f "$RESP"
exit 1
