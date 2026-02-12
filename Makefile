.PHONY: help install test run docker clean check-report-env export-kpis migrate migrate-007 migrate-008 migrate-railway railway-fix-vars onboard-tenant-users test-postgres

help:
	@echo "Commandes disponibles :"
	@echo "  make install         - Install dependencies"
	@echo "  make test            - Run all tests"
	@echo "  make test-postgres   - Tester connexion Postgres (DATABASE_URL ou railway run)"
	@echo "  make run             - Run dev server"
	@echo "  make docker          - Build & run docker"
	@echo "  make check-report-env - Vérifier les variables rapport quotidien (email)"
	@echo "  make export-kpis     - Export KPIs semaine précédente (--last-week)"
	@echo "  make migrate         - Run migrations 007+008 (local)"
	@echo "  make migrate-railway - Run migrations sur Railway"
	@echo "  make railway-fix-vars - Réappliquer variables TWILIO/SMTP (depuis .env)"
	@echo "  make backfill-tenant-users - Backfill tenant_users (tenants existants)"
	@echo "  make gh-secret-sync   - Configurer UWI_LANDING_PAT (gh secret set)"
	@echo "  make clean           - Clean cache & DB"

migrate: migrate-007 migrate-008

migrate-007:
	python3 -m backend.run_migration 007

migrate-008:
	python3 -m backend.run_migration 008

# Migration sur Railway (DATABASE_URL injecté). Prérequis : npx, railway login + railway link
migrate-railway:
	npx --yes @railway/cli run make migrate

# Réappliquer variables TWILIO/SMTP sur Railway (depuis .env). Fix "inactive"
railway-fix-vars:
	@chmod +x scripts/railway-fix-variables.sh && ./scripts/railway-fix-variables.sh

backfill-tenant-users:
	python3 scripts/backfill_tenant_users.py

# Tester Postgres (local avec .env ou railway run pour contexte Railway)
test-postgres:
	python3 scripts/test_postgres.py

# Configurer le secret GitHub pour le sync landing → uwi-landing
gh-secret-sync:
	@if command -v gh >/dev/null 2>&1; then \
		echo "Configuration de UWI_LANDING_PAT..."; \
		gh secret set UWI_LANDING_PAT; \
	else \
		echo "gh CLI non installé. Option 1 :"; \
		echo "  brew install gh && gh auth login && make gh-secret-sync"; \
		echo ""; \
		echo "Option 2 (manuel) :"; \
		echo "  https://github.com/lastminutejob75/agent/settings/secrets/actions"; \
		echo "  → New repository secret → Name: UWI_LANDING_PAT"; \
		echo ""; \
		echo "  Voir docs/GITHUB_SECRET_UWI_LANDING_PAT.md"; \
	fi

export-kpis:
	python3 scripts/export_weekly_kpis.py --last-week --out_dir .

check-report-env:
	python3 scripts/check_report_env.py

install:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt
	. .venv/bin/activate && python -c "from backend.db import init_db; init_db()"

test:
	pytest tests/ -v

test-compliance:
	pytest tests/test_prompt_compliance.py -v

test-engine:
	pytest tests/test_engine.py -v

test-api:
	pytest tests/test_api_sse.py -v

run:
	uvicorn backend.main:app --reload

docker:
	docker compose up --build

clean:
	rm -rf __pycache__ backend/__pycache__ tests/__pycache__ .pytest_cache
	rm -f agent.db
