.PHONY: install test test-cov lint format typecheck eval smoke verify run-api run-dashboard clean ci

PYTHON_BIN ?= python3
PYTHON := .venv/bin/python
PIP    := .venv/bin/pip
PYTEST := .venv/bin/pytest
RUFF   := .venv/bin/ruff

install:
	$(PYTHON_BIN) -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

test:
	$(PYTEST) tests/ -v --tb=short

test-cov:
	$(PYTEST) tests/ -v --tb=short --cov=app --cov-report=term-missing --cov-report=html

lint:
	$(RUFF) check app/ tests/ evals/

lint-fix:
	$(RUFF) check --fix app/ tests/ evals/

format:
	$(RUFF) format app/ tests/ dashboard/ evals/

typecheck:
	$(PYTHON) -m compileall -q app tests dashboard evals

eval:
	PYTHONPATH=. $(PYTHON) -m evals.generate_validation_artifacts

smoke:
	@set -eu; \
	PORT=8014; \
	LOG=/tmp/retina-scan-ai-smoke.log; \
	.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port $$PORT >$$LOG 2>&1 & \
	pid=$$!; \
	trap 'kill $$pid >/dev/null 2>&1 || true' EXIT INT TERM; \
	for _ in 1 2 3 4 5 6 7 8 9 10; do \
		if curl -fsS "http://127.0.0.1:$$PORT/health" >/dev/null 2>&1; then \
			break; \
		fi; \
		sleep 1; \
	done; \
	curl -fsS "http://127.0.0.1:$$PORT/health" >/dev/null; \
	curl -fsS "http://127.0.0.1:$$PORT/api/v1/ops/resource-pack" >/dev/null; \
	curl -fsS "http://127.0.0.1:$$PORT/api/v1/ops/monitoring" >/dev/null; \
	curl -fsS "http://127.0.0.1:$$PORT/api/v1/ops/release-readiness" >/dev/null; \
	echo "smoke ok: http://127.0.0.1:$$PORT"

verify: lint typecheck test eval smoke

run-api:
	.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-dashboard:
	.venv/bin/streamlit run dashboard/app.py --server.port 8501

clean:
	rm -rf .venv __pycache__ .pytest_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

ci: verify
