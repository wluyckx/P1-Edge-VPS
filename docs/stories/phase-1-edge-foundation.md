# Phase 1: Edge Foundation

**Status**: Not Started
**Stories**: 5
**Completed**: 5
**Depends On**: None

---

## Phase Completion Criteria

This phase is complete when:
- [ ] All stories have status "done"
- [ ] All tests passing (`pytest edge/tests/ -q`)
- [ ] Lint clean (`ruff check edge/src/`)
- [ ] Documentation updated
- [ ] Edge daemon can poll P1, normalize, buffer, and upload a batch end-to-end

---

## Stories

<story id="STORY-001" status="done" complexity="S" tdd="recommended">
  <title>Edge project scaffolding</title>
  <dependencies>None</dependencies>

  <description>
    Set up the edge project directory structure, configuration module (Pydantic BaseSettings),
    pyproject.toml, requirements.txt, Dockerfile, and docker-compose.edge.yml. This is the
    foundation for all edge development — every other edge story depends on it.
  </description>

  <acceptance_criteria>
    <ac id="AC1">edge/src/ directory exists with __init__.py and config.py</ac>
    <ac id="AC2">config.py uses Pydantic BaseSettings with all env vars from Architecture.md:
      HW_P1_HOST, HW_P1_TOKEN, VPS_INGEST_URL, VPS_DEVICE_TOKEN, POLL_INTERVAL_S (default 2),
      BATCH_SIZE (default 30), UPLOAD_INTERVAL_S (default 10)</ac>
    <ac id="AC3">edge/tests/ directory exists with __init__.py and conftest.py</ac>
    <ac id="AC4">requirements.txt lists: httpx, pydantic, pydantic-settings</ac>
    <ac id="AC5">Dockerfile builds Python 3.12 image, installs deps, runs main.py</ac>
    <ac id="AC6">docker-compose.edge.yml matches Architecture.md spec (env vars, volume for /data)</ac>
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
    - Unit test: config loads from env vars with correct defaults
    - Unit test: config validation rejects missing required vars (HW_P1_HOST, etc.)
    - `pytest edge/tests/ -q` all pass
  </test_plan>

  <notes>
    - Use Pydantic BaseSettings for automatic env var loading
    - .env.example documents all variables (never contains real values)
    - Docker volume: p1_edge_data:/data (for SQLite spool persistence)
  </notes>
</story>

---

<story id="STORY-002" status="done" complexity="M" tdd="required">
  <title>HomeWizard P1 poller</title>
  <dependencies>STORY-001</dependencies>

  <description>
    Implement the HTTP poller that reads from the HomeWizard P1 meter's Local API v2
    endpoint. The P1 meter exposes a local HTTP API at /api/measurement that returns
    real-time power and energy readings as JSON. The poller must handle network errors
    gracefully — the poll loop must never crash.

    HomeWizard P1 Local API v2:
    - Endpoint: GET http://{host}/api/measurement
    - Auth: Authorization: Bearer {token}
    - Response: JSON with power_w, energy_import_kwh, energy_export_kwh, and more
  </description>

  <acceptance_criteria>
    <ac id="AC1">poller.py sends HTTP GET with Bearer token to {HW_P1_HOST}/api/measurement</ac>
    <ac id="AC2">Returns parsed JSON dict on 200 OK</ac>
    <ac id="AC3">Returns None and logs warning on connection error (no crash)</ac>
    <ac id="AC4">Returns None and logs warning on HTTP error status (4xx, 5xx)</ac>
    <ac id="AC5">Configurable timeout (default 5s)</ac>
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
    <item>Test: connection error returns None (no exception raised)</item>
    <item>Test: HTTP 500 returns None (no exception raised)</item>
    <item>Test: timeout returns None (no exception raised)</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>

  <test_plan>
    - Unit tests with mocked httpx.Client
    - Fixture-based responses: success, HTTP error, connection error, timeout
    - `pytest edge/tests/ -q` all pass
  </test_plan>

  <notes>
    - Use httpx (sync) — edge daemon is a simple loop, no need for async
    - Fixture JSON example: {"power_w": 450, "energy_import_kwh": 1234.567, ...}
    - Log at WARNING level on errors (not ERROR — transient failures are expected)
  </notes>
</story>

---

<story id="STORY-003" status="done" complexity="S" tdd="required">
  <title>Measurement normalizer</title>
  <dependencies>STORY-001</dependencies>

  <description>
    Pure function that takes the raw HomeWizard measurement dict and returns a normalized
    sample dict matching the p1_samples database schema. The normalizer must not call
    datetime.now() — it accepts a timestamp parameter for testability.
  </description>

  <acceptance_criteria>
    <ac id="AC1">normalizer.py exports normalize(raw: dict, device_id: str, ts: datetime) -> dict</ac>
    <ac id="AC2">Output keys: device_id, ts (ISO 8601 UTC), power_w, import_power_w,
      energy_import_kwh, energy_export_kwh</ac>
    <ac id="AC3">import_power_w = max(power_w, 0) (never negative)</ac>
    <ac id="AC4">Raises ValueError on missing required fields in raw input</ac>
    <ac id="AC5">ts parameter allows injectable timestamp (no internal datetime.now() calls)</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>edge/src/normalizer.py</file>
    <file>edge/tests/test_normalizer.py</file>
  </allowed_scope>

  <test_first>
    <item>Create edge/tests/test_normalizer.py FIRST</item>
    <item>Test: valid input → correct normalized output with all fields</item>
    <item>Test: negative power_w → import_power_w is 0</item>
    <item>Test: zero power_w → import_power_w is 0</item>
    <item>Test: positive power_w → import_power_w equals power_w</item>
    <item>Test: missing "power_w" in raw → raises ValueError</item>
    <item>Test: ts is the provided timestamp, not generated internally</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>

  <test_plan>
    - Unit tests with hand-crafted input/output pairs
    - Edge cases: negative power, zero values, missing fields
    - `pytest edge/tests/ -q` all pass
  </test_plan>

  <notes>
    - Pure function — no side effects, no I/O, no state
    - Ref Architecture.md Time-Dependent Testing: accept ts as parameter
    - Raw dict keys from HomeWizard: "power_w", "energy_import_kwh", "energy_export_kwh"
  </notes>
</story>

---

<story id="STORY-004" status="done" complexity="M" tdd="required">
  <title>SQLite spool (local buffer)</title>
  <dependencies>STORY-001</dependencies>

  <description>
    Durable local queue using SQLite. This is the critical component for HC-001 (No Data Loss).
    Samples are written to the spool before any upload attempt. They are only deleted after
    server acknowledgment. The spool must survive process restarts.

    Operations: enqueue (write), peek (read batch without deleting), ack (delete confirmed),
    count (pending total).
  </description>

  <acceptance_criteria>
    <ac id="AC1">spool.py creates SQLite DB with WAL mode at configurable path</ac>
    <ac id="AC2">enqueue(sample: dict) inserts a normalized sample row</ac>
    <ac id="AC3">peek(n: int) returns up to n oldest samples with their rowids (FIFO)</ac>
    <ac id="AC4">ack(rowids: list[int]) deletes only the specified rows</ac>
    <ac id="AC5">count() returns number of pending samples</ac>
    <ac id="AC6">Spool DB file persists across process restarts</ac>
    <ac id="AC7">Table schema: rowid (auto), device_id TEXT, ts TEXT, power_w INTEGER,
      import_power_w INTEGER, energy_import_kwh REAL, energy_export_kwh REAL</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>edge/src/spool.py</file>
    <file>edge/tests/test_spool.py</file>
  </allowed_scope>

  <test_first>
    <item>Create edge/tests/test_spool.py FIRST</item>
    <item>Use pytest tmp_path fixture for isolated SQLite files</item>
    <item>Test: enqueue + peek returns the sample with correct data</item>
    <item>Test: ack(rowids) removes only those rows, rest remain</item>
    <item>Test: peek returns oldest first (FIFO ordering)</item>
    <item>Test: count reflects actual pending count after enqueue/ack</item>
    <item>Test: peek on empty spool returns empty list</item>
    <item>Test: multiple enqueues maintain insertion order</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>

  <test_plan>
    - Unit tests with real SQLite on tmp_path (not mocked — SQLite is fast and deterministic)
    - FIFO ordering verification with multiple samples
    - Partial ack: enqueue 5, ack 3, verify 2 remain
    - `pytest edge/tests/ -q` all pass
  </test_plan>

  <notes>
    - WAL mode: `PRAGMA journal_mode=WAL;` for concurrent read/write
    - Use rowid as the handle for ack (SQLite auto-generated)
    - Path from config: default /data/spool.db (Docker volume mount)
  </notes>
</story>

---

<story id="STORY-005" status="done" complexity="L" tdd="required">
  <title>Batch uploader with retry</title>
  <dependencies>STORY-002, STORY-003, STORY-004</dependencies>

  <description>
    The batch uploader reads pending samples from the spool, POSTs them as a JSON batch
    to the VPS ingest endpoint, and acks confirmed samples. On failure, it retries with
    exponential backoff. This story also creates the main.py entry point that ties the
    poll loop and upload loop together.

    Critical: samples must NEVER be deleted from spool without server confirmation (HC-001).
  </description>

  <acceptance_criteria>
    <ac id="AC1">uploader.py reads batch from spool via peek(batch_size)</ac>
    <ac id="AC2">POSTs batch as JSON to {VPS_INGEST_URL}/v1/ingest with Bearer token header</ac>
    <ac id="AC3">On 2xx response: acks the uploaded rowids from spool</ac>
    <ac id="AC4">On failure (network error, non-2xx): does NOT ack, retries with backoff</ac>
    <ac id="AC5">Exponential backoff: 1s → 2s → 4s → 8s → ... → max (default 300s)</ac>
    <ac id="AC6">Backoff resets to 1s on successful upload</ac>
    <ac id="AC7">Uploader validates VPS_INGEST_URL is HTTPS at startup; rejects HTTP (HC-003)</ac>
    <ac id="AC8">TLS certificate verification enabled (verify=True); never disabled in production</ac>
    <ac id="AC9">main.py runs poll loop (poll → normalize → enqueue) + upload loop</ac>
    <ac id="AC10">Empty spool: upload cycle is a no-op (no HTTP request)</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>edge/src/uploader.py</file>
    <file>edge/src/main.py</file>
    <file>edge/tests/test_uploader.py</file>
  </allowed_scope>

  <test_first>
    <item>Create edge/tests/test_uploader.py FIRST</item>
    <item>Mock httpx.Client for VPS responses (2xx, 5xx, connection error)</item>
    <item>Mock spool for peek/ack calls</item>
    <item>Test: successful upload (2xx) → acks rowids</item>
    <item>Test: failed upload (5xx) → does NOT ack</item>
    <item>Test: connection error → does NOT ack</item>
    <item>Test: exponential backoff delay sequence (1, 2, 4, 8, ...)</item>
    <item>Test: backoff resets after success</item>
    <item>Test: empty spool → no HTTP request made</item>
    <item>Test: VPS_INGEST_URL with http:// scheme → rejected at startup (HC-003)</item>
    <item>Test: TLS verify=True by default (not overridable to False)</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>

  <test_plan>
    - Unit tests with mocked HTTP client and mocked spool
    - Verify ack called only on 2xx
    - Verify no ack on any failure
    - Verify backoff delay calculation
    - Verify HTTPS enforcement (HC-003)
    - `pytest edge/tests/ -q` all pass
  </test_plan>

  <notes>
    - Backoff formula: min(base * 2^attempt, max_backoff)
    - Default base=1s, max=300s
    - main.py: two async/threaded loops — poll at POLL_INTERVAL_S, upload at UPLOAD_INTERVAL_S
    - main.py can use simple time.sleep() loops (no asyncio needed for edge)
    - CONTRACT DEPENDENCY: Uploader builds the canonical ingest payload defined in
      technicaldesign.md § Ingest API: POST /v1/ingest with {"samples": [...]}.
      Edge can be developed in parallel with VPS by coding against this contract.
      The test fixture in edge/tests/fixtures/ must match the schema.
      If STORY-009 changes the contract, STORY-005 must be updated to match.
  </notes>
</story>

---

## Phase Notes

### Dependencies on Other Phases
- Phase 2 (VPS Foundation) can be developed in parallel — STORY-006 has no edge dependencies
- Phase 1 + Phase 2 both complete before end-to-end integration testing

### Known Risks
- HomeWizard P1 Local API v2 may have undocumented response fields: handle gracefully
- SQLite WAL mode: ensure Docker volume supports WAL (most do, but verify)

### Technical Debt
- None expected at this phase (it's the foundation)
