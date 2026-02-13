"""
Shared test fixtures for VPS tests.

Provides a configured TestClient for FastAPI integration testing.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-006)

TODO:
- Add mock database session fixture (STORY-007)
- Add mock Redis client fixture (STORY-009)
- Add auth fixtures (STORY-008)
"""

import pytest
from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture()
def client() -> TestClient:
    """Create a FastAPI TestClient for integration testing.

    Returns:
        TestClient: Configured test client for the FastAPI app.
    """
    return TestClient(app)
