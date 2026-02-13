# MEMORY.md — P1-Edge-VPS Project State

## Current State

**All 15 stories complete (100%).** Backlog fully delivered.
272 tests passing. `make check` green (lint + format + tests).

## Project Summary

Energy telemetry platform: edge daemon polls HomeWizard P1 meter, buffers
in SQLite, uploads to VPS API over HTTPS. VPS stores in TimescaleDB,
serves realtime/capacity/series endpoints with Redis caching.

## Backlog Status

| Phase | Stories | Status |
|-------|---------|--------|
| 1. Edge Foundation | STORY-001..005 | 5/5 done |
| 2. VPS Foundation | STORY-006..009 | 4/4 done |
| 3. API Features | STORY-010..013 | 4/4 done |
| 4. Production Readiness | STORY-014..015 | 2/2 done |

## Key Architecture Facts

- **Edge**: Python 3.12, httpx, SQLite spool, threading (poll + upload loops)
- **VPS**: FastAPI, SQLAlchemy async, TimescaleDB, Redis, Caddy reverse proxy
- **Auth**: Bearer tokens via DEVICE_TOKENS env var (token:device_id pairs)
- **Import conventions**: edge tests use `from edge.src.xxx`, VPS tests use `from src.xxx`
- **Test isolation**: root `pyproject.toml` with `--import-mode=importlib` + `pythonpath = [".", "vps"]`
- **Continuous aggregates**: p1_hourly, p1_daily, p1_monthly with sample_count (migration 003)
- **Weighted average**: rebucket uses `SUM(avg * count) / SUM(count)`, not `AVG(avg)`

## Quality Fixes Applied This Session

1. **Monorepo test isolation** — removed tests/__init__.py, added root pyproject.toml
2. **Average-of-averages** — migration 003 adds sample_count, aggregation.py uses weighted avg
3. **Empty batch guard** — IngestRequest.samples has min_length=1, service has early return
4. **Makefile Python** — uses .venv/bin/python, combined test command
5. **Edge health wiring** — write_health_file() called in upload loop, p1_connected tracked
6. **VPS healthcheck** — replaced curl with python urllib (slim image has no curl)
7. **Code formatting** — ruff format on all src + test files, format gate in Makefile

## Remaining Items (Parking Lot)

- Dashboard web UI
- Multi-device support
- Push notifications for capacity peaks
- Historical data export (CSV/JSON)
- Automated capacity tariff cost calculation
- Grafana integration

## Known Deployment Notes

- `DEVICE_ID` env var on edge must match the device_id in VPS `DEVICE_TOKENS` mapping.
  Defaults to `HW_P1_HOST` if not set — likely needs explicit configuration.

## Resume Checklist

```bash
git log --oneline -5
make check
```

## Environment

- Python 3.12 via `.venv/bin/python` (system Python is 3.8 — do not use)
- pytest 9.0.2
- ruff for lint + format
