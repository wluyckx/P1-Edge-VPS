"""
FastAPI application entry point for the VPS API.

Provides the health endpoint and serves as the root application factory.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-006)
- 2026-02-13: Register ingest router (STORY-009)
- 2026-02-13: Register realtime router (STORY-010)
- 2026-02-13: Register capacity router (STORY-011)
- 2026-02-13: Register series router (STORY-012)
- 2026-02-13: Add startup lifespan to eagerly validate DEVICE_TOKENS

TODO:
- None
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.capacity import router as capacity_router
from src.api.deps import init_bearer_auth
from src.api.ingest import router as ingest_router
from src.api.realtime import router as realtime_router
from src.api.series import router as series_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: eagerly validate auth config at startup."""
    init_bearer_auth()
    logger.info("DEVICE_TOKENS validated at startup")
    yield


app = FastAPI(
    title="P1-Edge-VPS API",
    description="Energy telemetry API for HomeWizard P1 meter data.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(capacity_router)
app.include_router(ingest_router)
app.include_router(realtime_router)
app.include_router(series_router)


@app.get("/")
async def health() -> dict:
    """Health check endpoint.

    Returns:
        dict: JSON object with application status.
    """
    return {"status": "ok"}
