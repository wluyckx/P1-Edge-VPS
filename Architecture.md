# Architecture.md — P1-Edge-VPS Energy Telemetry Platform

**Last Updated**: 2026-02-13

---

## Overview

A production-grade telemetry pipeline that synchronizes real-time energy readings from a
HomeWizard P1 meter (LAN) to a secure cloud VPS. The system provides real-time power metrics,
Belgian capacity tariff calculations (15-minute kwartierpiek + monthly peak), historical
aggregated series, robust local buffering during outages, and a Redis-backed low-latency
public API.

**Primary Goal**: Reliable, zero-data-loss energy telemetry with accurate capacity tariff
tracking and sub-100ms API response times.

---

## Tech Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Language | Python | 3.12+ | Primary language for both edge and VPS |
| Edge HTTP Client | httpx | latest | Poll HomeWizard P1 meter, upload batches to VPS |
| VPS Framework | FastAPI | latest | Async REST API framework with auto-generated OpenAPI docs |
| VPS ASGI Server | uvicorn | latest | Production ASGI server for FastAPI |
| Edge Local Storage | SQLite | stdlib | Local sample spool/buffer (zero-config, durable) |
| VPS Database | PostgreSQL + TimescaleDB | 16 / latest | Time-series hypertable storage with continuous aggregates |
| VPS Cache | Redis | 7-alpine | Low-latency cache for realtime and series endpoints |
| VPS ORM | SQLAlchemy | 2.x | Async database models, queries, session management |
| VPS DB Driver | asyncpg | latest | High-performance async PostgreSQL driver |
| VPS Redis Client | redis-py | latest | Async Redis client |
| Reverse Proxy | Caddy | 2 | Auto-HTTPS, TLS termination, reverse proxy |
| Containerization | Docker + Compose | latest | Deployment and orchestration |
| Testing | pytest | latest | Test framework for both edge and VPS |
| Async Testing | pytest-asyncio | latest | Async test support for FastAPI/asyncpg |
| HTTP Testing | httpx (AsyncClient) | latest | FastAPI TestClient for integration tests |
| Mocking | pytest-mock | latest | Mock framework for external dependencies |
| Linting | ruff | latest | Fast Python linter and import sorter |
| Formatting | ruff format | latest | Code formatting (Black-compatible) |
| Validation | Pydantic | 2.x | Request/response validation (bundled with FastAPI) |
| DB Migrations | Alembic | latest | Database schema migrations |

### Dependencies NOT in Tech Stack (Forbidden Without ADR)
Any package not listed above requires an Architecture Proposal before use.

---

## Directory Structure

```
P1-Edge-VPS/
├── CLAUDE.md                           # Agent workflow rules (highest authority)
├── Architecture.md                     # This file — system design reference
├── technicaldesign.md                  # Detailed schemas, API specs, validation rules
├── SKILL.md                            # VibeSec security guidelines
├── docs/
│   ├── BACKLOG.md                      # Stories and requirements (XML format)
│   ├── project_idea.md                 # Original project concept
│   ├── PROJECT_START.md                # Bootstrap guide
│   ├── stories/                        # Detailed story files per phase
│   │   ├── phase-1-edge-foundation.md
│   │   ├── phase-2-vps-foundation.md
│   │   └── phase-3-api-features.md
│   └── templates/                      # Governance templates (reference)
├── edge/
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py                     # Edge daemon entry point (poll loop)
│   │   ├── config.py                   # Configuration from environment variables
│   │   ├── poller.py                   # HomeWizard P1 HTTP polling
│   │   ├── normalizer.py              # Measurement normalization and validation
│   │   ├── spool.py                    # SQLite local buffer (write/read/delete)
│   │   └── uploader.py                # Batch upload to VPS with retry + backoff
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                 # Shared fixtures
│   │   ├── test_config.py
│   │   ├── test_poller.py
│   │   ├── test_normalizer.py
│   │   ├── test_spool.py
│   │   ├── test_uploader.py
│   │   └── fixtures/
│   │       └── hw_responses.json       # HomeWizard P1 API mock responses
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml
├── vps/
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI app entry point
│   │   ├── config.py                   # Configuration from environment variables
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py                 # Dependency injection (DB session, Redis, auth)
│   │   │   ├── ingest.py              # POST /v1/ingest — batch sample ingestion
│   │   │   ├── realtime.py            # GET /v1/realtime — latest power reading
│   │   │   ├── capacity.py            # GET /v1/capacity/month/{month} — kwartierpiek
│   │   │   └── series.py             # GET /v1/series — historical aggregated data
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   └── bearer.py             # Bearer token validation middleware
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── models.py             # SQLAlchemy ORM models (p1_samples, etc.)
│   │   │   ├── session.py            # Async engine + session factory
│   │   │   └── migrations/           # Alembic migrations directory
│   │   │       ├── env.py
│   │   │       └── versions/
│   │   ├── cache/
│   │   │   ├── __init__.py
│   │   │   └── redis_client.py       # Redis connection + cache helpers
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── ingestion.py          # Idempotent upsert logic
│   │       ├── capacity.py           # 15-min kwartierpiek + monthly peak calculation
│   │       └── aggregation.py        # Time-series rollup queries
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                # Shared fixtures (TestClient, mock DB, mock Redis)
│   │   ├── test_ingest.py
│   │   ├── test_realtime.py
│   │   ├── test_capacity.py
│   │   ├── test_series.py
│   │   ├── test_auth.py
│   │   └── fixtures/
│   │       └── sample_data.json       # Sample measurement data for tests
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml
├── docker-compose.edge.yml             # Edge deployment compose
├── docker-compose.vps.yml              # VPS deployment compose (API + Postgres + Redis + Caddy)
├── Caddyfile                           # Caddy reverse proxy configuration
├── .env.example                        # Template for environment variables
└── .gitignore
```

---

## Key Components

### 1. Edge Poller
- **Location**: `edge/src/poller.py`
- **Responsibility**: Polls HomeWizard P1 meter at configurable interval via HTTP
- **Protocol**: HTTP GET to `http://{HW_P1_HOST}/api/measurement` (Local API v2, bearer token auth)
- **Dependencies**: httpx, config

### 2. Edge Normalizer
- **Location**: `edge/src/normalizer.py`
- **Responsibility**: Validates and normalizes raw HomeWizard readings into canonical format
- **Dependencies**: None (pure function)

### 3. Edge Spool (SQLite Buffer)
- **Location**: `edge/src/spool.py`
- **Responsibility**: Durable local queue — writes samples before upload, deletes only after confirmation
- **Protocol**: SQLite WAL mode for concurrent read/write
- **Dependencies**: sqlite3 (stdlib)

### 4. Edge Uploader
- **Location**: `edge/src/uploader.py`
- **Responsibility**: Batch-uploads samples from spool to VPS ingest endpoint with retry + exponential backoff
- **Protocol**: HTTPS POST to `{VPS_INGEST_URL}/v1/ingest` with Bearer token
- **Dependencies**: httpx, spool, config

### 5. VPS Ingest API
- **Location**: `vps/src/api/ingest.py`
- **Responsibility**: Receives batches, validates, performs idempotent upsert into TimescaleDB
- **Protocol**: POST /v1/ingest with JSON body, Bearer auth
- **Dependencies**: FastAPI, SQLAlchemy, asyncpg, auth

### 6. VPS Capacity Service
- **Location**: `vps/src/services/capacity.py`
- **Responsibility**: Calculates Belgian 15-minute kwartierpiek and monthly peak from raw samples
- **Dependencies**: SQLAlchemy, TimescaleDB time_bucket

### 7. VPS Cache Layer
- **Location**: `vps/src/cache/redis_client.py`
- **Responsibility**: Caches realtime readings and pre-computed series for sub-100ms responses
- **Dependencies**: redis-py

### 8. VPS Aggregation Service
- **Location**: `vps/src/services/aggregation.py`
- **Responsibility**: Queries continuous aggregates for historical series (hourly, weekly, monthly)
- **Dependencies**: SQLAlchemy, TimescaleDB continuous aggregates

---

## Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                         EDGE (Local LAN)                         │
│                                                                  │
│  HomeWizard P1     Edge Poller     Normalizer     SQLite Spool   │
│  ┌──────────┐     ┌──────────┐   ┌──────────┐   ┌──────────┐   │
│  │ /api/    │────>│ poll()   │──>│normalize()│──>│ enqueue()│   │
│  │measure-  │HTTP │          │   │          │   │          │   │
│  │ment     │     └──────────┘   └──────────┘   └────┬─────┘   │
│  └──────────┘                                        │          │
│                                              Batch Uploader      │
│                                              ┌──────────┐       │
│                                              │ upload() │       │
│                                              │ + retry  │       │
│                                              └────┬─────┘       │
└───────────────────────────────────────────────────┼──────────────┘
                                                    │
                                                  HTTPS
                                                    │
┌───────────────────────────────────────────────────┼──────────────┐
│                          VPS (Cloud)              │              │
│                                                   ▼              │
│  Caddy ──> FastAPI Ingest ──> TimescaleDB                       │
│  ┌─────┐   ┌──────────┐      ┌──────────┐    ┌──────────┐      │
│  │TLS  │──>│POST      │─────>│p1_samples│───>│Continuous│      │
│  │Term.│   │/v1/ingest│      │hypertable│    │Aggregates│      │
│  └─────┘   └──────────┘      └────┬─────┘    └──────────┘      │
│                                    │                             │
│              ┌─────────────────────┼─────────────┐              │
│              │                     │             │              │
│              ▼                     ▼             ▼              │
│  ┌────────────────┐   ┌────────────────┐  ┌──────────┐        │
│  │GET /v1/realtime│   │GET /v1/capacity│  │GET       │        │
│  │   (cached)     │   │  /month/{m}   │  │/v1/series│        │
│  └───────┬────────┘   └───────┬────────┘  └────┬─────┘        │
│          │                     │                │              │
│          └─────────┬───────────┴────────────────┘              │
│                    │                                            │
│               ┌────┴─────┐                                     │
│               │  Redis   │                                     │
│               │  Cache   │                                     │
│               └──────────┘                                     │
└──────────────────────────────────────────────────────────────────┘
```

### Flow: Measurement Ingestion (Edge → VPS)
1. Edge Poller sends HTTP GET to HomeWizard P1 `/api/measurement` every N seconds
2. Normalizer validates response and extracts `power_w`, `import_power_w`, `energy_import_kwh`, `energy_export_kwh`
3. Normalized sample written to SQLite spool with UTC timestamp
4. Batch Uploader reads pending samples from spool, POSTs batch to VPS `/v1/ingest`
5. VPS validates Bearer token, validates batch with Pydantic
6. VPS performs `INSERT ON CONFLICT DO NOTHING` (idempotent upsert) into TimescaleDB
7. VPS returns acknowledgment; Edge deletes confirmed samples from spool
8. Redis cache invalidated for affected device

### Flow: Realtime Query (Client → VPS)
1. Client sends GET `/v1/realtime?device_id={id}`
2. Redis cache checked first — on hit, return cached value (<100ms)
3. On miss, query latest row from TimescaleDB, cache result with short TTL
4. Return JSON response with latest power reading and timestamp

### Flow: Offline Resilience (Edge Buffering)
1. Edge Poller continues polling HomeWizard P1 regardless of VPS connectivity
2. All samples are always written to SQLite spool first (never fire-and-forget)
3. Uploader attempts batch upload — on failure, retries with exponential backoff
4. After reconnect, spool backlog is flushed in chronological batches
5. VPS idempotent upsert handles any duplicate submissions from retry

### Flow Characteristics
- **Reactive**: VPS cache invalidation on new ingestion; clients see fresh data within TTL
- **Offline-first**: Edge never depends on VPS availability for sample capture
- **Configurable**: Poll interval, batch size, retry parameters, cache TTL — all via env vars
- **Resilient**: Every layer handles its upstream being unavailable

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Edge local buffer | SQLite (WAL mode) | Reliable, zero-config, survives process/host restarts |
| Time-series storage | TimescaleDB | Purpose-built for time-series; continuous aggregates for rollups |
| API cache | Redis | Sub-millisecond reads for realtime endpoint target (<100ms) |
| API framework | FastAPI | Async-native, auto OpenAPI, Pydantic validation built-in |
| TLS termination | Caddy | Automatic HTTPS with Let's Encrypt, minimal configuration |
| Edge-to-VPS transport | HTTPS POST (batched) | Simple, reliable, firewall-friendly (outbound only from edge) |
| Authentication | Per-device Bearer token | Simple, stateless, sufficient for device auth |
| Idempotency key | (device_id, ts) composite PK | Natural dedup key — same measurement can't occur twice |
| Two-repo-in-one | Monorepo (edge/ + vps/) | Shared types, easier to manage stories and dependencies |
| Python for both | Python 3.12+ | Same language for edge and VPS reduces cognitive overhead |

---

## Integration Points

### Inputs

- **HomeWizard P1 Meter**:
  - Protocol: HTTP (local LAN only)
  - Endpoint: `http://{HW_P1_HOST}/api/measurement`
  - Auth: Bearer token (HomeWizard Local API v2)
  - Data: Real-time power (W), cumulative energy import/export (kWh)

### Outputs

- **Public REST API** (VPS):
  - Protocol: HTTPS
  - Base: `https://{VPS_DOMAIN}/v1/`
  - Auth: Bearer token (per-device)
  - Endpoints: `/ingest`, `/realtime`, `/capacity/month/{month}`, `/series`

---

## Development Patterns

### Repository Pattern (VPS)

```python
# Services receive DB session via FastAPI dependency injection
async def ingest_samples(
    session: AsyncSession,
    samples: list[SampleCreate],
) -> int:
    """Idempotent upsert — returns count of new rows inserted."""
    stmt = insert(P1Sample).values([s.model_dump() for s in samples])
    stmt = stmt.on_conflict_do_nothing(index_elements=["device_id", "ts"])
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount
```

### Error Handling
- Edge: Log errors, never crash the poll loop. Retry with exponential backoff for uploads.
- VPS API: Return structured error responses (RFC 7807 problem+json format).
- All exceptions caught at boundary layers; internal errors logged with context.

### Configuration
- Use `edge/src/config.py` and `vps/src/config.py` for env-var based configuration
- Use Pydantic `BaseSettings` for configuration validation at startup
- No hardcoded IPs, URLs, or secrets in code
- Environment-specific config via `.env` files (never committed) and Docker env

---

## Development Workflow

```bash
# Setup (edge)
cd edge && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Setup (vps)
cd vps && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Lint (must pass with zero warnings)
ruff check edge/src/ vps/src/

# Format (must pass)
ruff format --check edge/src/ vps/src/

# Test edge
pytest edge/tests/ -q

# Test VPS
pytest vps/tests/ -q

# Test all with coverage
pytest edge/tests/ vps/tests/ --cov=edge/src --cov=vps/src --cov-report=term-missing

# Run edge daemon (local dev)
cd edge && python -m src.main

# Run VPS API (local dev)
cd vps && uvicorn src.main:app --reload

# Docker build
docker compose -f docker-compose.edge.yml build
docker compose -f docker-compose.vps.yml build

# Docker run (VPS stack)
docker compose -f docker-compose.vps.yml up -d
```

---

## Testing Strategy

| Test Type | Location | Coverage Target | Tools |
|-----------|----------|-----------------|-------|
| Unit Tests (Edge) | `edge/tests/` | 90%+ | pytest, pytest-mock |
| Unit Tests (VPS) | `vps/tests/` | 90%+ | pytest, pytest-asyncio, pytest-mock |
| Integration (API) | `vps/tests/` | Key flows | httpx AsyncClient + TestClient |
| Fixtures (Edge) | `edge/tests/fixtures/` | Mock data | JSON files |
| Fixtures (VPS) | `vps/tests/fixtures/` | Mock data | JSON files |

### Test Requirements
- All tests must run without network access (mock HomeWizard P1, mock PostgreSQL, mock Redis)
- Edge spool tests may use real SQLite (in-memory or temp file)
- VPS API tests use FastAPI TestClient with mocked database sessions
- No tests may depend on real network access or real external services

### Mock Strategy
- HomeWizard P1 responses: JSON fixtures in `edge/tests/fixtures/hw_responses.json`
- PostgreSQL: Mock AsyncSession or use in-memory SQLite for simple ORM tests
- Redis: Mock redis-py client (fakeredis or pytest-mock)
- Time: Inject clock where time-dependent (capacity calculations, TTL)

### Time-Dependent Testing

Several features depend on clock time (polling intervals, 15-minute capacity windows, cache TTL).

| Feature | Time Dependency | Test Strategy |
|---------|----------------|---------------|
| Edge poll loop | Poll interval timer | Mock asyncio.sleep / time.sleep |
| Capacity calculation | 15-minute window boundaries | Inject fixed timestamps in test data |
| Cache TTL | Redis key expiry | Mock Redis with controllable expiry |
| Retry backoff | Exponential delay | Mock sleep, verify delay sequence |

**Pattern**: Use injectable timestamps in function signatures. Tests provide fixed timestamps.
Never call `datetime.now()` directly in business logic — accept `ts` as a parameter.

---

## Environment & Secrets

| Variable | Purpose | Component | Required |
|----------|---------|-----------|----------|
| `HW_P1_HOST` | HomeWizard P1 meter IP/hostname | Edge | Yes |
| `HW_P1_TOKEN` | HomeWizard P1 Local API bearer token | Edge | Yes |
| `VPS_INGEST_URL` | VPS base URL for ingestion | Edge | Yes |
| `VPS_DEVICE_TOKEN` | Per-device bearer token for VPS auth | Edge | Yes |
| `POLL_INTERVAL_S` | Seconds between P1 polls | Edge | No (default: 2) |
| `BATCH_SIZE` | Max samples per upload batch | Edge | No (default: 30) |
| `UPLOAD_INTERVAL_S` | Seconds between upload attempts | Edge | No (default: 10) |
| `DATABASE_URL` | PostgreSQL connection string | VPS | Yes |
| `REDIS_URL` | Redis connection string | VPS | Yes |
| `DEVICE_TOKENS` | Comma-separated valid device tokens | VPS | Yes |
| `CACHE_TTL_S` | Redis cache TTL in seconds | VPS | No (default: 5) |

**Security**: All secrets via environment variables or `.env` files, never in code.
`.env` files are in `.gitignore` and never committed.

---

## Operational Assumptions

1. **Runtime**: Python 3.12+, Docker 24+, Docker Compose v2
2. **Storage**: SQLite spool on edge (persistent Docker volume); TimescaleDB on VPS (persistent volume)
3. **Memory**: Edge daemon <50MB RSS; VPS API <200MB RSS per worker
4. **Network**: Edge has local LAN access to P1 meter; Edge has outbound HTTPS to VPS; VPS has public HTTPS

---

## Hard Constraints

### HC-001: No Data Loss
**Constraint**: Every polled measurement must reach TimescaleDB, even across outages.

**Rationale**: P1 meter readings are ephemeral — once missed, they cannot be re-read.

**Implications**:
- Write to SQLite spool before attempting upload
- Delete from spool only after server acknowledgment
- Spool must survive process and host restarts (persistent Docker volume)

**Allowed**: Local buffering, batch retry, backlog flush
**Forbidden**: Fire-and-forget, in-memory-only queues, deleting unacknowledged samples

### HC-002: Idempotent Ingestion
**Constraint**: Duplicate submissions must not create duplicate rows.

**Rationale**: Retry logic inherently causes duplicate POSTs.

**Implications**:
- (device_id, ts) is the composite primary key
- Use INSERT ON CONFLICT DO NOTHING

**Allowed**: Upsert patterns, idempotent endpoints
**Forbidden**: Blind INSERT, client-only deduplication

### HC-003: HTTPS Only
**Constraint**: All edge↔VPS traffic must use HTTPS with valid certificates.

**Rationale**: Device tokens and energy data must be encrypted in transit.

**Implications**:
- Caddy provides auto-HTTPS with Let's Encrypt
- Edge uploader must not disable certificate verification

**Allowed**: TLS 1.2+, auto-renewed certificates
**Forbidden**: HTTP in production, `verify=False`, self-signed certs in production

---

## Architecture Decision Records (ADRs)

### ADR-001: Monorepo for Edge + VPS
**Status**: Approved
**Date**: 2026-02-13
**Stories**: All

**Context**:
The system has two deployment targets (edge device, cloud VPS). They could live in
separate repositories or a single monorepo.

**Decision**:
Use a single monorepo with `edge/` and `vps/` top-level directories.

**Alternatives Considered**:
| Option | Pros | Cons |
|--------|------|------|
| Monorepo | Shared types, atomic story commits, simpler CI | Larger repo, both deploy targets in one |
| Two repos | Independent deploy cycles, smaller repos | Shared type drift, harder cross-cutting stories |

**Rationale**:
- Shared Pydantic models for ingest payload ensure edge and VPS stay in sync
- Stories often touch both edge and VPS (e.g., adding a new field)
- Single backlog and governance is simpler

**Consequences**:
- Docker builds must target specific directories
- CI may need path-based triggers

### ADR-002: TimescaleDB over Plain PostgreSQL
**Status**: Approved
**Date**: 2026-02-13
**Stories**: STORY-007, STORY-012, STORY-013

**Context**:
Time-series data (millions of rows, time-based queries, aggregation) needs efficient storage.

**Decision**:
Use TimescaleDB extension on PostgreSQL for hypertables and continuous aggregates.

**Alternatives Considered**:
| Option | Pros | Cons |
|--------|------|------|
| TimescaleDB | Native time-series, continuous aggregates, standard SQL | Extra extension dependency |
| Plain PostgreSQL | No extra deps, well-known | Manual partitioning, no continuous aggregates |
| InfluxDB | Purpose-built time-series | Different query language, separate system |

**Rationale**:
- Continuous aggregates eliminate expensive rollup queries at read time
- Standard SQL compatibility means SQLAlchemy works normally
- Automatic chunk management for time partitioning

**Consequences**:
- VPS Docker image must include TimescaleDB extension
- Migration files use TimescaleDB-specific DDL (create_hypertable, continuous aggregates)

---

## Deployment Strategy

### Environments

| Environment | URL | Purpose |
|-------------|-----|---------|
| Development | localhost | Local development and testing |
| Production (Edge) | N/A (local device) | Runs on home network device |
| Production (VPS) | `https://{VPS_DOMAIN}` | Cloud API server |

### Deployment Method

- **Edge**: Docker Compose on a local device (Raspberry Pi, NAS, or similar)
  - `docker compose -f docker-compose.edge.yml up -d`
  - Persistent volume for SQLite spool
- **VPS**: Docker Compose on cloud VPS
  - `docker compose -f docker-compose.vps.yml up -d`
  - Caddy for TLS, PostgreSQL + TimescaleDB, Redis, FastAPI app
  - Persistent volumes for database and Redis

---

## Documentation Strategy

### Documentation Sources
| Source | Location | Auto-generated |
|--------|----------|----------------|
| Architecture | `Architecture.md` | No |
| Technical Design | `technicaldesign.md` | No |
| Backlog | `docs/BACKLOG.md` | No |
| Stories | `docs/stories/*.md` | No |
| API docs | FastAPI `/docs` endpoint | Yes (OpenAPI) |
| Code docs | Docstrings | No |

### Documentation Requirements
- All public APIs must have documentation comments
- ADRs for all significant architectural decisions
- Story files for all development work
- CHANGELOG headers in all modified source files

---

## Related Documents

- `CLAUDE.md`: Agent workflow rules and gates (highest authority)
- `technicaldesign.md`: Detailed database schemas, API specs, validation rules
- `docs/BACKLOG.md`: Stories, acceptance criteria, progress tracking
- `SKILL.md`: VibeSec security guidelines
- `docs/project_idea.md`: Original project concept and requirements
