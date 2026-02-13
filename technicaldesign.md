# Technical Design — P1-Edge-VPS Energy Telemetry Platform

**Last Updated**: 2026-02-13
**Version**: 1.0

---

## Overview

This document contains detailed technical specifications for the P1-Edge-VPS platform.
It supplements Architecture.md with implementation details: database schemas, API endpoint
contracts, validation rules, and processing pipelines.

**When to use this document**: When a story requires detailed schema knowledge, specific
API contracts, or complex validation rules that would clutter Architecture.md.

---

## Data Models

### P1Sample

**Purpose**: A single energy measurement from a HomeWizard P1 meter at a specific point in time.

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `device_id` | TEXT | Yes | Identifier of the P1 meter device |
| `ts` | TIMESTAMPTZ | Yes | Measurement timestamp (UTC) |
| `power_w` | INTEGER | Yes | Current power consumption/production in watts (can be negative for export) |
| `import_power_w` | INTEGER | Yes | Import power in watts, always >= 0 (`max(power_w, 0)`) |
| `energy_import_kwh` | DOUBLE PRECISION | No | Cumulative energy imported from grid (kWh) |
| `energy_export_kwh` | DOUBLE PRECISION | No | Cumulative energy exported to grid (kWh) |

**Primary Key**: `(device_id, ts)` — composite, enforces idempotency (HC-002)

**Validation Rules**:
- `device_id`: Non-empty string, max 64 characters, alphanumeric + hyphens
- `ts`: Valid ISO 8601 datetime with timezone, not in the future (>5 min tolerance)
- `power_w`: Integer, range -100000 to 100000 (watts)
- `import_power_w`: Integer, >= 0, must equal `max(power_w, 0)`
- `energy_import_kwh`: Float >= 0 if present
- `energy_export_kwh`: Float >= 0 if present

**JSON Example** (as used in ingest API):
```json
{
  "device_id": "hw-p1-001",
  "ts": "2026-02-13T14:30:00Z",
  "power_w": 450,
  "import_power_w": 450,
  "energy_import_kwh": 12345.678,
  "energy_export_kwh": 1234.567
}
```

---

## Database Schema

### Tables

#### p1_samples (TimescaleDB Hypertable)

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE p1_samples (
    device_id TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    power_w INTEGER NOT NULL,
    import_power_w INTEGER NOT NULL,
    energy_import_kwh DOUBLE PRECISION,
    energy_export_kwh DOUBLE PRECISION,
    PRIMARY KEY (device_id, ts)
);

SELECT create_hypertable('p1_samples', 'ts', if_not_exists => TRUE);
```

**Purpose**: Store all raw energy measurements as a time-series hypertable.

**Indexes**:
- Primary key index on `(device_id, ts)` — used for idempotent upserts and time-range queries
- TimescaleDB automatic chunk indexes on `ts`

**Partitioning**: TimescaleDB auto-chunks by `ts` (default 7-day chunks)

---

### Continuous Aggregate Views (STORY-013)

#### p1_hourly

```sql
CREATE MATERIALIZED VIEW p1_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', ts) AS bucket,
    device_id,
    AVG(power_w)::INTEGER AS avg_power_w,
    MAX(power_w) AS max_power_w,
    MAX(energy_import_kwh) - MIN(energy_import_kwh) AS energy_import_kwh,
    MAX(energy_export_kwh) - MIN(energy_export_kwh) AS energy_export_kwh
FROM p1_samples
GROUP BY bucket, device_id;

SELECT add_continuous_aggregate_policy('p1_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
```

#### p1_daily

```sql
CREATE MATERIALIZED VIEW p1_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', ts) AS bucket,
    device_id,
    AVG(power_w)::INTEGER AS avg_power_w,
    MAX(power_w) AS max_power_w,
    MAX(energy_import_kwh) - MIN(energy_import_kwh) AS energy_import_kwh,
    MAX(energy_export_kwh) - MIN(energy_export_kwh) AS energy_export_kwh
FROM p1_samples
GROUP BY bucket, device_id;

SELECT add_continuous_aggregate_policy('p1_daily',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');
```

#### p1_monthly

```sql
CREATE MATERIALIZED VIEW p1_monthly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 month', ts) AS bucket,
    device_id,
    AVG(power_w)::INTEGER AS avg_power_w,
    MAX(power_w) AS max_power_w,
    MAX(energy_import_kwh) - MIN(energy_import_kwh) AS energy_import_kwh,
    MAX(energy_export_kwh) - MIN(energy_export_kwh) AS energy_export_kwh
FROM p1_samples
GROUP BY bucket, device_id;

SELECT add_continuous_aggregate_policy('p1_monthly',
    start_offset => INTERVAL '3 months',
    end_offset => INTERVAL '1 month',
    schedule_interval => INTERVAL '1 day');
```

### Entity Relationship

```
┌─────────────────────┐
│    p1_samples        │  (hypertable)
├─────────────────────┤
│ PK device_id TEXT    │
│ PK ts TIMESTAMPTZ    │
│    power_w INTEGER   │
│    import_power_w    │
│    energy_import_kwh │
│    energy_export_kwh │
└──────────┬──────────┘
           │ continuous aggregates
    ┌──────┴──────┬──────────────┐
    ▼             ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ p1_hourly│ │ p1_daily │ │p1_monthly│
└──────────┘ └──────────┘ └──────────┘
```

---

## Edge SQLite Spool Schema

The edge daemon uses a local SQLite database to buffer samples before upload.

```sql
-- WAL mode for concurrent read/write
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS spool (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    ts TEXT NOT NULL,          -- ISO 8601 UTC string
    power_w INTEGER NOT NULL,
    import_power_w INTEGER NOT NULL,
    energy_import_kwh REAL,
    energy_export_kwh REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Operations**:
- `enqueue(sample)`: INSERT into spool
- `peek(n)`: SELECT ... ORDER BY rowid ASC LIMIT n (FIFO)
- `ack(rowids)`: DELETE FROM spool WHERE rowid IN (...)
- `count()`: SELECT COUNT(*) FROM spool

---

## API Specifications

### Authentication

**Method**: Bearer token per device

**Header format**:
```
Authorization: Bearer {device_token}
```

**Token configuration** (VPS environment variable):
```
DEVICE_TOKENS=tokenA:device-1,tokenB:device-2
```

Parsed at startup into `dict[str, str]` mapping `token → device_id`.
Validation uses `secrets.compare_digest()` for constant-time comparison.

**Responses**:
- Missing/invalid token: `401 Unauthorized`
- Valid token: request proceeds with `device_id` in context

---

### POST /v1/ingest

**Description**: Receive a batch of energy samples from an edge device. Idempotent upsert.

**Authentication**: Required (Bearer token)

**Request**:
```http
POST /v1/ingest HTTP/1.1
Content-Type: application/json
Authorization: Bearer {device_token}

{
  "samples": [
    {
      "device_id": "hw-p1-001",
      "ts": "2026-02-13T14:30:00Z",
      "power_w": 450,
      "import_power_w": 450,
      "energy_import_kwh": 12345.678,
      "energy_export_kwh": 1234.567
    }
  ]
}
```

**Request Model** (Pydantic):
```python
class SampleCreate(BaseModel):
    device_id: str
    ts: datetime
    power_w: int
    import_power_w: int
    energy_import_kwh: float | None = None
    energy_export_kwh: float | None = None

class IngestRequest(BaseModel):
    samples: list[SampleCreate]
```

**Validation Rules**:
- `samples` list must be non-empty, max 1000 items per batch
- All `device_id` values in the batch MUST match the authenticated device_id (403 on mismatch)
- Field validation per P1Sample data model rules above

**Response** (200 OK):
```json
{
  "inserted": 15
}
```
Where `inserted` = number of new rows (duplicates silently ignored via ON CONFLICT DO NOTHING).

**Error Responses**:
| Status | Condition | Body |
|--------|-----------|------|
| 401 | Missing/invalid Bearer token | `{"detail": "Not authenticated"}` |
| 403 | Sample device_id does not match authenticated device | `{"detail": "Device ID mismatch"}` |
| 422 | Invalid request body (Pydantic validation) | Standard FastAPI validation error |

**Idempotency**: `INSERT ... ON CONFLICT (device_id, ts) DO NOTHING`
Sending the same batch twice is safe — duplicates are silently skipped.

**Side effects**: On successful ingest, Redis cache key `realtime:{device_id}` is deleted.

---

### GET /v1/realtime

**Description**: Get the latest power reading for a device. Redis-cached.

**Authentication**: Not required (public endpoint)

**Request**:
```http
GET /v1/realtime?device_id=hw-p1-001 HTTP/1.1
```

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `device_id` | string | Yes | Device identifier |

**Response** (200 OK):
```json
{
  "device_id": "hw-p1-001",
  "ts": "2026-02-13T14:30:00Z",
  "power_w": 450,
  "import_power_w": 450,
  "energy_import_kwh": 12345.678,
  "energy_export_kwh": 1234.567
}
```

**Error Responses**:
| Status | Condition | Body |
|--------|-----------|------|
| 404 | No data for device_id | `{"detail": "No data for device"}` |

**Caching**: Redis key `realtime:{device_id}`, TTL = `CACHE_TTL_S` (default 5s).
Cache-first: check Redis → on miss query DB → cache result.

---

### GET /v1/capacity/month/{month}

**Description**: Belgian capacity tariff (kwartierpiek) data for a given month.

**Authentication**: Not required (public endpoint)

**Request**:
```http
GET /v1/capacity/month/2026-01?device_id=hw-p1-001 HTTP/1.1
```

**Path Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `month` | string | Yes | Month in YYYY-MM format |

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `device_id` | string | Yes | Device identifier |

**Response** (200 OK):
```json
{
  "month": "2026-01",
  "device_id": "hw-p1-001",
  "peaks": [
    {"bucket": "2026-01-01T00:00:00Z", "avg_power_w": 320},
    {"bucket": "2026-01-01T00:15:00Z", "avg_power_w": 450}
  ],
  "monthly_peak_w": 2150,
  "monthly_peak_ts": "2026-01-15T18:30:00Z"
}
```

**Error Responses**:
| Status | Condition | Body |
|--------|-----------|------|
| 400 | Invalid month format (not YYYY-MM) | `{"detail": "Invalid month format"}` |

**SQL**:
```sql
SELECT time_bucket('15 minutes', ts) AS bucket,
       AVG(import_power_w)::INTEGER AS avg_power_w
FROM p1_samples
WHERE device_id = :device_id
  AND ts >= :month_start AND ts < :month_end
GROUP BY bucket
ORDER BY bucket;
```

---

### GET /v1/series

**Description**: Aggregated historical energy data with configurable time frame.

**Authentication**: Not required (public endpoint)

**Request**:
```http
GET /v1/series?device_id=hw-p1-001&frame=day HTTP/1.1
```

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `device_id` | string | Yes | Device identifier |
| `frame` | string | Yes | Time frame: `day`, `month`, `year`, `all` |

**Frame-to-Interval Mapping**:
| Frame | Bucket Interval | Time Range |
|-------|-----------------|------------|
| `day` | 1 hour | Today (UTC) |
| `month` | 1 week | Current month |
| `year` | 1 month | Current year |
| `all` | 1 month | All data |

**Response** (200 OK):
```json
{
  "device_id": "hw-p1-001",
  "frame": "day",
  "series": [
    {
      "bucket": "2026-02-13T00:00:00Z",
      "avg_power_w": 320,
      "max_power_w": 1200,
      "energy_import_kwh": 0.45,
      "energy_export_kwh": 0.12
    }
  ]
}
```

**Error Responses**:
| Status | Condition | Body |
|--------|-----------|------|
| 400 | Invalid frame parameter | `{"detail": "Invalid frame. Must be one of: day, month, year, all"}` |

---

## Configuration

### Edge Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `HW_P1_HOST` | HomeWizard P1 meter IP/hostname | — | Yes |
| `HW_P1_TOKEN` | HomeWizard Local API v2 bearer token | — | Yes |
| `VPS_INGEST_URL` | VPS base URL (must be HTTPS) | — | Yes |
| `VPS_DEVICE_TOKEN` | Per-device bearer token | — | Yes |
| `POLL_INTERVAL_S` | Seconds between P1 polls | `2` | No |
| `BATCH_SIZE` | Max samples per upload batch | `30` | No |
| `UPLOAD_INTERVAL_S` | Seconds between upload attempts | `10` | No |
| `SPOOL_PATH` | SQLite spool file path | `/data/spool.db` | No |

**Validation** (at startup):
- `VPS_INGEST_URL` must start with `https://` (HC-003)
- `POLL_INTERVAL_S` must be >= 1
- `BATCH_SIZE` must be >= 1 and <= 1000

### VPS Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | — | Yes |
| `REDIS_URL` | Redis connection string | — | Yes |
| `DEVICE_TOKENS` | Comma-separated `token:device_id` pairs | — | Yes |
| `CACHE_TTL_S` | Redis cache TTL in seconds | `5` | No |

---

## Security Specifications

### Authentication Flow

```
Edge Device                           VPS API
    │                                    │
    │  POST /v1/ingest                   │
    │  Authorization: Bearer {token}     │
    │  {"samples": [...]}                │
    │───────────────────────────────────>│
    │                                    │ 1. Extract Bearer token
    │                                    │ 2. Lookup token in DEVICE_TOKENS map
    │                                    │ 3. If not found → 401
    │                                    │ 4. Extract device_id from token map
    │                                    │ 5. Validate all sample.device_id == device_id
    │                                    │ 6. If mismatch → 403
    │                                    │ 7. Proceed with upsert
    │  200 {"inserted": N}               │
    │<───────────────────────────────────│
```

### Rate Limiting

| Tier | Limit | Window |
|------|-------|--------|
| Ingest (per device) | 60 requests | 1 minute |
| Read endpoints | 120 requests | 1 minute |

---

## Glossary

| Term | Definition |
|------|------------|
| Kwartierpiek | Belgian capacity tariff term: the highest 15-minute average power consumption in a month |
| Hypertable | TimescaleDB time-partitioned table with automatic chunk management |
| Continuous aggregate | TimescaleDB materialized view that auto-refreshes on new data |
| Spool | Local durable queue (SQLite) that buffers samples before upload |
| WAL mode | SQLite Write-Ahead Logging mode for concurrent read/write |
| Idempotent upsert | INSERT that silently ignores duplicates (ON CONFLICT DO NOTHING) |
