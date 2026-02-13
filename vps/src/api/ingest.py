"""
Ingest API endpoint for P1 energy telemetry samples.

Accepts batches of energy samples via POST /v1/ingest, validates them
against the authenticated device_id, performs idempotent database inserts,
and invalidates the Redis cache for the device.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-009)

TODO:
- None
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.deps import CurrentDeviceId, DbSession
from src.cache.redis_client import invalidate_device_cache
from src.services.ingestion import ingest_samples

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["ingest"])


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------


class SampleCreate(BaseModel):
    """Schema for a single energy telemetry sample.

    Attributes:
        device_id: Identifier of the P1 meter device.
        ts: Measurement timestamp (UTC recommended).
        power_w: Current power in watts.
        import_power_w: Import power in watts.
        energy_import_kwh: Cumulative energy imported (optional).
        energy_export_kwh: Cumulative energy exported (optional).
    """

    device_id: str
    ts: datetime
    power_w: int
    import_power_w: int
    energy_import_kwh: float | None = None
    energy_export_kwh: float | None = None


class IngestRequest(BaseModel):
    """Schema for the ingest request body.

    Attributes:
        samples: List of energy telemetry samples to ingest.
    """

    samples: list[SampleCreate]


class IngestResponse(BaseModel):
    """Schema for the ingest response.

    Attributes:
        inserted: Number of newly inserted rows (excludes duplicates).
    """

    inserted: int


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    request: IngestRequest,
    device_id: CurrentDeviceId,
    db: DbSession,
) -> IngestResponse:
    """Ingest a batch of P1 energy telemetry samples.

    Validates that all sample device_ids match the authenticated device_id,
    inserts new rows (skipping duplicates via ON CONFLICT DO NOTHING), and
    invalidates the Redis cache for the device.

    Args:
        request: Validated ingest request with a list of samples.
        device_id: Authenticated device_id from Bearer token.
        db: Async database session.

    Returns:
        IngestResponse: Number of newly inserted rows.

    Raises:
        HTTPException: 403 if any sample device_id does not match the
            authenticated device_id.
    """
    # AC8: Verify all samples belong to the authenticated device
    for sample in request.samples:
        if sample.device_id != device_id:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Sample device_id '{sample.device_id}' does not match "
                    f"authenticated device_id '{device_id}'."
                ),
            )

    # Convert Pydantic models to dicts for the ingestion service
    sample_dicts = [s.model_dump() for s in request.samples]

    # AC4: Idempotent insert with ON CONFLICT DO NOTHING
    inserted = await ingest_samples(db, sample_dicts)

    # AC9: Best-effort cache invalidation
    try:
        await invalidate_device_cache(device_id)
    except Exception:
        logger.warning(
            "Cache invalidation failed for device %s", device_id, exc_info=True,
        )

    return IngestResponse(inserted=inserted)
