<backlog>

<metadata>
  <project>P1-Edge-VPS Energy Telemetry Platform</project>
  <last_updated>2026-02-13</last_updated>
  <total_stories>15</total_stories>
  <done>12</done>
  <progress>80%</progress>
  <changelog>
    <entry date="2026-02-13">Wave 4: STORY-010 (realtime) + STORY-011 (capacity tariff) + STORY-012 (historical series) done. Review fixes: explicit DEVICE_ID config, HTTPBearer auto_error=False for 401, eager startup token validation, root Makefile for CI, URL trailing-slash strip. 220 tests, 0 failures.</entry>
    <entry date="2026-02-13">Wave 3: STORY-005 (batch uploader) + STORY-009 (ingest API) done. Review fixes: lazy auth init via get_settings(), poller catch-all exception, normalizer tz-aware enforcement, spool peek guard, token parse warning logs. 168 tests, 0 failures.</entry>
    <entry date="2026-02-13">Wave 2: STORY-002..004 (edge) + STORY-007..008 (VPS) done. Review fixes: standardize VPS imports to src.X, edge conftest future annotations, remove direct port 8000 binding, monkeypatch config tests, fix .env.example asyncpg URL, add requirements-dev.txt. 121 tests, 0 failures.</entry>
    <entry date="2026-02-13">Fix 7 backlog issues: canonical ingest contract (wrapped object), device_id auth matching AC, HTTPS enforcement ACs, sync cross-file drift, trim rolling 12-month from STORY-011, create technicaldesign.md, add contract dependency note to STORY-005</entry>
    <entry date="2026-02-13">Initial backlog creation (15 stories across 3 phases)</entry>
  </changelog>
</metadata>

<!-- ============================================================ -->
<!-- MVP DEFINITION                                                -->
<!-- ============================================================ -->

<mvp>
  <goal>End-to-end telemetry pipeline: edge polls P1 meter, buffers locally, uploads to VPS, stores in TimescaleDB, serves realtime and capacity endpoints via cached API.</goal>

  <scope>
    <item priority="1" story="STORY-001">Edge project scaffolding and configuration</item>
    <item priority="2" story="STORY-002">HomeWizard P1 poller</item>
    <item priority="3" story="STORY-003">Measurement normalizer</item>
    <item priority="4" story="STORY-004">SQLite spool (local buffer)</item>
    <item priority="5" story="STORY-005">Batch uploader with retry</item>
    <item priority="6" story="STORY-006">VPS project scaffolding</item>
    <item priority="7" story="STORY-007">Database schema + TimescaleDB hypertable</item>
    <item priority="8" story="STORY-008">Device authentication (Bearer tokens)</item>
    <item priority="9" story="STORY-009">Ingest API endpoint (idempotent)</item>
    <item priority="10" story="STORY-010">Realtime metrics endpoint (cached)</item>
    <item priority="11" story="STORY-011">Capacity tariff calculation</item>
  </scope>

  <deliverables>
    <item>Edge daemon that polls P1, buffers in SQLite, uploads batches to VPS</item>
    <item>VPS API with authenticated ingest, realtime, and capacity endpoints</item>
    <item>Docker Compose files for both edge and VPS deployment</item>
    <item>Full test suite with mocked external dependencies</item>
  </deliverables>

  <post_mvp>
    <item>Historical series endpoint with aggregation frames (STORY-012)</item>
    <item>TimescaleDB continuous aggregates (STORY-013)</item>
    <item>Health checks and monitoring (STORY-014)</item>
    <item>Production hardening — structured logging, graceful shutdown (STORY-015)</item>
  </post_mvp>
</mvp>

<!-- ============================================================ -->
<!-- KEY CONSTRAINTS                                               -->
<!-- ============================================================ -->

<constraints>
  <constraint id="HC-001" ref="Architecture.md">No data loss — every polled sample must reach TimescaleDB, even across outages</constraint>
  <constraint id="HC-002" ref="Architecture.md">Idempotent ingestion — (device_id, ts) composite PK, ON CONFLICT DO NOTHING</constraint>
  <constraint id="HC-003" ref="Architecture.md">HTTPS only — all edge↔VPS traffic encrypted with valid certificates</constraint>
</constraints>

<!-- ============================================================ -->
<!-- DEFINITION OF READY                                           -->
<!-- ============================================================ -->

<dor>
  <title>Definition of Ready</title>
  <description>A story is ready for development when ALL conditions are true:</description>
  <checklist>
    <item>Clear description of what needs to be built</item>
    <item>Acceptance criteria are specific and testable</item>
    <item>Dependencies are identified and completed</item>
    <item>Technical approach is understood</item>
    <item>Estimated complexity noted (S/M/L/XL)</item>
    <item>Allowed Scope defined (files/modules)</item>
    <item>Test-First Requirements defined (if TDD-mandated)</item>
    <item>Mock strategy defined for external dependencies</item>
  </checklist>
</dor>

<!-- ============================================================ -->
<!-- DEFINITION OF DONE                                            -->
<!-- ============================================================ -->

<dod>
  <title>Definition of Done</title>
  <description>A story is complete when ALL conditions are true:</description>
  <checklist>
    <item>All acceptance criteria pass</item>
    <item>ruff check passes with zero warnings</item>
    <item>ruff format --check passes</item>
    <item>pytest passes with no failures</item>
    <item>Documentation on all public APIs</item>
    <item>CHANGELOG header updated in modified files</item>
    <item>No undocumented TODOs introduced</item>
    <item>Security checklist passed (per CLAUDE.md section 13)</item>
    <item>Code reviewed (self-review minimum)</item>
  </checklist>
</dod>

<!-- ============================================================ -->
<!-- PRIORITY ORDER                                                -->
<!-- ============================================================ -->

<priority_order>
  <tier name="Edge Foundation" description="Edge daemon: poll, normalize, buffer, upload">
    <entry priority="1" story="STORY-001" title="Edge project scaffolding" complexity="S" deps="None" />
    <entry priority="2" story="STORY-002" title="HomeWizard P1 poller" complexity="M" deps="STORY-001" />
    <entry priority="3" story="STORY-003" title="Measurement normalizer" complexity="S" deps="STORY-001" />
    <entry priority="4" story="STORY-004" title="SQLite spool" complexity="M" deps="STORY-001" />
    <entry priority="5" story="STORY-005" title="Batch uploader with retry" complexity="L" deps="STORY-002, STORY-003, STORY-004" />
  </tier>

  <tier name="VPS Foundation" description="VPS API: schema, auth, ingest">
    <entry priority="6" story="STORY-006" title="VPS project scaffolding" complexity="S" deps="None" />
    <entry priority="7" story="STORY-007" title="Database schema + TimescaleDB" complexity="M" deps="STORY-006" />
    <entry priority="8" story="STORY-008" title="Device authentication" complexity="S" deps="STORY-006" />
    <entry priority="9" story="STORY-009" title="Ingest API endpoint" complexity="L" deps="STORY-007, STORY-008" />
  </tier>

  <tier name="API Features" description="Query endpoints and calculations">
    <entry priority="10" story="STORY-010" title="Realtime metrics endpoint" complexity="M" deps="STORY-009" />
    <entry priority="11" story="STORY-011" title="Capacity tariff calculation" complexity="L" deps="STORY-009" />
    <entry priority="12" story="STORY-012" title="Historical series endpoint" complexity="L" deps="STORY-009" />
    <entry priority="13" story="STORY-013" title="Continuous aggregates" complexity="M" deps="STORY-007, STORY-012" />
  </tier>

  <tier name="Production Readiness" description="Monitoring, hardening, operational readiness">
    <entry priority="14" story="STORY-014" title="Health checks and monitoring" complexity="M" deps="STORY-005, STORY-009" />
    <entry priority="15" story="STORY-015" title="Production hardening" complexity="M" deps="STORY-005, STORY-009" />
  </tier>
</priority_order>

<!-- ============================================================ -->
<!-- PHASE 1: Edge Foundation                                       -->
<!-- Story file: docs/stories/phase-1-edge-foundation.md            -->
<!-- ============================================================ -->

<phase id="1" name="Edge Foundation" story_file="docs/stories/phase-1-edge-foundation.md">

<story id="STORY-001" status="done" complexity="S" tdd="recommended">
  <title>Edge project scaffolding</title>
  <dependencies>None</dependencies>
  <description>
    Set up the edge project directory structure, configuration module (Pydantic BaseSettings),
    pyproject.toml, requirements.txt, Dockerfile, and docker-compose.edge.yml.
  </description>
  <acceptance_criteria>
    <ac id="AC1">edge/src/ directory exists with __init__.py and config.py</ac>
    <ac id="AC2">config.py uses Pydantic BaseSettings with all env vars from Architecture.md</ac>
    <ac id="AC3">edge/tests/ directory exists with conftest.py</ac>
    <ac id="AC4">requirements.txt lists all edge dependencies from Architecture.md Tech Stack</ac>
    <ac id="AC5">Dockerfile builds successfully</ac>
    <ac id="AC6">docker-compose.edge.yml matches Architecture.md spec</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>edge/src/__init__.py</file>
    <file>edge/src/config.py</file>
    <file>edge/tests/__init__.py</file>
    <file>edge/tests/conftest.py</file>
    <file>edge/tests/test_config.py</file>
    <file>edge/requirements.txt</file>
    <file>edge/pyproject.toml</file>
    <file>edge/Dockerfile</file>
    <file>docker-compose.edge.yml</file>
    <file>.env.example</file>
    <file>.gitignore</file>
  </allowed_scope>
  <test_plan>
    - Unit test: config loads from env vars with defaults
    - Unit test: config validation rejects missing required vars
    - pytest edge/tests/ -q all pass
  </test_plan>
  <notes>
    - Use Pydantic BaseSettings for config validation
    - All env vars per Architecture.md Environment &amp; Secrets section
  </notes>
</story>

<story id="STORY-002" status="done" complexity="M" tdd="required">
  <title>HomeWizard P1 poller</title>
  <dependencies>STORY-001</dependencies>
  <description>
    Implement the HTTP poller that reads from the HomeWizard P1 meter's Local API v2
    endpoint (/api/measurement). Must handle connection errors gracefully and return
    raw measurement dict or None on failure.
  </description>
  <acceptance_criteria>
    <ac id="AC1">poller.py sends HTTP GET with Bearer token to HW_P1_HOST/api/measurement</ac>
    <ac id="AC2">Returns parsed JSON dict on success</ac>
    <ac id="AC3">Returns None and logs warning on connection error (does not crash)</ac>
    <ac id="AC4">Returns None and logs warning on HTTP error status</ac>
    <ac id="AC5">Configurable timeout from config</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>edge/src/poller.py</file>
    <file>edge/tests/test_poller.py</file>
    <file>edge/tests/fixtures/hw_responses.json</file>
  </allowed_scope>
  <test_first>
    <item>Create edge/tests/test_poller.py FIRST</item>
    <item>Create edge/tests/fixtures/hw_responses.json with mock P1 responses</item>
    <item>Mock httpx.Client to return fixture data</item>
    <item>Test: successful poll returns parsed measurement dict</item>
    <item>Test: connection error returns None</item>
    <item>Test: HTTP error status returns None</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>
  <test_plan>
    - Unit tests with mocked httpx.Client
    - Fixture-based responses (success, error, timeout)
    - pytest edge/tests/ -q all pass
  </test_plan>
  <notes>
    - HomeWizard P1 Local API v2: GET /api/measurement with Authorization: Bearer {token}
    - Response includes: power_w, energy_import_kwh, energy_export_kwh, and more
  </notes>
</story>

<story id="STORY-003" status="done" complexity="S" tdd="required">
  <title>Measurement normalizer</title>
  <dependencies>STORY-001</dependencies>
  <description>
    Pure function that takes raw HomeWizard measurement dict and returns a normalized
    sample dict with: ts (UTC ISO 8601), device_id, power_w, import_power_w,
    energy_import_kwh, energy_export_kwh.
  </description>
  <acceptance_criteria>
    <ac id="AC1">normalizer.py exports normalize(raw: dict, device_id: str, ts: datetime) -> dict</ac>
    <ac id="AC2">Output includes all fields from p1_samples schema</ac>
    <ac id="AC3">import_power_w = max(power_w, 0)</ac>
    <ac id="AC4">Raises ValueError on missing required fields in raw input</ac>
    <ac id="AC5">ts parameter allows injectable timestamp (no datetime.now() calls)</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>edge/src/normalizer.py</file>
    <file>edge/tests/test_normalizer.py</file>
  </allowed_scope>
  <test_first>
    <item>Create edge/tests/test_normalizer.py FIRST</item>
    <item>Test: valid input produces correct normalized output</item>
    <item>Test: import_power_w is max(power_w, 0) for negative values</item>
    <item>Test: missing required fields raise ValueError</item>
    <item>Test: ts is passed through (not generated internally)</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>
  <test_plan>
    - Unit tests with fixture data
    - Edge cases: negative power, missing fields, zero values
    - pytest edge/tests/ -q all pass
  </test_plan>
  <notes>
    - Pure function — no side effects, no I/O
    - Accept ts as parameter for testability (ref Architecture.md Time-Dependent Testing)
  </notes>
</story>

<story id="STORY-004" status="done" complexity="M" tdd="required">
  <title>SQLite spool (local buffer)</title>
  <dependencies>STORY-001</dependencies>
  <description>
    Implement the SQLite-based local buffer that stores normalized samples before upload.
    Must support: enqueue (write sample), peek (read batch without deleting),
    ack (delete confirmed samples by rowid), and count.
  </description>
  <acceptance_criteria>
    <ac id="AC1">spool.py creates SQLite DB with WAL mode at configurable path</ac>
    <ac id="AC2">enqueue() inserts a normalized sample row</ac>
    <ac id="AC3">peek(n) returns up to n oldest samples with their rowids</ac>
    <ac id="AC4">ack(rowids) deletes only the specified rows</ac>
    <ac id="AC5">count() returns number of pending samples</ac>
    <ac id="AC6">Spool survives process restart (persistent file)</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>edge/src/spool.py</file>
    <file>edge/tests/test_spool.py</file>
  </allowed_scope>
  <test_first>
    <item>Create edge/tests/test_spool.py FIRST</item>
    <item>Use tmp_path fixture for isolated SQLite files</item>
    <item>Test: enqueue + peek returns the sample</item>
    <item>Test: ack removes only specified rows</item>
    <item>Test: peek returns oldest first (FIFO order)</item>
    <item>Test: count reflects actual pending count</item>
    <item>Test: empty spool peek returns empty list</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>
  <test_plan>
    - Unit tests with real SQLite (tmp_path)
    - FIFO ordering verification
    - Partial ack (ack some, verify rest remain)
    - pytest edge/tests/ -q all pass
  </test_plan>
  <notes>
    - Use WAL mode for concurrent read/write safety
    - Schema: rowid INTEGER PRIMARY KEY, device_id TEXT, ts TEXT, power_w INTEGER,
      import_power_w INTEGER, energy_import_kwh REAL, energy_export_kwh REAL
  </notes>
</story>

<story id="STORY-005" status="done" complexity="L" tdd="required">
  <title>Batch uploader with retry</title>
  <dependencies>STORY-002, STORY-003, STORY-004</dependencies>
  <description>
    Implement the batch uploader that reads from the spool, POSTs batches to the VPS
    ingest endpoint, and acks confirmed samples. Includes exponential backoff on failure
    and integration into the main edge daemon loop.
  </description>
  <acceptance_criteria>
    <ac id="AC1">uploader.py reads batch from spool via peek()</ac>
    <ac id="AC2">POSTs batch as JSON to VPS_INGEST_URL/v1/ingest with Bearer token</ac>
    <ac id="AC3">On 2xx response, acks the uploaded rowids from spool</ac>
    <ac id="AC4">On failure, retries with exponential backoff (configurable base/max)</ac>
    <ac id="AC5">Never deletes samples from spool without server confirmation</ac>
    <ac id="AC6">Uploader validates VPS_INGEST_URL is HTTPS at startup; rejects HTTP (HC-003)</ac>
    <ac id="AC7">TLS certificate verification enabled (verify=True); never disabled in production</ac>
    <ac id="AC8">main.py runs poll loop + upload loop (configurable intervals)</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>edge/src/uploader.py</file>
    <file>edge/src/main.py</file>
    <file>edge/tests/test_uploader.py</file>
  </allowed_scope>
  <test_first>
    <item>Create edge/tests/test_uploader.py FIRST</item>
    <item>Mock httpx.Client for VPS responses</item>
    <item>Mock spool for peek/ack calls</item>
    <item>Test: successful upload acks rowids</item>
    <item>Test: failed upload does NOT ack (samples remain)</item>
    <item>Test: exponential backoff delay sequence</item>
    <item>Test: empty spool skips upload</item>
    <item>Test: VPS_INGEST_URL with http:// scheme raises error at startup (HC-003)</item>
    <item>Test: httpx client is created with verify=True (TLS cert verification)</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>
  <test_plan>
    - Unit tests with mocked HTTP client and mocked spool
    - Verify ack/no-ack behavior on success/failure
    - Verify backoff timing sequence
    - Verify http:// URL rejected at init (HC-003)
    - Verify TLS verify=True on HTTP client
    - pytest edge/tests/ -q all pass
  </test_plan>
  <notes>
    - Backoff: 1s, 2s, 4s, 8s, ... up to configurable max (default 300s)
    - Reset backoff on successful upload
    - main.py ties together: poll → normalize → spool → upload cycle
    - CONTRACT: Builds payload per technicaldesign.md ingest spec: {"samples": [...]}.
      No runtime dependency on STORY-009 (parallel dev OK), but contract must stay in sync.
  </notes>
</story>

</phase>

<!-- ============================================================ -->
<!-- PHASE 2: VPS Foundation                                       -->
<!-- Story file: docs/stories/phase-2-vps-foundation.md            -->
<!-- ============================================================ -->

<phase id="2" name="VPS Foundation" story_file="docs/stories/phase-2-vps-foundation.md">

<story id="STORY-006" status="done" complexity="S" tdd="recommended">
  <title>VPS project scaffolding</title>
  <dependencies>None</dependencies>
  <description>
    Set up the VPS project directory structure, FastAPI app, configuration module,
    pyproject.toml, requirements.txt, Dockerfile, docker-compose.vps.yml, and Caddyfile.
  </description>
  <acceptance_criteria>
    <ac id="AC1">vps/src/ directory exists with FastAPI app in main.py</ac>
    <ac id="AC2">config.py uses Pydantic BaseSettings with all VPS env vars</ac>
    <ac id="AC3">vps/tests/ directory exists with conftest.py and TestClient setup</ac>
    <ac id="AC4">requirements.txt lists all VPS dependencies from Architecture.md Tech Stack</ac>
    <ac id="AC5">Dockerfile builds successfully</ac>
    <ac id="AC6">docker-compose.vps.yml includes api, postgres, redis, caddy services</ac>
    <ac id="AC7">FastAPI health endpoint GET / returns 200</ac>
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
    - TestClient: GET / returns 200 with health status
    - Config loads from env vars with defaults
    - pytest vps/tests/ -q all pass
  </test_plan>
  <notes>
    - FastAPI app with /docs auto-generated
    - Caddy reverse proxies to FastAPI on port 8000
  </notes>
</story>

<story id="STORY-007" status="done" complexity="M" tdd="required">
  <title>Database schema + TimescaleDB hypertable</title>
  <dependencies>STORY-006</dependencies>
  <description>
    Create SQLAlchemy models for p1_samples table, Alembic migration to create the table
    and TimescaleDB hypertable, and database session management.
  </description>
  <acceptance_criteria>
    <ac id="AC1">models.py defines P1Sample model matching technicaldesign.md schema</ac>
    <ac id="AC2">Alembic migration creates p1_samples table with (device_id, ts) PK</ac>
    <ac id="AC3">Migration enables TimescaleDB extension and creates hypertable</ac>
    <ac id="AC4">session.py provides async engine and session factory</ac>
    <ac id="AC5">Session is injectable via FastAPI Depends()</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>vps/src/db/models.py</file>
    <file>vps/src/db/session.py</file>
    <file>vps/src/db/migrations/env.py</file>
    <file>vps/src/db/migrations/versions/001_initial_schema.py</file>
    <file>vps/src/api/deps.py</file>
    <file>vps/tests/test_models.py</file>
  </allowed_scope>
  <test_first>
    <item>Create vps/tests/test_models.py FIRST</item>
    <item>Test: P1Sample model has correct columns and types</item>
    <item>Test: composite PK on (device_id, ts)</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>
  <test_plan>
    - Unit tests for model definition (column names, types, PK)
    - Migration script review (manual — verify SQL)
    - pytest vps/tests/ -q all pass
  </test_plan>
  <notes>
    - Schema from technicaldesign.md / project_idea.md section 6
    - TimescaleDB: CREATE EXTENSION, create_hypertable('p1_samples', 'ts')
  </notes>
</story>

<story id="STORY-008" status="done" complexity="S" tdd="required">
  <title>Device authentication (Bearer tokens)</title>
  <dependencies>STORY-006</dependencies>
  <description>
    Implement Bearer token validation middleware for the VPS API. Valid tokens are
    configured via DEVICE_TOKENS env var (comma-separated). Invalid/missing tokens
    return 401.
  </description>
  <acceptance_criteria>
    <ac id="AC1">bearer.py validates Authorization: Bearer {token} header</ac>
    <ac id="AC2">Valid token passes; request continues with device_id context</ac>
    <ac id="AC3">Missing or invalid token returns 401 Unauthorized</ac>
    <ac id="AC4">Tokens loaded from DEVICE_TOKENS env var at startup</ac>
    <ac id="AC5">Auth dependency injectable via FastAPI Depends()</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>vps/src/auth/bearer.py</file>
    <file>vps/src/api/deps.py</file>
    <file>vps/tests/test_auth.py</file>
  </allowed_scope>
  <test_first>
    <item>Create vps/tests/test_auth.py FIRST</item>
    <item>Test: valid token returns device context</item>
    <item>Test: invalid token returns 401</item>
    <item>Test: missing Authorization header returns 401</item>
    <item>Test: malformed header returns 401</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>
  <test_plan>
    - Unit tests for bearer validation function
    - Integration test via TestClient with auth header
    - pytest vps/tests/ -q all pass
  </test_plan>
  <notes>
    - DEVICE_TOKENS format: "token1:device1,token2:device2"
    - Constant-time comparison to prevent timing attacks
  </notes>
</story>

<story id="STORY-009" status="done" complexity="L" tdd="required">
  <title>Ingest API endpoint</title>
  <dependencies>STORY-007, STORY-008</dependencies>
  <description>
    Implement POST /v1/ingest endpoint that receives a batch of samples, validates with
    Pydantic, performs idempotent upsert into TimescaleDB, and invalidates Redis cache.
  </description>
  <acceptance_criteria>
    <ac id="AC1">POST /v1/ingest accepts {"samples": [...]} JSON body (wrapped object, not bare array)</ac>
    <ac id="AC2">Request body validated with Pydantic model</ac>
    <ac id="AC3">Requires valid Bearer token (uses auth dependency)</ac>
    <ac id="AC4">Performs INSERT ON CONFLICT DO NOTHING (idempotent)</ac>
    <ac id="AC5">Returns 200 with {"inserted": N} where N = new rows (not duplicates)</ac>
    <ac id="AC6">Returns 401 on invalid/missing auth</ac>
    <ac id="AC7">Returns 422 on invalid request body (Pydantic validation error)</ac>
    <ac id="AC8">All sample device_id values must match authenticated device_id; reject 403 on mismatch</ac>
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
    <item>Create vps/tests/fixtures/sample_data.json with mock batches</item>
    <item>Mock AsyncSession for DB operations</item>
    <item>Mock Redis client for cache invalidation assertions</item>
    <item>Test: valid batch returns 200 with insert count</item>
    <item>Test: duplicate samples do not error (idempotent)</item>
    <item>Test: invalid body returns 422</item>
    <item>Test: missing auth returns 401</item>
    <item>Test: sample device_id differs from authenticated device_id returns 403</item>
    <item>Test: successful ingest deletes Redis key "realtime:{device_id}"</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>
  <test_plan>
    - Unit tests for ingestion service with mocked session
    - Integration tests via TestClient with mocked DB + Redis
    - Idempotency test: send same batch twice, verify no duplicates
    - Device integrity test: device_id mismatch returns 403
    - Cache invalidation test: assert Redis delete called with "realtime:{device_id}" on success
    - pytest vps/tests/ -q all pass
  </test_plan>
  <notes>
    - Use SQLAlchemy insert().on_conflict_do_nothing()
    - Pydantic model: SampleCreate with device_id, ts, power_w, import_power_w, energy_import_kwh, energy_export_kwh
    - Batch endpoint: {"samples": [...]}
  </notes>
</story>

</phase>

<!-- ============================================================ -->
<!-- PHASE 3: API Features                                         -->
<!-- Story file: docs/stories/phase-3-api-features.md              -->
<!-- ============================================================ -->

<phase id="3" name="API Features" story_file="docs/stories/phase-3-api-features.md">

<story id="STORY-010" status="done" complexity="M" tdd="required">
  <title>Realtime metrics endpoint</title>
  <dependencies>STORY-009</dependencies>
  <description>
    Implement GET /v1/realtime endpoint that returns the latest power reading for a device.
    Redis-cached with configurable TTL for sub-100ms response times.
  </description>
  <acceptance_criteria>
    <ac id="AC1">GET /v1/realtime?device_id={id} returns latest sample</ac>
    <ac id="AC2">Response JSON: {device_id, ts, power_w, import_power_w, energy_import_kwh, energy_export_kwh}</ac>
    <ac id="AC3">Redis cache hit returns in &lt;100ms</ac>
    <ac id="AC4">Cache miss queries TimescaleDB, caches result</ac>
    <ac id="AC5">Cache invalidated on new ingest for that device</ac>
    <ac id="AC6">Returns 404 if no data for device</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>vps/src/api/realtime.py</file>
    <file>vps/src/cache/redis_client.py</file>
    <file>vps/tests/test_realtime.py</file>
  </allowed_scope>
  <test_first>
    <item>Create vps/tests/test_realtime.py FIRST</item>
    <item>Mock Redis client and AsyncSession</item>
    <item>Test: cache hit returns cached value</item>
    <item>Test: cache miss queries DB, caches result</item>
    <item>Test: unknown device returns 404</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>
  <test_plan>
    - Unit tests with mocked Redis and DB
    - Verify cache-first behavior
    - pytest vps/tests/ -q all pass
  </test_plan>
  <notes>
    - Cache key: "realtime:{device_id}"
    - TTL from config.CACHE_TTL_S (default 5s)
  </notes>
</story>

<story id="STORY-011" status="done" complexity="L" tdd="required">
  <title>Capacity tariff calculation (kwartierpiek)</title>
  <dependencies>STORY-009</dependencies>
  <description>
    Implement GET /v1/capacity/month/{month} endpoint that returns the Belgian capacity
    tariff metrics: all 15-minute average power values for the month and the monthly peak
    (highest 15-min average). Rolling 12-month peak is deferred to a future story.
  </description>
  <acceptance_criteria>
    <ac id="AC1">GET /v1/capacity/month/{month}?device_id={id} returns 15-minute peaks for given month and device</ac>
    <ac id="AC2">Each 15-min window: average of import_power_w samples in that window</ac>
    <ac id="AC3">Monthly peak: highest 15-min average in the month</ac>
    <ac id="AC4">Response includes: month, device_id, peaks array, monthly_peak_w, monthly_peak_ts</ac>
    <ac id="AC5">Uses TimescaleDB time_bucket('15 minutes', ts) for efficient calculation</ac>
    <ac id="AC6">Returns 400 for invalid month format (expected: YYYY-MM)</ac>
    <ac id="AC7">Month with no data returns 200 with peaks=[], monthly_peak_w=null, monthly_peak_ts=null</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>vps/src/api/capacity.py</file>
    <file>vps/src/services/capacity.py</file>
    <file>vps/tests/test_capacity.py</file>
  </allowed_scope>
  <test_first>
    <item>Create vps/tests/test_capacity.py FIRST</item>
    <item>Mock AsyncSession with predefined time_bucket results</item>
    <item>Test: correct 15-min averages from sample data</item>
    <item>Test: monthly peak is max of 15-min averages</item>
    <item>Test: invalid month format returns 400</item>
    <item>Test: month with no data returns empty peaks</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>
  <test_plan>
    - Unit tests for capacity service with fixture data
    - Verify 15-min bucketing logic
    - Verify peak calculation accuracy
    - pytest vps/tests/ -q all pass
  </test_plan>
  <notes>
    - Belgian capacity tariff: based on highest 15-minute average kW in a month
    - SQL: SELECT time_bucket('15 minutes', ts) AS bucket, AVG(import_power_w) AS avg_power
    - Month format: YYYY-MM (e.g., "2026-01")
  </notes>
</story>

<story id="STORY-012" status="done" complexity="L" tdd="required">
  <title>Historical series endpoint</title>
  <dependencies>STORY-009</dependencies>
  <description>
    Implement GET /v1/series endpoint with configurable time frames and aggregation:
    day → hourly, month → weekly, year → monthly, all → monthly.
  </description>
  <acceptance_criteria>
    <ac id="AC1">GET /v1/series?device_id={id}&amp;frame={frame} returns aggregated data</ac>
    <ac id="AC2">frame=day: hourly aggregation for today</ac>
    <ac id="AC3">frame=month: weekly aggregation for current month</ac>
    <ac id="AC4">frame=year: monthly aggregation for current year</ac>
    <ac id="AC5">frame=all: monthly aggregation for all time</ac>
    <ac id="AC6">Each bucket: avg_power_w, max_power_w, energy_import_kwh, energy_export_kwh</ac>
    <ac id="AC7">Returns 400 for invalid frame parameter</ac>
    <ac id="AC8">No data in range returns 200 with empty series array</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>vps/src/api/series.py</file>
    <file>vps/src/services/aggregation.py</file>
    <file>vps/tests/test_series.py</file>
  </allowed_scope>
  <test_first>
    <item>Create vps/tests/test_series.py FIRST</item>
    <item>Mock AsyncSession with predefined aggregation results</item>
    <item>Test: each frame returns correct time_bucket interval</item>
    <item>Test: invalid frame returns 400</item>
    <item>Test: empty result returns empty series</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>
  <test_plan>
    - Unit tests for aggregation service with mocked DB
    - Verify each frame maps to correct time_bucket interval
    - pytest vps/tests/ -q all pass
  </test_plan>
  <notes>
    - Uses TimescaleDB time_bucket() for efficient aggregation
    - Redis caching for frequently-accessed frames
    - frame parameter: "day", "month", "year", "all"
  </notes>
</story>

<story id="STORY-013" status="pending" complexity="M" tdd="recommended">
  <title>TimescaleDB continuous aggregates</title>
  <dependencies>STORY-007, STORY-012</dependencies>
  <description>
    Create TimescaleDB continuous aggregate materialized views for hourly, daily, and
    monthly rollups. This replaces on-the-fly aggregation queries with pre-computed views.
  </description>
  <acceptance_criteria>
    <ac id="AC1">Alembic migration creates hourly continuous aggregate</ac>
    <ac id="AC2">Alembic migration creates daily continuous aggregate</ac>
    <ac id="AC3">Alembic migration creates monthly continuous aggregate</ac>
    <ac id="AC4">aggregation.py queries continuous aggregates instead of raw table</ac>
    <ac id="AC5">Continuous aggregates auto-refresh on new data</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>vps/src/db/migrations/versions/002_continuous_aggregates.py</file>
    <file>vps/src/services/aggregation.py</file>
    <file>vps/tests/test_series.py</file>
  </allowed_scope>
  <test_plan>
    - Migration script review (verify continuous aggregate SQL)
    - Aggregation service now queries views
    - pytest vps/tests/ -q all pass
  </test_plan>
  <notes>
    - TimescaleDB continuous aggregates: CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous)
    - Refresh policy: timescaledb.add_continuous_aggregate_policy
  </notes>
</story>

</phase>

<!-- ============================================================ -->
<!-- PHASE 4: Production Readiness (Post-MVP)                      -->
<!-- Story file: (inline — small phase)                            -->
<!-- ============================================================ -->

<phase id="4" name="Production Readiness">

<story id="STORY-014" status="pending" complexity="M" tdd="recommended">
  <title>Health checks and monitoring</title>
  <dependencies>STORY-005, STORY-009</dependencies>
  <description>
    Add health check endpoints for both edge and VPS, and basic monitoring/logging.
  </description>
  <acceptance_criteria>
    <ac id="AC1">VPS: GET /health returns status of DB, Redis connections</ac>
    <ac id="AC2">Edge: health check reports P1 connectivity, spool depth, last upload time</ac>
    <ac id="AC3">Docker Compose healthcheck configured for both services</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>vps/src/api/health.py</file>
    <file>edge/src/health.py</file>
    <file>vps/tests/test_health.py</file>
    <file>edge/tests/test_health.py</file>
    <file>docker-compose.edge.yml</file>
    <file>docker-compose.vps.yml</file>
  </allowed_scope>
  <test_plan>
    - Unit tests for health check logic
    - pytest all pass
  </test_plan>
  <notes>
    - Docker HEALTHCHECK for auto-restart on failure
  </notes>
</story>

<story id="STORY-015" status="pending" complexity="M" tdd="recommended">
  <title>Production hardening</title>
  <dependencies>STORY-005, STORY-009</dependencies>
  <description>
    Structured logging, graceful shutdown handlers, proper signal handling for Docker.
  </description>
  <acceptance_criteria>
    <ac id="AC1">Structured JSON logging in both edge and VPS</ac>
    <ac id="AC2">Graceful shutdown: edge flushes pending uploads before exit</ac>
    <ac id="AC3">Graceful shutdown: VPS completes in-flight requests before exit</ac>
    <ac id="AC4">SIGTERM/SIGINT handlers registered</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>edge/src/main.py</file>
    <file>edge/src/logging_config.py</file>
    <file>vps/src/main.py</file>
    <file>vps/src/logging_config.py</file>
    <file>edge/tests/test_main.py</file>
    <file>vps/tests/test_main.py</file>
  </allowed_scope>
  <test_plan>
    - Unit tests for signal handling
    - pytest all pass
  </test_plan>
  <notes>
    - Use Python stdlib logging with JSON formatter
    - Docker: STOPSIGNAL SIGTERM in Dockerfile
  </notes>
</story>

</phase>

<!-- ============================================================ -->
<!-- PROGRESS OVERVIEW                                             -->
<!-- ============================================================ -->

<progress>
  <phase_summary>
    <phase id="1" name="Edge Foundation" stories="5" done="5" progress="100%" link="stories/phase-1-edge-foundation.md" />
    <phase id="2" name="VPS Foundation" stories="4" done="4" progress="100%" link="stories/phase-2-vps-foundation.md" />
    <phase id="3" name="API Features" stories="4" done="3" progress="75%" link="stories/phase-3-api-features.md" />
    <phase id="4" name="Production Readiness" stories="2" done="0" progress="0%" />
  </phase_summary>
  <total stories="15" done="12" progress="80%" />
</progress>

<!-- ============================================================ -->
<!-- DEPENDENCY GRAPH                                              -->
<!-- ============================================================ -->

<dependency_graph>
<!--
STORY-001 (Edge scaffolding)
├── STORY-002 (P1 poller)
│   └── STORY-005 (Batch uploader)
├── STORY-003 (Normalizer)
│   └── STORY-005 (Batch uploader)
└── STORY-004 (SQLite spool)
    └── STORY-005 (Batch uploader)
        ├── STORY-014 (Health checks)
        └── STORY-015 (Production hardening)

STORY-006 (VPS scaffolding)
├── STORY-007 (DB schema + TimescaleDB)
│   ├── STORY-009 (Ingest API)
│   └── STORY-013 (Continuous aggregates)
└── STORY-008 (Device auth)
    └── STORY-009 (Ingest API)
        ├── STORY-010 (Realtime endpoint)
        ├── STORY-011 (Capacity tariff)
        ├── STORY-012 (Historical series)
        │   └── STORY-013 (Continuous aggregates)
        ├── STORY-014 (Health checks)
        └── STORY-015 (Production hardening)

Note: STORY-001 and STORY-006 have no dependencies and can be parallelized.
      STORY-002, STORY-003, STORY-004 can be parallelized (all depend only on STORY-001).
      STORY-007 and STORY-008 can be parallelized (both depend only on STORY-006).
-->
</dependency_graph>

<!-- ============================================================ -->
<!-- BLOCKED STORIES                                               -->
<!-- ============================================================ -->

<blocked>
</blocked>

<!-- ============================================================ -->
<!-- PARKING LOT                                                   -->
<!-- ============================================================ -->

<parking_lot>
  <idea>Dashboard web UI for realtime monitoring</idea>
  <idea>Multi-device support (multiple P1 meters)</idea>
  <idea>Push notifications when monthly capacity peak is approaching threshold</idea>
  <idea>Historical data export (CSV, JSON)</idea>
  <idea>Automated capacity tariff cost calculation based on provider rates</idea>
  <idea>Grafana integration for advanced visualization</idea>
</parking_lot>

<!-- ============================================================ -->
<!-- LABELS REFERENCE                                              -->
<!-- ============================================================ -->

<labels>
  <label name="foundation">Core infrastructure and scaffolding</label>
  <label name="feature">New functionality</label>
  <label name="api">API endpoint</label>
  <label name="edge">Edge daemon component</label>
  <label name="vps">VPS component</label>
  <label name="database">Database schema or migration</label>
  <label name="mvp">Required for MVP</label>
  <label name="post-mvp">Post-MVP feature</label>
</labels>

</backlog>
