#!/usr/bin/env bash
# Bootstrap sécurité production (PostgreSQL Railway)
# Usage:
#   export DATABASE_URL='postgresql://postgres:...@...railway.app:5432/railway'
#   ./scripts/prod_security_bootstrap.sh
#
# Ou avec mot de passe uwi_app choisi :
#   UWI_APP_PASSWORD='...' ./scripts/prod_security_bootstrap.sh

set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -z "${DATABASE_URL:-}" && -z "${DATABASE_URL_MIGRATE:-}" && -z "${PG_TENANTS_URL:-}" ]]; then
  echo "Erreur: définissez DATABASE_URL (utilisateur postgres Railway)." >&2
  exit 1
fi

export DATABASE_URL="${DATABASE_URL_MIGRATE:-${DATABASE_URL:-${PG_TENANTS_URL:-}}}"

echo "==> Migration 034 (RLS)"
python3 scripts/run_migration.py 034

echo "==> Rôle applicatif uwi_app + GRANT 035"
python3 scripts/setup_uwi_app_role.py

echo ""
echo "==> Rappel variables Railway (service backend)"
echo "  - DATABASE_URL_MIGRATE = URL postgres (migrations)"
echo "  - DATABASE_URL + PG_TENANTS_URL = URL uwi_app (affichée ci-dessus)"
echo "  - VAPI_WEBHOOK_SECRET, JWT_SECRET, ADMIN_SESSION_SECRET"
echo "  - ALLOW_GOOGLE_SELF_SIGNUP=false"
echo "  - REDIS_URL (recommandé)"
echo ""
echo "==> Optionnel : rattrapage profils cabinets"
echo "  python3 scripts/backfill_tenant_profile_from_params.py --dry-run"
echo "  python3 scripts/backfill_tenant_profile_from_params.py"
