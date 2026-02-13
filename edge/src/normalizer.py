"""
Measurement normalizer for HomeWizard P1 raw readings.

Pure function that transforms a raw HomeWizard measurement dict into a
normalized sample dict matching the p1_samples database schema. No side
effects, no I/O, no internal clock dependency -- the timestamp is always
injected via parameter for testability.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-003)

TODO:
- None
"""

from datetime import datetime

# Required keys that must be present in the raw HomeWizard measurement dict.
_REQUIRED_RAW_KEYS: frozenset[str] = frozenset(
    {
        "power_w",
        "energy_import_kwh",
        "energy_export_kwh",
    }
)


def normalize(raw: dict, device_id: str, ts: datetime) -> dict:
    """Normalize a raw HomeWizard measurement into a p1_samples-compatible dict.

    Takes the raw JSON dict from the HomeWizard P1 Local API v2 and returns
    a flat dict with exactly the fields required by the p1_samples schema.

    The function is pure: it has no side effects, performs no I/O, and does
    not call datetime.now(). The timestamp is provided externally via the
    ``ts`` parameter so callers can inject a deterministic value for testing.

    Args:
        raw: Raw measurement dict from HomeWizard P1 meter. Must contain
            at minimum: ``power_w``, ``energy_import_kwh``,
            ``energy_export_kwh``.
        device_id: Identifier of the P1 meter device (e.g. ``"hw-p1-001"``).
        ts: UTC timestamp to attach to this sample. Must be timezone-aware.

    Returns:
        A dict with keys: ``device_id``, ``ts`` (ISO 8601 UTC string),
        ``power_w``, ``import_power_w``, ``energy_import_kwh``,
        ``energy_export_kwh``.

    Raises:
        ValueError: If any required field is missing from ``raw``.
    """
    _validate_required_fields(raw)

    power_w: int = raw["power_w"]

    return {
        "device_id": device_id,
        "ts": ts.isoformat(),
        "power_w": power_w,
        "import_power_w": max(power_w, 0),
        "energy_import_kwh": raw["energy_import_kwh"],
        "energy_export_kwh": raw["energy_export_kwh"],
    }


def _validate_required_fields(raw: dict) -> None:
    """Check that all required HomeWizard fields are present in *raw*.

    Args:
        raw: The raw measurement dict to validate.

    Raises:
        ValueError: Listing every missing required field name.
    """
    missing = _REQUIRED_RAW_KEYS - raw.keys()
    if missing:
        sorted_missing = sorted(missing)
        raise ValueError(
            f"Raw measurement is missing required field(s): "
            f"{', '.join(sorted_missing)}"
        )
