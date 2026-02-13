.PHONY: test test-edge test-vps lint lint-edge lint-vps check

# Run all tests (per-component to avoid import collisions)
test: test-edge test-vps

test-edge:
	cd edge && python -m pytest tests/ -q

test-vps:
	cd vps && python -m pytest tests/ -q

# Run lint checks
lint: lint-edge lint-vps

lint-edge:
	ruff check edge/src/

lint-vps:
	ruff check vps/src/

# Combined check (lint + test)
check: lint test
