"""
HomeWizard P1 meter poller — reads real-time measurements via Local API v2.

Sends an HTTP GET with Bearer token to ``http://{host}/api/measurement``
and returns the parsed JSON dict. All network and HTTP errors are caught
and logged at WARNING level so the poll loop never crashes.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-002)

TODO:
- None
"""

import logging

import httpx

logger = logging.getLogger(__name__)

# Default request timeout in seconds.
_DEFAULT_TIMEOUT: float = 5.0


def poll_measurement(
    *,
    host: str,
    token: str,
    timeout: float = _DEFAULT_TIMEOUT,
) -> dict | None:
    """Poll the HomeWizard P1 meter for the latest measurement.

    Sends ``GET http://{host}/api/measurement`` with an
    ``Authorization: Bearer {token}`` header.

    Args:
        host: IP address or hostname of the HomeWizard P1 meter on the
              local network (e.g. ``"192.168.1.100"``).
        token: HomeWizard Local API v2 bearer token.
        timeout: HTTP request timeout in seconds. Defaults to 5.0.

    Returns:
        Parsed JSON dict on HTTP 200, or ``None`` on any error.
    """
    url = f"http://{host}/api/measurement"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as exc:
        logger.warning(
            "P1 poll HTTP error %s for %s: %s",
            exc.response.status_code,
            url,
            exc,
        )
        return None

    except httpx.TimeoutException as exc:
        logger.warning("P1 poll timeout for %s: %s", url, exc)
        return None

    except httpx.ConnectError as exc:
        logger.warning("P1 poll connection error for %s: %s", url, exc)
        return None
