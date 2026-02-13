# Phase 2: VPS Foundation

**Status**: Not Started
**Stories**: 4
**Completed**: 0
**Depends On**: None (can be developed in parallel with Phase 1)

---

## Phase Completion Criteria

This phase is complete when:
- [ ] All stories have status "done"
- [ ] All tests passing (`pytest vps/tests/ -q`)
- [ ] Lint clean (`ruff check vps/src/`)
- [ ] Documentation updated
- [ ] VPS can receive authenticated batch ingestion and store in TimescaleDB

---

## Stories

<story id="STORY-006" status="pending" complexity="S" tdd="recommended">
  <title>VPS project scaffolding</title>
  <dependencies>None</dependencies>

  <description>
    Set up the VPS project directory structure, FastAPI app with health endpoint,
    configuration module (Pydantic BaseSettings), pyproject.toml, requirements.txt,
    Dockerfile, docker-compose.vps.yml, and Caddyfile. This is the foundation for all
    VPS development.
  </description>

  <acceptance_criteria>
    <ac id="AC1">vps/src/ directory exists with FastAPI app in main.py (GET / returns 200)</ac>
    <ac id="AC2">config.py uses Pydantic BaseSettings: DATABASE_URL, REDIS_URL, DEVICE_TOKENS,
      CACHE_TTL_S (default 5)</ac>
    <ac id="AC3">vps/tests/ directory with conftest.py, TestClient setup</ac>
    <ac id="AC4">requirements.txt: fastapi, uvicorn, sqlalchemy, asyncpg, redis, pydantic,
      pydantic-settings, alembic</ac>
    <ac id="AC5">Dockerfile builds Python 3.12 image, installs deps, runs uvicorn</ac>
    <ac id="AC6">docker-compose.vps.yml: api, postgres (timescale/timescaledb), redis, caddy</ac>
    <ac id="AC7">Caddyfile: reverse proxy to api:8000 with auto-HTTPS</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>vps/src/__init__.py</file>
    <file>vps/src/main.py</file>
    <file>vps/src/config.py</file>
    <file>vps/src/api/__init__.py</file>
    <file>vps/src/api/deps.py</file>
    <file>vps/src/auth/__init__.py</file>
    <file>vps/src/db/__init__.py</file>
    <file>vps/src/db/session.py</file>
    <file>vps/src/cache/__init__.py</file>
    <file>vps/src/services/__init__.py</file>
    <file>vps/tests/__init__.py</file>
    <file>vps/tests/conftest.py</file>
    <file>vps/requirements.txt</file>
    <file>vps/pyproject.toml</file>
    <file>vps/Dockerfile</file>
    <file>docker-compose.vps.yml</file>
    <file>Caddyfile</file>
  </allowed_scope>

  <test_plan>
    - TestClient: GET / returns 200 with health status JSON
    - Config loads from env vars with correct defaults
    - `pytest vps/tests/ -q` all pass
  </test_plan>

  <notes>
    - FastAPI auto-generates /docs (Swagger UI) and /redoc endpoints
    - Caddy: use placeholder domain, auto-HTTPS with Let's Encrypt
    - PostgreSQL image: timescale/timescaledb:latest-pg16
    - Redis image: redis:7-alpine
  </notes>
</story>

---

<story id="STORY-007" status="pending" complexity="M" tdd="required">
  <title>Database schema + TimescaleDB hypertable</title>
  <dependencies>STORY-006</dependencies>

  <description>
    Create the SQLAlchemy model for p1_samples, the Alembic migration that creates the
    table with TimescaleDB hypertable, and the database session management module.

    Schema (from technicaldesign.md):
    - device_id TEXT NOT NULL
    - ts TIMESTAMPTZ NOT NULL
    - power_w INTEGER NOT NULL
    - import_power_w INTEGER NOT NULL
    - energy_import_kwh DOUBLE PRECISION
    - energy_export_kwh DOUBLE PRECISION
    - PRIMARY KEY (device_id, ts)
    - TimescaleDB hypertable on ts column
  </description>

  <acceptance_criteria>
    <ac id="AC1">models.py defines P1Sample with all columns matching schema above</ac>
    <ac id="AC2">Composite primary key on (device_id, ts)</ac>
    <ac id="AC3">Alembic migration: CREATE EXTENSION IF NOT EXISTS timescaledb</ac>
    <ac id="AC4">Alembic migration: CREATE TABLE p1_samples with correct schema</ac>
    <ac id="AC5">Alembic migration: SELECT create_hypertable('p1_samples', 'ts')</ac>
    <ac id="AC6">session.py provides async_engine and async_session_factory</ac>
    <ac id="AC7">DB session injectable via FastAPI Depends() in deps.py</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>vps/src/db/models.py</file>
    <file>vps/src/db/session.py</file>
    <file>vps/src/db/__init__.py</file>
    <file>vps/src/db/migrations/env.py</file>
    <file>vps/src/db/migrations/versions/001_initial_schema.py</file>
    <file>vps/src/api/deps.py</file>
    <file>vps/tests/test_models.py</file>
  </allowed_scope>

  <test_first>
    <item>Create vps/tests/test_models.py FIRST</item>
    <item>Test: P1Sample model has correct column names</item>
    <item>Test: P1Sample model has correct column types</item>
    <item>Test: composite primary key on (device_id, ts)</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>

  <test_plan>
    - Unit tests for model definition (introspect column metadata)
    - Migration SQL review (verify DDL correctness)
    - `pytest vps/tests/ -q` all pass
  </test_plan>

  <notes>
    - SQLAlchemy 2.x async style
    - Use mapped_column() for type annotations
    - Alembic: configure for async engine
    - TimescaleDB extension must be enabled before create_hypertable
  </notes>
</story>

---

<story id="STORY-008" status="pending" complexity="S" tdd="required">
  <title>Device authentication (Bearer tokens)</title>
  <dependencies>STORY-006</dependencies>

  <description>
    Implement Bearer token validation for the VPS API. Valid tokens are configured via the
    DEVICE_TOKENS environment variable. Format: "token1:device1,token2:device2". Each token
    maps to a device_id. Invalid or missing tokens return 401 Unauthorized.
  </description>

  <acceptance_criteria>
    <ac id="AC1">bearer.py validates Authorization: Bearer {token} header</ac>
    <ac id="AC2">Valid token: request continues, device_id extracted from token mapping</ac>
    <ac id="AC3">Invalid token: returns 401 Unauthorized with JSON error body</ac>
    <ac id="AC4">Missing Authorization header: returns 401 Unauthorized</ac>
    <ac id="AC5">Tokens loaded from DEVICE_TOKENS env var at startup</ac>
    <ac id="AC6">Auth dependency injectable via FastAPI Depends() — returns device_id string</ac>
    <ac id="AC7">Token comparison uses constant-time comparison (secrets.compare_digest)</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>vps/src/auth/__init__.py</file>
    <file>vps/src/auth/bearer.py</file>
    <file>vps/src/api/deps.py</file>
    <file>vps/tests/test_auth.py</file>
  </allowed_scope>

  <test_first>
    <item>Create vps/tests/test_auth.py FIRST</item>
    <item>Test: valid token → returns device_id</item>
    <item>Test: invalid token → raises 401</item>
    <item>Test: missing Authorization header → raises 401</item>
    <item>Test: malformed header (no "Bearer " prefix) → raises 401</item>
    <item>Test: empty token string → raises 401</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>

  <test_plan>
    - Unit tests for token validation function
    - Integration test via TestClient with auth header
    - `pytest vps/tests/ -q` all pass
  </test_plan>

  <notes>
    - DEVICE_TOKENS format: "tokenA:device-1,tokenB:device-2"
    - Parse at startup into dict: {token: device_id}
    - Use secrets.compare_digest() to prevent timing attacks
    - FastAPI HTTPBearer security scheme for OpenAPI docs
  </notes>
</story>

---

<story id="STORY-009" status="pending" complexity="L" tdd="required">
  <title>Ingest API endpoint</title>
  <dependencies>STORY-007, STORY-008</dependencies>

  <description>
    The core ingestion endpoint. Receives a JSON batch of samples from edge, validates
    with Pydantic, performs idempotent upsert into TimescaleDB, and returns the count of
    new rows inserted. This is the VPS counterpart to the edge uploader (STORY-005).

    Must enforce HC-002 (Idempotent Ingestion): INSERT ON CONFLICT DO NOTHING.
  </description>

  <acceptance_criteria>
    <ac id="AC1">POST /v1/ingest accepts {"samples": [...]} JSON body</ac>
    <ac id="AC2">Each sample validated: device_id, ts, power_w, import_power_w,
      energy_import_kwh, energy_export_kwh</ac>
    <ac id="AC3">Requires valid Bearer token (auth dependency from STORY-008)</ac>
    <ac id="AC4">INSERT ON CONFLICT (device_id, ts) DO NOTHING — idempotent</ac>
    <ac id="AC5">Returns 200 with {"inserted": N} where N = new rows (not duplicates)</ac>
    <ac id="AC6">Returns 401 on invalid/missing auth</ac>
    <ac id="AC7">Returns 422 on invalid request body (Pydantic validation error)</ac>
    <ac id="AC8">All sample device_id values must match authenticated device_id from Bearer token; reject 403 on mismatch</ac>
    <ac id="AC9">Invalidates Redis cache for the device on successful ingest</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>vps/src/api/ingest.py</file>
    <file>vps/src/services/ingestion.py</file>
    <file>vps/src/cache/redis_client.py</file>
    <file>vps/tests/test_ingest.py</file>
    <file>vps/tests/fixtures/sample_data.json</file>
  </allowed_scope>

  <test_first>
    <item>Create vps/tests/test_ingest.py FIRST</item>
    <item>Create vps/tests/fixtures/sample_data.json with valid and invalid batches</item>
    <item>Mock AsyncSession for DB operations</item>
    <item>Mock Redis client for cache invalidation</item>
    <item>Test: valid batch with auth → 200 with insert count</item>
    <item>Test: duplicate batch (same device_id + ts) → 200 with inserted=0</item>
    <item>Test: invalid body (missing fields) → 422</item>
    <item>Test: missing auth → 401</item>
    <item>Test: invalid auth → 401</item>
    <item>Test: sample device_id differs from authenticated device_id → 403</item>
    <item>Test: successful ingest calls Redis delete on key "realtime:{device_id}"</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>

  <test_plan>
    - Unit tests for ingestion service (mocked session)
    - Integration tests via TestClient (mocked DB + Redis)
    - Idempotency test: same batch twice → second returns inserted=0
    - Auth test: missing/invalid token → 401
    - Device integrity test: device_id mismatch → 403
    - Cache invalidation test: assert Redis delete called with "realtime:{device_id}"
    - Validation test: malformed body → 422
    - `pytest vps/tests/ -q` all pass
  </test_plan>

  <notes>
    - Pydantic model: SampleCreate(device_id: str, ts: datetime, power_w: int,
      import_power_w: int, energy_import_kwh: float | None, energy_export_kwh: float | None)
    - Request model: IngestRequest(samples: list[SampleCreate])
    - SQLAlchemy: insert(P1Sample).values(...).on_conflict_do_nothing(
        index_elements=["device_id", "ts"])
    - Cache invalidation: delete keys "realtime:{device_id}" on ingest
  </notes>
</story>

---

## Phase Notes

### Dependencies on Other Phases
- Phase 1 (Edge Foundation) can be developed in parallel — no cross-phase dependencies
- STORY-009 is the integration point where edge uploads connect to VPS

### Known Risks
- TimescaleDB Docker image version compatibility with PostgreSQL 16
- Alembic async configuration can be tricky — test early

### Technical Debt
- Redis cache invalidation in STORY-009 is basic (key deletion) — may need pub/sub later
