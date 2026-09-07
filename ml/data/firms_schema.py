"""
ml/data/firms_schema.py — Column mappings and normalization rules for NASA FIRMS CSV.

Supports real FIRMS CSV variants without inventing fake data.

Typical FIRMS columns (VIIRS / MODIS):
  latitude, longitude, bright_ti4, bright_ti5, scan, track,
  acq_date, acq_time, satellite, instrument, confidence, version,
  bright_t31, frp, daynight

Essential normalized fields (→ ThermalEvent):
  latitude, longitude, timestamp, frp, brightness_temperature, confidence, satellite

Design notes:
- VIIRS brightness temperature: prefer bright_ti4 (I4 ~3.7µm, primary fire channel)
  then bright_ti5 (I5 ~11µm) then bright_t31 (MODIS heritage) then any generic
  brightness_temperature variant. Rationale: bright_ti4 is most sensitive to
  sub-pixel fire; this matches NASA FIRMS documentation for active fire.
- Confidence: FIRMS uses different encodings:
    VIIRS:  'l'/'n'/'h'  (low/nominal/high)  → 30/60/90
    MODIS:  0-100 numeric OR 'l'/'n'/'h'
    Some exports use 'confidence' as integer 0-100 already.
  Normalized to 0-100 float (see firms_cleaner._normalize_confidence).
- Timestamp: FIRMS provides acq_date (YYYY-MM-DD) + acq_time (HHMM, e.g. "1342"
  meaning 13:42 UTC) or occasionally HH:MM. Converted to UTC-aware ISO8601
  (YYYY-MM-DDTHH:MM:SSZ). See firms_cleaner._parse_timestamp.
- Satellite: values like "VIIRS", "N", "Terra", "Aqua", "NOAA-20", "NOAA-21",
  "1" etc. Normalized to upper-case canonical string; fallback to instrument
  if satellite column missing.
- ID: deterministic SHA-1 of (satellite|timestamp|lat|lon) — see firms_cleaner.

All mappings are case-insensitive, stripped, and preserve original fields
in the raw record where practical.
"""

from __future__ import annotations

# Canonical normalized keys expected downstream
ESSENTIAL_NORMALIZED = [
    "latitude",
    "longitude",
    "timestamp",
    "frp",
    "brightness_temperature",
    "confidence",
    "satellite",
]

# Columns that MUST be derivable; loader will raise FirmsSchemaError if absent
# (latitude/longitude/acq_date+acq_time or timestamp/satellite-or-instrument)
REQUIRED_SOURCE_GROUPS = [
    # At least one from each group must be present
    ["latitude", "lat", "y"],
    ["longitude", "lon", "long", "lng", "x"],
    # timestamp can be derived from acq_date+acq_time OR acq_datetime/timestamp
    ["acq_date", "acq_datetime", "timestamp", "datetime", "date"],
]

# Variant → canonical mapping (lower-cased stripped input → canonical)
COLUMN_ALIASES: dict[str, str] = {
    # latitude
    "latitude": "latitude",
    "lat": "latitude",
    "y": "latitude",
    # longitude
    "longitude": "longitude",
    "lon": "longitude",
    "long": "longitude",
    "lng": "longitude",
    "x": "longitude",
    # FRP
    "frp": "frp",
    "fire_radiative_power": "frp",
    "power": "frp",
    # brightness temperature variants
    "bright_ti4": "bright_ti4",
    "bright_ti5": "bright_ti5",
    "bright_t31": "bright_t31",
    "bright_t4": "bright_ti4",
    "brightness": "brightness_temperature",
    "brightness_temperature": "brightness_temperature",
    "bright_temp": "brightness_temperature",
    "bt": "brightness_temperature",
    "ti4": "bright_ti4",
    "ti5": "bright_ti5",
    "t31": "bright_t31",
    # confidence
    "confidence": "confidence",
    "conf": "confidence",
    "conf_a": "confidence",
    # timestamp parts
    "acq_date": "acq_date",
    "acq_time": "acq_time",
    "acq_datetime": "acq_datetime",
    "timestamp": "timestamp",
    "datetime": "acq_datetime",
    "date": "acq_date",
    "time": "acq_time",
    # satellite / instrument
    "satellite": "satellite",
    "sat": "satellite",
    "instrument": "instrument",
    "sensor": "instrument",
    "daynight": "daynight",
    # passthrough useful originals
    "scan": "scan",
    "track": "track",
    "version": "version",
}

# Priority for selecting brightness_temperature from available FIRMS BT columns
# Highest priority first
BT_PRIORITY = ["bright_ti4", "bright_ti5", "bright_t31", "brightness_temperature"]


class FirmsSchemaError(ValueError):
    """Raised when essential FIRMS columns are absent or unrecoverable."""


def normalize_column_name(raw: str) -> str:
    """Map raw CSV header to canonical key (or preserve lower-cased raw if unknown)."""
    key = raw.strip().lower()
    return COLUMN_ALIASES.get(key, key)


def select_brightness_temperature(row: dict) -> tuple[float | None, str | None]:
    """
    Select BT value following BT_PRIORITY.
    Returns (value, source_column_name) or (None, None) if absent.
    """
    for col in BT_PRIORITY:
        if col in row and row[col] not in (None, ""):
            try:
                v = float(str(row[col]).strip())
                return v, col
            except (ValueError, TypeError):
                continue
    return None, None


def validate_essential_columns(present_canonical: set[str]) -> None:
    """
    Raise FirmsSchemaError if required source groups not satisfied.
    Allows either acq_date+acq_time OR any timestamp-like column.
    """
    missing_groups = []
    for group in REQUIRED_SOURCE_GROUPS:
        if not any(c in present_canonical for c in group):
            missing_groups.append(group)

    # Special: timestamp group — check alternative combos
    # If we have both acq_date and acq_time, that's okay even if acq_datetime missing
    # Our group already checks; just report
    if missing_groups:
        details = "; ".join(f"need one of {g}" for g in missing_groups)
        raise FirmsSchemaError(
            f"Missing essential FIRMS column(s): {details}. "
            f"Present columns (canonical): {sorted(present_canonical)}. "
            f"Expected at least latitude, longitude, and acq_date+acq_time or timestamp, plus satellite/instrument if available."
        )

    # Also need satellite or instrument to derive satellite
    if "satellite" not in present_canonical and "instrument" not in present_canonical:
        # Not fatal — we will default to VIIRS, but warn via caller
        pass
