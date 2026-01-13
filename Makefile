.PHONY: help install test run docker clean

help:
	@echo "Commandes disponibles :"
	@echo "  make install   - Install dependencies"
	@echo "  make test      - Run all tests"
	@echo "  make run       - Run dev server"
	@echo "  make docker    - Build & run docker"
	@echo "  make clean     - Clean cache & DB"

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
