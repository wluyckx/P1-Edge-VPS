.PHONY: test test-edge test-vps lint format secrets check

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

# High-confidence secret scan (fails on likely real credentials/keys)
secrets:
	./scripts/secret_scan.sh

# Combined check (lint + format + secrets + test)
check: lint format secrets test
