.PHONY: test test-edge test-vps lint lint-edge lint-vps check

PYTHON := .venv/bin/python

# Run all tests (root pyproject.toml handles import isolation)
test:
	$(PYTHON) -m pytest edge/tests/ vps/tests/ -q

test-edge:
	$(PYTHON) -m pytest edge/tests/ -q

test-vps:
	$(PYTHON) -m pytest vps/tests/ -q

# Run lint checks
lint: lint-edge lint-vps

lint-edge:
	ruff check edge/src/

lint-vps:
	ruff check vps/src/

# Combined check (lint + test)
check: lint test
