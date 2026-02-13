# project_start.md

# P1-to-VPS Energy Telemetry Platform

## 1. Main Project Idea

Build a robust, production-grade telemetry pipeline that synchronizes real-time energy readings from a HomeWizard P1 meter (LAN) to a secure cloud VPS.

The system provides:

- Real-time power metrics
- Capacity tariff calculations (15-minute kwartierpiek + monthly peak)
- Historical frames:
  - All time → monthly aggregation
  - Year → monthly aggregation
  - Month → weekly aggregation
  - Day → hourly aggregation
- Robust local buffering when internet is down
- Redis-backed low-latency API responses

---

## 2. Functional Description

### Edge (Local Network)

- Polls HomeWizard P1 `/api/measurement` (Local API v2)
- Normalizes measurements
- Stores samples in local SQLite spool before upload
- Uploads in batches to VPS
- Retries with exponential backoff
- Flushes backlog after reconnect

### VPS (Cloud)

- TLS termination (Caddy)
- Device authentication (Bearer tokens)
- Idempotent ingestion
- Postgres + TimescaleDB storage
- Continuous aggregates
- 15-minute peak calculation
- Redis cache layer
- Public API

---

## 3. High-Level Requirements

### Reliability
- No data loss during outage
- Durable local buffering
- Idempotent upserts (device_id + ts)
- Automatic retry

### Performance
- <100ms realtime endpoint (cache hit)
- Efficient rollups
- Batched ingestion

### Security
- HTTPS only
- Per-device token
- Outbound-only edge traffic

---

## 4. Architecture

HomeWizard P1 → Edge Docker → HTTPS → VPS API → TimescaleDB → Redis → Public API

---

## 5. Production Docker Compose

### Edge compose.yml

```yaml
version: "3.9"
services:
  p1-edge:
    image: ghcr.io/your-org/p1-edge:latest
    restart: unless-stopped
    environment:
      HW_P1_HOST: "${HW_P1_HOST}"
      HW_P1_TOKEN: "${HW_P1_TOKEN}"
      VPS_INGEST_URL: "${VPS_INGEST_URL}"
      VPS_DEVICE_TOKEN: "${VPS_DEVICE_TOKEN}"
    volumes:
      - p1_edge_data:/data
volumes:
  p1_edge_data:
```

### VPS compose.yml

```yaml
version: "3.9"
services:
  api:
    image: ghcr.io/your-org/p1-api:latest
    restart: unless-stopped
    environment:
      DATABASE_URL: "postgresql://p1:${POSTGRES_PASSWORD}@postgres:5432/p1"
      REDIS_URL: "redis://redis:6379/0"
  postgres:
    image: timescale/timescaledb:latest
  redis:
    image: redis:7-alpine
  caddy:
    image: caddy:2
```

---

## 6. Database Schema (SQL)

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

---

## 7. OpenAPI Specification (Excerpt)

```yaml
openapi: 3.1.0
info:
  title: P1 Energy API
  version: 1.0.0
paths:
  /v1/ingest:
    post:
      summary: Ingest batch
  /v1/realtime:
    get:
      summary: Realtime metrics
  /v1/capacity/month/{month}:
    get:
      summary: Monthly peak
  /v1/series:
    get:
      summary: Historical series
```

---

## 8. Edge Daemon Skeleton (Python)

```python
import requests, sqlite3, time, os, json
from datetime import datetime, timezone

def normalize(hw):
    power_w = int(hw.get("power_w", 0))
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "power_w": power_w,
        "import_power_w": max(power_w, 0)
    }

while True:
    # poll HomeWizard
    # enqueue to SQLite
    # batch upload
    time.sleep(2)
```

---

## Summary

This architecture ensures:

- No data loss
- Robust buffering
- Accurate capacity tariff calculations
- Scalable time-series storage
- Low-latency API via Redis
