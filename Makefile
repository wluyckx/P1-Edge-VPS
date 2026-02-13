.PHONY: test test-edge test-vps lint format check

PYTHON := .venv/bin/python

# Run all tests (root pyproject.toml handles import isolation)
test:
	$(PYTHON) -m pytest edge/tests/ vps/tests/ -q

test-edge:
	$(PYTHON) -m pytest edge/tests/ -q

test-vps:
	$(PYTHON) -m pytest vps/tests/ -q

# Lint (zero warnings required)
lint:
	ruff check edge/src/ edge/tests/ vps/src/ vps/tests/

# Format check (DoD gate)
format:
	ruff format --check edge/src/ edge/tests/ vps/src/ vps/tests/

# Combined check (lint + format + test)
check: lint format test
