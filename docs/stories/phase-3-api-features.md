# Phase 3: API Features

**Status**: Not Started
**Stories**: 4
**Completed**: 3
**Depends On**: Phase 2 (specifically STORY-009 for all stories, STORY-007 for STORY-013)

---

## Phase Completion Criteria

This phase is complete when:
- [ ] All stories have status "done"
- [ ] All tests passing (`pytest vps/tests/ -q`)
- [ ] Lint clean (`ruff check vps/src/`)
- [ ] Documentation updated
- [ ] All API endpoints operational: /v1/realtime, /v1/capacity/month/{month}, /v1/series

---

## Stories

<story id="STORY-010" status="done" complexity="M" tdd="required">
  <title>Realtime metrics endpoint</title>
  <dependencies>STORY-009</dependencies>

  <description>
    Serve the latest power reading for a device, cached in Redis for sub-100ms responses.
    Cache-first strategy: check Redis → on miss query TimescaleDB → cache result.
    Cache is invalidated by the ingest endpoint (STORY-009) on new data.
  </description>

  <acceptance_criteria>
    <ac id="AC1">GET /v1/realtime?device_id={id} returns latest sample for device</ac>
    <ac id="AC2">Response JSON: {device_id, ts, power_w, import_power_w, energy_import_kwh,
      energy_export_kwh}</ac>
    <ac id="AC3">Redis cache hit → response in &lt;100ms (no DB query)</ac>
    <ac id="AC4">Cache miss → query last row from TimescaleDB ORDER BY ts DESC LIMIT 1</ac>
    <ac id="AC5">Cache miss → result cached with TTL = CACHE_TTL_S</ac>
    <ac id="AC6">Unknown device_id (no data) → 404 Not Found</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>vps/src/api/realtime.py</file>
    <file>vps/src/cache/redis_client.py</file>
    <file>vps/tests/test_realtime.py</file>
  </allowed_scope>

  <test_first>
    <item>Create vps/tests/test_realtime.py FIRST</item>
    <item>Mock Redis client (get/set/delete)</item>
    <item>Mock AsyncSession for DB query</item>
    <item>Test: cache hit → returns cached JSON, no DB call</item>
    <item>Test: cache miss → queries DB, caches result, returns data</item>
    <item>Test: unknown device (no DB rows) → 404</item>
    <item>Test: response includes all required fields</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>

  <test_plan>
    - Unit tests for cache layer (get/set with mock Redis)
    - Integration tests via TestClient (mocked Redis + DB)
    - Verify cache-first behavior (no DB call on cache hit)
    - `pytest vps/tests/ -q` all pass
  </test_plan>

  <notes>
    - Cache key: "realtime:{device_id}"
    - Cache value: JSON-serialized sample
    - TTL from config.CACHE_TTL_S (default 5 seconds)
    - STORY-009 already deletes cache key on new ingest
  </notes>
</story>

---

<story id="STORY-011" status="done" complexity="L" tdd="required">
  <title>Capacity tariff calculation (kwartierpiek)</title>
  <dependencies>STORY-009</dependencies>

  <description>
    Belgian capacity tariff is based on the highest 15-minute average power consumption
    in a month. This endpoint calculates all 15-minute average power values for a given
    month and identifies the peak.

    Algorithm:
    1. Bucket all import_power_w samples into 15-minute windows using time_bucket()
    2. Calculate average import_power_w per window
    3. The monthly peak is the highest 15-minute average
    4. Return all windows and the peak

    Month format: YYYY-MM (e.g., "2026-01")
  </description>

  <acceptance_criteria>
    <ac id="AC1">GET /v1/capacity/month/{month}?device_id={id} returns capacity data</ac>
    <ac id="AC2">Response: {month, device_id, peaks: [{bucket, avg_power_w}...],
      monthly_peak_w, monthly_peak_ts}</ac>
    <ac id="AC3">15-min windows: time_bucket('15 minutes', ts), AVG(import_power_w)</ac>
    <ac id="AC4">monthly_peak_w = MAX of all 15-min averages</ac>
    <ac id="AC5">monthly_peak_ts = timestamp of the peak window</ac>
    <ac id="AC6">Invalid month format → 400 Bad Request</ac>
    <ac id="AC7">Month with no data → 200 with empty peaks array and null peak</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>vps/src/api/capacity.py</file>
    <file>vps/src/services/capacity.py</file>
    <file>vps/tests/test_capacity.py</file>
  </allowed_scope>

  <test_first>
    <item>Create vps/tests/test_capacity.py FIRST</item>
    <item>Mock AsyncSession to return predefined time_bucket query results</item>
    <item>Test: known data → correct 15-min averages</item>
    <item>Test: monthly peak is the max of 15-min averages</item>
    <item>Test: monthly_peak_ts matches the peak bucket</item>
    <item>Test: invalid month format (e.g., "2026-1") → 400</item>
    <item>Test: month with no data → empty peaks, null peak</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>

  <test_plan>
    - Unit tests for capacity service with fixture data (mocked DB results)
    - Verify 15-minute bucketing produces correct averages
    - Verify peak identification
    - Edge cases: single sample, all samples in one window, empty month
    - `pytest vps/tests/ -q` all pass
  </test_plan>

  <notes>
    - SQL: SELECT time_bucket('15 minutes', ts) AS bucket,
             AVG(import_power_w)::integer AS avg_power_w
           FROM p1_samples
           WHERE device_id = :device_id AND ts >= :month_start AND ts < :month_end
           GROUP BY bucket ORDER BY bucket
    - Belgian capacity tariff: the peak determines the monthly capacity charge
    - Month parameter: YYYY-MM parsed to first and last day of month (UTC)
  </notes>
</story>

---

<story id="STORY-012" status="done" complexity="L" tdd="required">
  <title>Historical series endpoint</title>
  <dependencies>STORY-009</dependencies>

  <description>
    Serve aggregated historical energy data with configurable time frames:
    - day → hourly buckets (today)
    - month → weekly buckets (current month)
    - year → monthly buckets (current year)
    - all → monthly buckets (all time)

    Each bucket includes: avg_power_w, max_power_w, sum energy_import_kwh, sum energy_export_kwh.
  </description>

  <acceptance_criteria>
    <ac id="AC1">GET /v1/series?device_id={id}&amp;frame={frame} returns aggregated series</ac>
    <ac id="AC2">frame=day → time_bucket('1 hour', ts) for today (UTC)</ac>
    <ac id="AC3">frame=month → time_bucket('1 week', ts) for current month</ac>
    <ac id="AC4">frame=year → time_bucket('1 month', ts) for current year</ac>
    <ac id="AC5">frame=all → time_bucket('1 month', ts) for all data</ac>
    <ac id="AC6">Each bucket: {bucket, avg_power_w, max_power_w, energy_import_kwh, energy_export_kwh}</ac>
    <ac id="AC7">Invalid frame → 400 Bad Request</ac>
    <ac id="AC8">No data in range → 200 with empty series array</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>vps/src/api/series.py</file>
    <file>vps/src/services/aggregation.py</file>
    <file>vps/tests/test_series.py</file>
  </allowed_scope>

  <test_first>
    <item>Create vps/tests/test_series.py FIRST</item>
    <item>Mock AsyncSession to return predefined aggregation results</item>
    <item>Test: frame=day → 1-hour bucket interval</item>
    <item>Test: frame=month → 1-week bucket interval</item>
    <item>Test: frame=year → 1-month bucket interval</item>
    <item>Test: frame=all → 1-month bucket interval</item>
    <item>Test: invalid frame → 400</item>
    <item>Test: no data → empty series</item>
    <item>Tests must FAIL before implementation</item>
  </test_first>

  <test_plan>
    - Unit tests for aggregation service with mocked DB
    - Verify frame → time_bucket mapping is correct
    - Verify aggregation fields (avg, max, sum)
    - `pytest vps/tests/ -q` all pass
  </test_plan>

  <notes>
    - Frame-to-interval mapping: {"day": "1 hour", "month": "1 week", "year": "1 month", "all": "1 month"}
    - Frame-to-range mapping: {"day": today, "month": current month, "year": current year, "all": no filter}
    - Optional: Redis caching for frequently-accessed frames (can add in STORY-013)
  </notes>
</story>

---

<story id="STORY-013" status="pending" complexity="M" tdd="recommended">
  <title>TimescaleDB continuous aggregates</title>
  <dependencies>STORY-007, STORY-012</dependencies>

  <description>
    Replace on-the-fly aggregation queries in the series endpoint with pre-computed
    TimescaleDB continuous aggregates. This dramatically improves query performance
    for historical data.

    Create materialized views:
    - p1_hourly: 1-hour buckets
    - p1_daily: 1-day buckets
    - p1_monthly: 1-month buckets

    Each view: bucket, device_id, avg_power_w, max_power_w, energy_import_kwh, energy_export_kwh
  </description>

  <acceptance_criteria>
    <ac id="AC1">Alembic migration creates p1_hourly continuous aggregate view</ac>
    <ac id="AC2">Alembic migration creates p1_daily continuous aggregate view</ac>
    <ac id="AC3">Alembic migration creates p1_monthly continuous aggregate view</ac>
    <ac id="AC4">Each view auto-refreshes with continuous aggregate policy</ac>
    <ac id="AC5">aggregation.py queries continuous aggregates instead of raw p1_samples</ac>
    <ac id="AC6">Series endpoint performance improves (queries materialized data)</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>vps/src/db/migrations/versions/002_continuous_aggregates.py</file>
    <file>vps/src/services/aggregation.py</file>
    <file>vps/tests/test_series.py</file>
  </allowed_scope>

  <test_plan>
    - Migration SQL review: verify continuous aggregate DDL
    - Verify aggregation service queries correct views
    - Existing series tests still pass
    - `pytest vps/tests/ -q` all pass
  </test_plan>

  <notes>
    - TimescaleDB: CREATE MATERIALIZED VIEW p1_hourly WITH (timescaledb.continuous) AS
        SELECT time_bucket('1 hour', ts) AS bucket, device_id, ...
    - Refresh policy: SELECT add_continuous_aggregate_policy('p1_hourly',
        start_offset => INTERVAL '3 hours', end_offset => INTERVAL '1 hour',
        schedule_interval => INTERVAL '1 hour')
    - Repeat for daily (1 day) and monthly (1 month) buckets
  </notes>
</story>

---

## Phase Notes

### Dependencies on Other Phases
- All stories in this phase depend on STORY-009 (Ingest API) from Phase 2
- STORY-013 also depends on STORY-007 (DB schema) for migration ordering

### Known Risks
- Continuous aggregate limitations: cannot include columns not in the GROUP BY or aggregate
- time_bucket for months is approximate — verify boundary handling

### Technical Debt
- STORY-012 initially queries raw table; STORY-013 optimizes to continuous aggregates
- Redis caching for series endpoint deferred — add if needed for performance
