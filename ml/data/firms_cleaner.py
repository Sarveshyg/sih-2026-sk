"""
ml/data/firms_cleaner.py — Validation, cleaning, normalization.

- Coordinate validation (-90..90, -180..180), globally usable (no India hard-box)
- Numeric validation (no silent zero-fabrication)
- Timestamp: acq_date + acq_time → UTC-aware datetime → ISO8601Z
- Confidence: h/n/l or 0-100 → 0-100 float
- Brightness temperature: BT_PRIORITY selection documented in firms_schema
- Deterministic IDs
- Geospatial/temporal sanity checks
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional, Any

from .firms_schema import select_brightness_temperature, BT_PRIORITY

# Confidence mapping for VIIRS/MODIS 'l'/'n'/'h'
CONFIDENCE_MAP = {"l": 30.0, "n": 60.0, "h": 90.0}


def _parse_float(raw: Any, field: str) -> tuple[float | None, str | None]:
    if raw is None or str(raw).strip() == "":
        return None, f"missing {field}"
    s = str(raw).strip()
    try:
        v = float(s)
        if v != v:  # NaN
            return None, f"NaN {field}"
        return v, None
    except (ValueError, TypeError):
        return None, f"malformed {field}: {raw!r}"


def _normalize_confidence(raw: Any) -> tuple[float | None, str | None]:
    if raw is None or str(raw).strip() == "":
        return None, "missing confidence"
    s = str(raw).strip().lower()
    # MODIS numeric 0-100 or VIIRS l/n/h
    if s in CONFIDENCE_MAP:
        return CONFIDENCE_MAP[s], None
    # Some FIRMS exports use numeric strings
    try:
        v = float(s)
        # Clamp to 0-100 but flag out-of-range
        if v < 0 or v > 100:
            # Could be 0-1 confidence; if 0-1, scale
            if 0 <= v <= 1:
                return v * 100, None
            return None, f"confidence out of range 0-100: {raw!r}"
        return v, None
    except (ValueError, TypeError):
        return None, f"malformed confidence: {raw!r}"


def _parse_timestamp(row: Dict[str, Any]) -> tuple[datetime | None, str | None]:
    """
    Convert FIRMS acq_date + acq_time to UTC-aware datetime.

    FIRMS acq_time is typically HHMM (e.g., "1342" = 13:42 UTC) or HH:MM.
    FIRMS acq_date is YYYY-MM-DD.
    Also supports single 'acq_datetime' or 'timestamp' ISO strings.
    Returns (datetime, error).
    """
    # Check combined ISO first
    for key in ("acq_datetime", "timestamp"):
        if row.get(key) not in (None, ""):
            raw = str(row[key]).strip()
            # Try ISO parse
            try:
                # Handle Z suffix
                iso = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
                dt = datetime.fromisoformat(iso)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                return dt, None
            except Exception:
                pass  # fall through to acq_date path

    acq_date = row.get("acq_date")
    acq_time = row.get("acq_time")

    if acq_date is None or str(acq_date).strip() == "":
        return None, "missing acq_date"

    date_str = str(acq_date).strip()
    time_str = str(acq_time).strip() if acq_time is not None else "0000"

    # Parse date
    try:
        # FIRMS uses YYYY-MM-DD
        date_part = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        # Try YYYY/MM/DD
        try:
            date_part = datetime.strptime(date_str, "%Y/%m/%d")
        except ValueError:
            return None, f"malformed acq_date: {date_str!r}"

    # Parse time: HHMM or HH:MM or H:MM
    t = time_str.strip()
    hour = 0
    minute = 0
    sec = 0
    try:
        if ":" in t:
            parts = t.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            if len(parts) > 2:
                sec = int(float(parts[2]))
        else:
            # HHMM — pad to 4 digits
            t_padded = t.zfill(4)
            if len(t_padded) == 4:
                hour = int(t_padded[:2])
                minute = int(t_padded[2:4])
            elif len(t_padded) <= 2:
                hour = int(t_padded)
            else:
                return None, f"malformed acq_time: {time_str!r}"
        if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= sec <= 59):
            return None, f"acq_time out of range: {time_str!r}"
    except (ValueError, TypeError):
        return None, f"malformed acq_time: {time_str!r}"

    dt = datetime(
        date_part.year, date_part.month, date_part.day, hour, minute, sec, tzinfo=timezone.utc
    )
    return dt, None


def _normalize_satellite(row: Dict[str, Any]) -> str:
    """
    Derive canonical satellite string from satellite or instrument.
    Examples: "VIIRS", "N", "NOAA-20", "Terra", "Aqua", "1" (VIIRS), "MODIS".
    Fallback: VIIRS if unknown.
    """
    sat = row.get("satellite")
    instr = row.get("instrument")
    # Instrument hints
    # VIIRS instrument values: "VIIRS", "VIIRS S-NPP", etc.
    # MODIS instrument values: "MODIS"
    raw = None
    if sat not in (None, ""):
        raw = str(sat).strip()
    elif instr not in (None, ""):
        raw = str(instr).strip()

    if raw is None or raw == "":
        return "VIIRS"

    # Normalize known variants
    r = raw.strip()
    # Handle single letter codes: N = VIIRS NOAA-20? But keep as is upper
    # Map Terra/Aqua to MODIS Terra/Aqua for clarity
    if r.lower() in ("terra", "aqua"):
        return f"MODIS_{r.upper()}"
    if r.lower() in ("modis",):
        return "MODIS"
    if r.lower() in ("viirs", "v", "n", "j1", "npp"):
        # Use VIIRS as generic if truncated
        # Preserve NOAA-20/21 exact if given
        if r.upper().startswith("NOAA"):
            return r.upper()
        return "VIIRS"
    # For NOAA-20, NOAA-21 keep verbatim upper
    if r.upper().startswith("NOAA"):
        return r.upper()
    return r.upper()


def _deterministic_id(satellite: str, timestamp: datetime, lat: float, lon: float) -> str:
    """
    Deterministic event ID: FIRMS_<8hex>.

    Hash input: satellite|timestamp_iso|lat(5dec)|lon(5dec)
    Stable across runs; same input → same ID.
    """
    ts_iso = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = f"{satellite}|{ts_iso}|{lat:.5f}|{lon:.5f}"
    h = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8].upper()
    return f"FIRMS_{h}"


def clean_row(row: Dict[str, Any], row_index: int) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None, Dict[str, str]]:
    """
    Clean a single canonical row.

    Returns (cleaned_event_dict or None, error_info or None, stats_flags).
    cleaned_event_dict matches ThermalEvent fields when valid.
    error_info includes row_index and reason when invalid.
    stats_flags records missing counts for report.
    """
    flags: Dict[str, str] = {}

    # Latitude
    lat, lat_err = _parse_float(row.get("latitude"), "latitude")
    if lat_err or lat is None:
        return None, {"row": row_index, "reason": lat_err or "missing latitude", "raw": row}, {"missing": "latitude"}
    if lat < -90 or lat > 90:
        return None, {"row": row_index, "reason": f"latitude out of range: {lat}", "raw": row}, {}

    # Longitude
    lon, lon_err = _parse_float(row.get("longitude"), "longitude")
    if lon_err or lon is None:
        return None, {"row": row_index, "reason": lon_err or "missing longitude", "raw": row}, {"missing": "longitude"}
    if lon < -180 or lon > 180:
        return None, {"row": row_index, "reason": f"longitude out of range: {lon}", "raw": row}, {}

    # Timestamp
    ts, ts_err = _parse_timestamp(row)
    if ts_err or ts is None:
        return None, {"row": row_index, "reason": ts_err or "missing timestamp", "raw": row}, {}

    # FRP — missing/invalid is invalid row (do not fabricate)
    frp, frp_err = _parse_float(row.get("frp"), "frp")
    if frp_err or frp is None:
        # Check if frp column was empty string → missing
        raw_frp = row.get("frp")
        if raw_frp is None or str(raw_frp).strip() == "":
            flags["missing_frp"] = "1"
            return None, {"row": row_index, "reason": "missing frp", "raw": row}, flags
        return None, {"row": row_index, "reason": frp_err or "missing frp", "raw": row}, flags
    if frp < 0:
        flags["invalid_frp"] = "1"
        return None, {"row": row_index, "reason": f"negative frp: {frp}", "raw": row}, flags

    # Brightness temperature — selected per BT_PRIORITY
    bt_value, bt_source = select_brightness_temperature(row)
    if bt_value is None:
        flags["missing_bt"] = "1"
        return None, {"row": row_index, "reason": "missing brightness_temperature (no bright_ti4/ti5/t31)", "raw": row}, flags
    if bt_value < 0:
        flags["invalid_bt"] = "1"
        return None, {"row": row_index, "reason": f"invalid brightness_temperature: {bt_value}", "raw": row}, flags
    # Physical sanity: BT should be 200-600K plausible
    if not (200 <= bt_value <= 600):
        # Still allow but flag; treat out-of-range as invalid for quality
        flags["bt_out_of_range"] = "1"
        # Not rejecting yet — but document; we will reject if obviously wrong (>1000)
        if bt_value > 1000 or bt_value < 100:
            return None, {"row": row_index, "reason": f"brightness_temperature out of plausible range: {bt_value}", "raw": row}, flags

    # Confidence — missing treated as invalid (do not default silently)
    conf_raw = row.get("confidence")
    conf, conf_err = _normalize_confidence(conf_raw)
    if conf_err or conf is None:
        if conf_raw is None or str(conf_raw).strip() == "":
            flags["missing_confidence"] = "1"
            return None, {"row": row_index, "reason": "missing confidence", "raw": row}, flags
        flags["invalid_confidence"] = "1"
        return None, {"row": row_index, "reason": conf_err, "raw": row}, flags

    # Satellite
    satellite = _normalize_satellite(row)

    # Deterministic ID
    eid = _deterministic_id(satellite, ts, lat, lon)

    # Additional preserved fields (optional)
    extra = {}
    for k in ("daynight", "scan", "track", "version", "instrument"):
        if row.get(k) not in (None, ""):
            extra[k] = row.get(k)

    event = {
        "id": eid,
        "latitude": lat,
        "longitude": lon,
        "frp": frp,
        "brightness_temperature": bt_value,
        "confidence": conf,
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "satellite": satellite,
        # Meta for debugging / audit
        "_bt_source": bt_source,
        "_raw_extra": extra,
    }
    return event, None, flags


def clean_rows(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
    """
    Clean list of canonical rows.
    Returns (valid_events, invalid_entries, missing_counts).
    """
    valid: List[Dict[str, Any]] = []
    invalid: List[Dict[str, Any]] = []
    missing_counts = {"missing_frp": 0, "missing_confidence": 0, "missing_bt": 0}

    for idx, r in enumerate(rows, start=2):  # header is row 1
        ev, err, flags = clean_row(r, idx)
        if ev is not None:
            valid.append(ev)
        else:
            invalid.append(err)
            # Count missing categories
            for k in missing_counts:
                if flags.get(k):
                    missing_counts[k] += 1
            # Also count generic
            if flags.get("missing") == "latitude" or flags.get("missing") == "longitude":
                pass

    return valid, invalid, missing_counts
