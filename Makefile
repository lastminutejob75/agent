.PHONY: help install test run docker clean check-report-env export-kpis migrate migrate-007 migrate-008 migrate-railway onboard-tenant-users

help:
	@echo "Commandes disponibles :"
	@echo "  make install         - Install dependencies"
	@echo "  make test            - Run all tests"
	@echo "  make run             - Run dev server"
	@echo "  make docker          - Build & run docker"
	@echo "  make check-report-env - Vérifier les variables rapport quotidien (email)"
	@echo "  make export-kpis     - Export KPIs semaine précédente (--last-week)"
	@echo "  make migrate         - Run migrations 007+008 (local)"
	@echo "  make migrate-railway - Run migrations sur Railway"
	@echo "  make backfill-tenant-users - Backfill tenant_users (tenants existants)"
	@echo "  make clean           - Clean cache & DB"

migrate: migrate-007 migrate-008

migrate-007:
	python3 scripts/run_migration.py 007

migrate-008:
	python3 scripts/run_migration.py 008

# Migration sur Railway (DATABASE_URL injecté). Prérequis : npx, railway login + railway link
migrate-railway:
	npx --yes @railway/cli run make migrate

backfill-tenant-users:
	python3 scripts/backfill_tenant_users.py

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
