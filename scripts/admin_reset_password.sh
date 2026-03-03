#!/bin/bash
# Réinitialise le mot de passe admin sur Railway.
# Usage: ./scripts/admin_reset_password.sh [nouveau_mot_de_passe]
# Si pas d'arg: utilise UwiAdmin#2026
#
# Prérequis: npx railway link (choisir le projet + service backend)

set -e
PWD="${1:-UwiAdmin#2026}"

echo "=== Réinitialisation mot de passe admin ==="
echo "Nouveau mot de passe: $PWD"
echo ""

# Vérifier que railway est lié
if ! npx railway status 2>/dev/null | grep -q .; then
  echo "❌ Aucun service Railway lié."
  echo "   Lance dans ce dossier: npx railway link"
  echo "   (choisis le projet + le service backend)"
  exit 1
fi

echo "→ Définition ADMIN_PASSWORD sur Railway..."
npx --yes @railway/cli variable set "ADMIN_PASSWORD=$PWD"

echo ""
echo "✅ Mot de passe mis à jour."
echo "   Railway redéploie automatiquement."
echo ""
echo "Test (remplace TON_EMAIL par ton ADMIN_EMAIL):"
echo "  curl -i -X POST https://agent-production-c246.up.railway.app/api/admin/auth/login \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"email\":\"TON_EMAIL\",\"password\":\"$PWD\"}'"
echo ""
echo "Puis /admin/login avec ton email et ce mot de passe."
