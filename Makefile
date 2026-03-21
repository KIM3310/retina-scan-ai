.PHONY: install test test-cov lint format typecheck run-api run-dashboard clean

PYTHON := .venv/bin/python
PIP    := .venv/bin/pip
PYTEST := .venv/bin/pytest
RUFF   := .venv/bin/ruff

install:
	/usr/local/bin/python3.12 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

test:
	$(PYTEST) tests/ -v --tb=short

test-cov:
	$(PYTEST) tests/ -v --tb=short --cov=app --cov-report=term-missing --cov-report=html

lint:
	$(RUFF) check app/ tests/ dashboard/

lint-fix:
	$(RUFF) check --fix app/ tests/ dashboard/

format:
	$(RUFF) format app/ tests/ dashboard/

run-api:
	.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-dashboard:
	.venv/bin/streamlit run dashboard/app.py --server.port 8501

clean:
	rm -rf .venv __pycache__ .pytest_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

ci: lint test
