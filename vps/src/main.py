"""
FastAPI application entry point for the VPS API.

Provides the health endpoint and serves as the root application factory.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-006)

TODO:
- None
"""

from fastapi import FastAPI

app = FastAPI(
    title="P1-Edge-VPS API",
    description="Energy telemetry API for HomeWizard P1 meter data.",
    version="0.1.0",
)


@app.get("/")
async def health() -> dict:
    """Health check endpoint.

    Returns:
        dict: JSON object with application status.
    """
    return {"status": "ok"}
