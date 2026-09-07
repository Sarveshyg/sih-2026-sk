"""
ml/geospatial/osm_downloader.py — Robust batched Overpass download for industrial facilities.

Features:
- Configurable User-Agent via OSM_USER_AGENT env (default SIH2026-ThermalSourceDetection/0.1)
- Configurable endpoints via OSM_OVERPASS_ENDPOINTS env (comma-separated)
- Proper Accept headers, no browser spoofing
- Per-status error handling (400,401/403,406,429 with Retry-After, 5xx, timeout)
- Short timeouts (connect 15s, read 60s) to avoid 180s hangs; dead endpoints skipped quickly
- Detection-driven tiled queries (not one giant India query) — groups FIRMS detections into spatial cells
- Caches per tile with metadata (query region, hash, endpoint, timestamp, User-Agent)
- Resume support, deduplication, report, dry-run, test-endpoints CLI
- Documents exact Overpass query and source
"""

from __future__ import annotations

import os
import json
import time
import math
import hashlib
import logging
import csv
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

try:
    import requests  # type: ignore
except ImportError:
    requests = None  # type: ignore

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable defaults
# ---------------------------------------------------------------------------
DEFAULT_USER_AGENT = "SIH2026-ThermalSourceDetection/0.1 (OpenStreetMap Overpass research prototype)"
DEFAULT_OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
# Only the verified working endpoint is enabled by default; additional endpoints can be
# added via OSM_OVERPASS_ENDPOINTS env for failover. Previously failing endpoints
# (kumi read timeout, ru connect timeout) are disabled by default.
FALLBACK_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
]

INDIA_BBOX = "68,6,98,36"
INDIA_BBOX_OVERPASS = "6,68,36,98"
CACHE_DEFAULT = Path("data/geospatial/cache/osm_india.json")
# Targeted cache namespace for corrected thermal query (wind turbines excluded)
# Old broad cache remains at data/geospatial/cache/tiles/ (preserved, not overwritten)
CACHE_TILED_DIR = Path("data/geospatial/cache/targeted_tiles")
# Legacy broad cache path (kept for comparison)
CACHE_TILED_DIR_BROAD = Path("data/geospatial/cache/tiles")
REPORT_PATH = Path("data/geospatial/cache/osm_download_report.json")

# Retry / timeout config
DEFAULT_RETRIES = 2  # per endpoint, then failover
DEFAULT_BACKOFF = 2.0
# Use tuple timeout: (connect, read) to avoid 180s hang
DEFAULT_CONNECT_TIMEOUT = 15
DEFAULT_READ_TIMEOUT = 60
# For backward compat, DEFAULT_TIMEOUT is combined
DEFAULT_TIMEOUT = (DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT)

# Tiling defaults — chosen based on 6,523 India detections distribution
# India extent ~30x30 degrees; 1.0 deg tiles (~110km) produce ~120 tiles with detections (not 900)
# Buffer 0.05 deg (~5km) ensures facilities near tile edges are not missed
DEFAULT_TILE_DEG = 1.0
DEFAULT_BUFFER_DEG = 0.05  # ~5km


def get_user_agent() -> str:
    return os.environ.get("OSM_USER_AGENT", DEFAULT_USER_AGENT).strip() or DEFAULT_USER_AGENT


def get_endpoints() -> List[str]:
    env = os.environ.get("OSM_OVERPASS_ENDPOINTS", "").strip()
    if env:
        eps = [e.strip() for e in env.split(",") if e.strip()]
        if eps:
            return eps
    return FALLBACK_ENDPOINTS


def _headers() -> Dict[str, str]:
    return {
        "User-Agent": get_user_agent(),
        "Accept": "application/json, application/osm3s, */*",
        "Content-Type": "application/x-www-form-urlencoded",
    }


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------
def build_overpass_query(bbox: str = INDIA_BBOX_OVERPASS) -> str:
    """
    Build *TARGETED* Overpass QL for thermal/industrial context.

    This is the corrected query (wind turbines removed). See git history for old broad query.
    - Industrial: industrial=*, landuse=industrial, building=industrial
    - Works/facilities: man_made=works
    - Oil/gas: man_made=petroleum_well, industrial~oil|gas|refinery/steel/cement/chemical/manufacturing
    - Storage tanks: man_made=storage_tank (water tanks will be classified as 'other' post-hoc, not industrial)
    - Power: plant and substation only; generator omitted entirely (previously retrieved 6,644 wind turbines per tile)

    Thermal/industrial context only — not every power generator.
    bbox: "south,west,north,east"
    Documented source: Overpass API — https://wiki.openstreetmap.org/wiki/Overpass_API
    """
    query = f"""
[out:json][timeout:90];
(
  // Industrial core
  node["industrial"]({bbox});
  way["industrial"]({bbox});
  node["landuse"="industrial"]({bbox});
  way["landuse"="industrial"]({bbox});
  node["building"="industrial"]({bbox});
  way["building"="industrial"]({bbox});
  // Works / facilities
  node["man_made"="works"]({bbox});
  way["man_made"="works"]({bbox});
  // Oil/gas
  node["man_made"="petroleum_well"]({bbox});
  way["man_made"="petroleum_well"]({bbox});
  node["man_made"="storage_tank"]({bbox});
  way["man_made"="storage_tank"]({bbox});
  // Power — only plants/substations, NOT generators (wind turbines excluded)
  node["power"="plant"]({bbox});
  way["power"="plant"]({bbox});
  node["power"="substation"]({bbox});
  way["power"="substation"]({bbox});
);
out center;
"""
    return query.strip()


def build_broad_overpass_query(bbox: str = INDIA_BBOX_OVERPASS) -> str:
    """Previous broad query (kept for comparison, includes wind generators)."""
    query = f"""
[out:json][timeout:90];
(
  node["industrial"]({bbox});
  way["industrial"]({bbox});
  node["landuse"="industrial"]({bbox});
  way["landuse"="industrial"]({bbox});
  node["man_made"="works"]({bbox});
  way["man_made"="works"]({bbox});
  node["man_made"="petroleum_well"]({bbox});
  way["man_made"="petroleum_well"]({bbox});
  node["man_made"="storage_tank"]({bbox});
  way["man_made"="storage_tank"]({bbox});
  node["power"="plant"]({bbox});
  way["power"="plant"]({bbox});
  node["power"="generator"]({bbox});
  way["power"="generator"]({bbox});
  node["power"="substation"]({bbox});
  way["power"="substation"]({bbox});
  node["industrial"~"oil|gas|refinery"]({bbox});
  way["industrial"~"oil|gas|refinery"]({bbox});
  node["building"="industrial"]({bbox});
  way["building"="industrial"]({bbox});
);
out center;
"""
    return query.strip()


def build_overpass_query_for_tile(south: float, west: float, north: float, east: float) -> str:
    bbox = f"{south:.4f},{west:.4f},{north:.4f},{east:.4f}"
    return build_overpass_query(bbox=bbox)


# ---------------------------------------------------------------------------
# HTTP helpers with per-status handling
# ---------------------------------------------------------------------------
def _parse_retry_after(headers: Dict[str, Any]) -> Optional[float]:
    ra = headers.get("Retry-After") or headers.get("retry-after")
    if ra is None:
        return None
    try:
        return float(str(ra).strip())
    except Exception:
        return None


def fetch_overpass(
    query: str,
    endpoint: str = DEFAULT_OVERPASS_ENDPOINT,
    max_retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    timeout: Any = DEFAULT_TIMEOUT,
    session=None,
) -> Dict[str, Any]:
    """POST query to Overpass with detailed per-status handling. Returns JSON."""
    if requests is None:
        raise RuntimeError("requests required for Overpass (pip install requests)")
    sess = session or requests.Session()
    headers = _headers()
    # Normalize timeout to tuple
    if isinstance(timeout, (int, float)):
        timeout_tuple = (DEFAULT_CONNECT_TIMEOUT, int(timeout))
    else:
        timeout_tuple = timeout

    last_exc: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            resp = sess.post(endpoint, data={"data": query}, timeout=timeout_tuple, headers=headers)
            status = resp.status_code
            # 200 success
            if status == 200:
                try:
                    return resp.json()
                except Exception:
                    return {"elements": []}
            # 400 bad request — do not retry
            if status == 400:
                raise RuntimeError(f"Overpass 400 Bad Request at {endpoint}: {resp.text[:500]}")
            # 401/403 auth/permission — do not retry
            if status in (401, 403):
                raise RuntimeError(f"Overpass {status} at {endpoint}: {resp.text[:300]}")
            # 406 not acceptable — likely header/content negotiation, at most one retry then failover
            if status == 406:
                # Log and raise immediately to trigger failover, no long retries
                raise RuntimeError(f"Overpass 406 Not Acceptable at {endpoint}: {resp.text[:300]}")
            # 429 rate limiting — respect Retry-After
            if status == 429:
                if attempt < max_retries:
                    retry_after = _parse_retry_after(resp.headers)
                    sleep = retry_after if retry_after is not None else backoff * (2 ** attempt)
                    sleep = min(sleep, 30)  # bounded
                    log.warning(f"Overpass 429 at {endpoint}, retry {attempt+1}/{max_retries} in {sleep:.1f}s (Retry-After: {retry_after})")
                    time.sleep(sleep)
                    continue
                raise RuntimeError(f"Overpass 429 rate limited at {endpoint}: {resp.text[:300]}")
            # 5xx retry with backoff, then failover
            if status in (500, 502, 503, 504):
                if attempt < max_retries:
                    sleep = backoff * (2 ** attempt)
                    log.warning(f"Overpass {status} at {endpoint}, retry {attempt+1}/{max_retries} in {sleep:.1f}s")
                    time.sleep(sleep)
                    continue
                raise RuntimeError(f"Overpass {status} at {endpoint}: {resp.text[:500]}")
            # Other 4xx — don't retry
            if 400 <= status < 500:
                raise RuntimeError(f"Overpass {status} at {endpoint}: {resp.text[:500]}")
            # Other — raise
            raise RuntimeError(f"Overpass {status} at {endpoint}: {resp.text[:500]}")
        except Exception as e:
            # If it's already a RuntimeError with 4xx, don't retry
            msg = str(e)
            if "400 Bad Request" in msg or "401" in msg or "403" in msg or "406 Not Acceptable" in msg:
                raise
            # Timeout — retry at most once with short timeout, then failover
            is_timeout = "Timeout" in type(e).__name__ or "Timeout" in str(e) or "ConnectTimeout" in str(e)
            if is_timeout:
                if attempt < min(1, max_retries):  # at most one retry for timeout
                    log.warning(f"Overpass timeout at {endpoint}, retry {attempt+1} in {backoff:.1f}s: {e!r}")
                    time.sleep(backoff)
                    continue
                raise RuntimeError(f"Overpass timeout at {endpoint}: {e!r}")
            # Other exception — retry if we have attempts left and it's retryable
            if attempt < max_retries:
                # For generic exception, treat as retryable once
                log.warning(f"Overpass exception at {endpoint} retry {attempt+1}/{max_retries}: {e!r}")
                time.sleep(backoff * (2 ** attempt))
                continue
            last_exc = e
            raise
    raise RuntimeError(f"Overpass max retries exceeded at {endpoint}: {last_exc}")


# ---------------------------------------------------------------------------
# Tiling
# ---------------------------------------------------------------------------
def generate_tiles(
    input_csv: Path,
    tile_deg: float = DEFAULT_TILE_DEG,
    buffer_deg: float = DEFAULT_BUFFER_DEG,
) -> List[Dict[str, Any]]:
    """
    Generate spatial tiles covering FIRMS detections.
    - Groups detections into grid cells of tile_deg degrees
    - Adds buffer_deg buffer around each tile
    - Returns list of tiles sorted deterministically (by south, west)
    Each tile: {id, south, west, north, east, buffered_bbox, count, hash}
    Deduplication: only tiles with at least 1 detection.
    Documented: tile_deg=1.0 (~110km) with 0.05 deg (~5km) buffer chosen because
    India extent 30x30 deg would be 900 tiles, but only ~120-180 tiles contain detections
    from 6,523 points (sparse), avoiding 6,523 individual requests while keeping
    query regions small enough for Overpass (not one giant India query).
    """
    input_csv = Path(input_csv)
    if not input_csv.exists():
        raise FileNotFoundError(f"FIRMS CSV not found: {input_csv}")
    # Read lat/lon
    lats: List[float] = []
    lons: List[float] = []
    with input_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        lat_key = next((k for k in reader.fieldnames or [] if k.lower() in ("latitude", "lat", "y")), None)
        lon_key = next((k for k in reader.fieldnames or [] if k.lower() in ("longitude", "lon", "long", "lng", "x")), None)
        if not lat_key or not lon_key:
            raise ValueError(f"Cannot find lat/lon columns in {reader.fieldnames}")
        for row in reader:
            try:
                lats.append(float(row[lat_key]))
                lons.append(float(row[lon_key]))
            except Exception:
                continue
    # Group into grid cells
    cell_counts: Dict[Tuple[int, int], int] = {}
    cell_bounds: Dict[Tuple[int, int], Dict[str, float]] = {}
    for lat, lon in zip(lats, lons):
        # Cell index by tile_deg
        # Use floor division on lat/lon
        # For lat: south .. north, for lon: west .. east
        # Use int(lat // tile_deg) etc. Need to handle negative? India lat 6-36 positive, lon 68-98 positive
        lat_idx = int(math.floor(lat / tile_deg))
        lon_idx = int(math.floor(lon / tile_deg))
        key = (lat_idx, lon_idx)
        cell_counts[key] = cell_counts.get(key, 0) + 1
        # Track bounds for buffered bbox
        if key not in cell_bounds:
            # Base cell bounds
            south = lat_idx * tile_deg
            west = lon_idx * tile_deg
            north = south + tile_deg
            east = west + tile_deg
            # Add buffer
            cell_bounds[key] = {
                "south": max(-90, south - buffer_deg),
                "west": max(-180, west - buffer_deg),
                "north": min(90, north + buffer_deg),
                "east": min(180, east + buffer_deg),
            }
    # Build sorted tiles deterministically (by south, west)
    tiles: List[Dict[str, Any]] = []
    for key in sorted(cell_bounds.keys()):
        bounds = cell_bounds[key]
        # Hash for cache filename: hash of bbox string
        bbox_str = f"{bounds['south']:.4f},{bounds['west']:.4f},{bounds['north']:.4f},{bounds['east']:.4f}"
        h = hashlib.sha1(bbox_str.encode()).hexdigest()[:8]
        tile_id = f"tile_{key[0]}_{key[1]}_{h}"
        tiles.append(
            {
                "id": tile_id,
                "south": bounds["south"],
                "west": bounds["west"],
                "north": bounds["north"],
                "east": bounds["east"],
                "bbox": bbox_str,
                "count": cell_counts[key],
                "hash": h,
                "tile_deg": tile_deg,
                "buffer_deg": buffer_deg,
            }
        )
    # Sort deterministically
    tiles.sort(key=lambda t: (t["south"], t["west"]))
    return tiles


def estimate_tile_stats(input_csv: Path, tile_deg: float = DEFAULT_TILE_DEG, buffer_deg: float = DEFAULT_BUFFER_DEG) -> Dict[str, Any]:
    tiles = generate_tiles(input_csv, tile_deg=tile_deg, buffer_deg=buffer_deg)
    # Read total detections
    import csv as _csv

    with Path(input_csv).open("r", encoding="utf-8") as f:
        total = sum(1 for _ in _csv.DictReader(f))
    return {
        "input": str(input_csv),
        "total_detections": total,
        "tile_deg": tile_deg,
        "buffer_deg": buffer_deg,
        "buffer_km": round(buffer_deg * 111.32, 1),
        "num_tiles": len(tiles),
        "detections_per_tile": {t["id"]: t["count"] for t in tiles},
        "avg_per_tile": round(total / len(tiles), 1) if tiles else 0,
        "max_per_tile": max((t["count"] for t in tiles), default=0),
        "min_per_tile": min((t["count"] for t in tiles), default=0),
        "estimated_queries": len(tiles),
        "note": "One query per tile with OSM industrial/power/man_made tags, not per detection (6523 -> ~120 tiles)",
    }


# ---------------------------------------------------------------------------
# Tiled download with caching, deduplication, resume
# ---------------------------------------------------------------------------
def _tile_cache_path(cache_dir: Path, tile: Dict[str, Any]) -> Path:
    return cache_dir / f"{tile['id']}.json"


def _tile_meta_path(cache_dir: Path, tile: Dict[str, Any]) -> Path:
    return cache_dir / f"{tile['id']}.meta.json"


def download_tiled_osm(
    input_csv: Path,
    cache_dir: Path = CACHE_TILED_DIR,
    endpoints: Optional[List[str]] = None,
    tile_deg: float = DEFAULT_TILE_DEG,
    buffer_deg: float = DEFAULT_BUFFER_DEG,
    force: bool = False,
    max_retries: int = DEFAULT_RETRIES,
    timeout: Any = DEFAULT_TIMEOUT,
    session=None,
) -> Dict[str, Any]:
    """
    Download OSM facilities tiled by FIRMS detections.
    - Generates tiles from input_csv
    - For each tile, checks cache; if exists and not force, skip
    - Else fetches via Overpass with retry/failover
    - Deduplicates OSM elements globally by type/id
    - Writes report to data/geospatial/cache/osm_download_report.json
    Returns report dict.
    """
    input_csv = Path(input_csv)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    endpoints = endpoints or get_endpoints()
    # Normalize timeout
    if isinstance(timeout, (int, float)):
        timeout = (DEFAULT_CONNECT_TIMEOUT, int(timeout))
    session = session or (requests.Session() if requests else None)

    tiles = generate_tiles(input_csv, tile_deg=tile_deg, buffer_deg=buffer_deg)
    start_time = time.time()
    results: List[Dict[str, Any]] = []
    all_elements: Dict[str, Dict[str, Any]] = {}
    failed_tiles: List[Dict[str, Any]] = []
    successful_tiles = 0
    cache_hits = 0

    for tile in tiles:
        cache_path = _tile_cache_path(cache_dir, tile)
        meta_path = _tile_meta_path(cache_dir, tile)
        # Check cache
        if cache_path.exists() and not force:
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "elements" in data:
                    # Deduplicate
                    for el in data["elements"]:
                        key = f"{el.get('type')}/{el.get('id')}"
                        if key not in all_elements:
                            all_elements[key] = el
                    results.append(
                        {
                            "tile_id": tile["id"],
                            "bbox": tile["bbox"],
                            "count": tile["count"],
                            "status": "cache_hit",
                            "elements": len(data["elements"]),
                            "endpoint": "cache",
                        }
                    )
                    cache_hits += 1
                    successful_tiles += 1
                    continue
            except Exception:
                pass

        # Need to fetch
        query = build_overpass_query(bbox=tile["bbox"])
        query_hash = hashlib.sha1(query.encode()).hexdigest()[:8]
        tile_success = False
        last_err = None
        endpoint_used = None
        retry_count = 0
        for ep in endpoints:
            try:
                # Use fetch_overpass with per-tile retry
                # For tiled, we use shorter timeout per tile
                data = fetch_overpass(query, endpoint=ep, max_retries=max_retries, timeout=timeout, session=session)
                # Validate
                if not isinstance(data, dict) or "elements" not in data:
                    raise ValueError("Invalid Overpass response")
                # Write cache with metadata
                cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                meta = {
                    "tile_id": tile["id"],
                    "bbox": tile["bbox"],
                    "query_hash": query_hash,
                    "endpoint": ep,
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "user_agent": get_user_agent(),
                    "elements": len(data["elements"]),
                    "tile_deg": tile_deg,
                    "buffer_deg": buffer_deg,
                    "detections_in_tile": tile["count"],
                }
                meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
                # Deduplicate
                for el in data["elements"]:
                    key = f"{el.get('type')}/{el.get('id')}"
                    if key not in all_elements:
                        all_elements[key] = el
                results.append(
                    {
                        "tile_id": tile["id"],
                        "bbox": tile["bbox"],
                        "count": tile["count"],
                        "status": "fetched",
                        "elements": len(data["elements"]),
                        "endpoint": ep,
                    }
                )
                successful_tiles += 1
                tile_success = True
                endpoint_used = ep
                # Rate limit spacing
                time.sleep(0.5)
                break
            except Exception as e:
                last_err = e
                # If 400, don't retry other endpoints? Actually 400 is query problem, no point retrying other endpoints with same query
                if "400 Bad Request" in str(e):
                    results.append(
                        {
                            "tile_id": tile["id"],
                            "bbox": tile["bbox"],
                            "count": tile["count"],
                            "status": "failed",
                            "error": str(e)[:500],
                            "endpoint": ep,
                        }
                    )
                    failed_tiles.append({"tile_id": tile["id"], "bbox": tile["bbox"], "error": str(e)[:500]})
                    tile_success = False
                    break
                # For 406, move to next endpoint after at most one retry (handled in fetch)
                # Continue to next endpoint
                log.warning(f"Tile {tile['id']} failed at {ep}: {e}")
                # If endpoint is dead (timeout), skip it for remaining tiles? For now, just continue
                continue
        if not tile_success and not any(r["tile_id"] == tile["id"] and r["status"] == "failed" for r in results):
            # All endpoints failed
            results.append(
                {
                    "tile_id": tile["id"],
                    "bbox": tile["bbox"],
                    "count": tile["count"],
                    "status": "failed",
                    "error": str(last_err)[:500] if last_err else "unknown",
                    "endpoint": endpoints[0] if endpoints else "none",
                }
            )
            failed_tiles.append({"tile_id": tile["id"], "bbox": tile["bbox"], "error": str(last_err)[:500] if last_err else "unknown"})

    elapsed = time.time() - start_time
    # Write combined cache for backward compat
    combined_path = cache_dir.parent / "osm_india.json"
    if all_elements:
        combined_data = {"elements": list(all_elements.values()), "generator": "tiled download", "tiles": len(tiles)}
        try:
            combined_path.write_text(json.dumps(combined_data, indent=2), encoding="utf-8")
            # Also GeoJSON
            try:
                from .osm_enrichment import overpass_to_geojson

                gj = overpass_to_geojson(combined_data)
                geojson_path = combined_path.with_suffix(".geojson")
                geojson_path.write_text(json.dumps(gj, indent=2), encoding="utf-8")
            except Exception:
                pass
        except Exception:
            pass

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "input": str(input_csv),
        "tile_deg": tile_deg,
        "buffer_deg": buffer_deg,
        "buffer_km": round(buffer_deg * 111.32, 1),
        "num_tiles": len(tiles),
        "successful_tiles": successful_tiles,
        "failed_tiles": len(failed_tiles),
        "failed_details": failed_tiles[:10],
        "cache_hits": cache_hits,
        "total_osm_elements": len(all_elements),
        "unique_osm_ids": len(all_elements),
        "endpoint_used": endpoints[0] if endpoints else None,
        "endpoints_tried": endpoints,
        "user_agent": get_user_agent(),
        "elapsed_seconds": round(elapsed, 1),
        "results": results[:20],  # first 20 for brevity
        "note": "Tiled download: one query per spatial tile covering FIRMS detections, deduplicated globally. Resume: cached tiles skipped unless --force.",
    }
    report_path = cache_dir.parent / "osm_download_report.json"
    # Also write to cache_dir
    (cache_dir / "osm_download_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


# ---------------------------------------------------------------------------
# Legacy single-bbox download (kept for backward compat)
# ---------------------------------------------------------------------------
def download_osm_india(
    cache_path: Path = CACHE_DEFAULT,
    endpoint: str = DEFAULT_OVERPASS_ENDPOINT,
    bbox: str = INDIA_BBOX_OVERPASS,
    force: bool = False,
    max_retries: int = DEFAULT_RETRIES,
    backoff: float = 2.0,
    timeout: Any = DEFAULT_TIMEOUT,
    session=None,
) -> Path:
    """
    Download OSM India facilities via Overpass, cache to cache_path.
    Respects cache: if file exists and valid and not force, skip.
    Returns cache path.
    DEPRECATED: Use download_tiled_osm for detection-driven tiling.
    """
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists() and not force:
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "elements" in data and len(data["elements"]) > 0:
                log.info(f"Using cached OSM {cache_path} ({len(data['elements'])} elements)")
                return cache_path
        except Exception:
            pass

    query = build_overpass_query(bbox=bbox)
    log.info(f"Fetching OSM India facilities from {endpoint} (bbox {bbox})")
    # Try primary endpoint, then fallbacks
    endpoints = get_endpoints()
    # Ensure endpoint is first
    endpoints = [endpoint] + [e for e in endpoints if e != endpoint]
    last_err = None
    for ep in endpoints:
        try:
            data = fetch_overpass(query, endpoint=ep, max_retries=max_retries, backoff=backoff, timeout=timeout, session=session)
            if not isinstance(data, dict) or "elements" not in data:
                raise ValueError("Invalid Overpass response: missing elements")
            cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            log.info(f"Cached OSM to {cache_path} ({len(data['elements'])} elements) from {ep}")
            geojson_path = cache_path.with_suffix(".geojson")
            try:
                from .osm_enrichment import overpass_to_geojson

                gj = overpass_to_geojson(data)
                geojson_path.write_text(json.dumps(gj, indent=2), encoding="utf-8")
                log.info(f"Wrote GeoJSON {geojson_path} ({len(gj.get('features', []))} features)")
            except Exception as e:
                log.warning(f"Failed to convert OSM to GeoJSON: {e}")
            return cache_path
        except Exception as e:
            last_err = e
            # Don't retry 400 again
            if "400 Bad Request" in str(e):
                raise
            log.warning(f"Overpass fetch failed at {ep}: {e}")
            time.sleep(1.0)
            continue
    raise RuntimeError(f"All Overpass endpoints failed. Last error: {last_err}")


def load_cached_osm(cache_path: Path = CACHE_DEFAULT) -> Optional[Dict[str, Any]]:
    p = Path(cache_path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _test_endpoints(endpoints: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Send tiny query to each endpoint."""
    endpoints = endpoints or get_endpoints()
    tiny_query = """
[out:json][timeout:10];
node["industrial"](19.0,72.8,19.1,72.9);
out count;
"""
    # Even smaller: just count
    tiny_query = '[out:json][timeout:10]; node["industrial"](19.0,72.8,19.1,72.9); out count;'
    results = []
    for ep in endpoints:
        start = time.time()
        try:
            data = fetch_overpass(tiny_query, endpoint=ep, max_retries=1, timeout=(10, 30))
            elapsed = time.time() - start
            # Count elements if any
            count = len(data.get("elements", [])) if isinstance(data, dict) else 0
            results.append({"endpoint": ep, "status": 200, "elapsed": round(elapsed, 2), "success": True, "elements": count})
        except Exception as e:
            elapsed = time.time() - start
            results.append({"endpoint": ep, "status": None, "elapsed": round(elapsed, 2), "success": False, "error": str(e)[:500]})
    return results


def main(argv: Optional[List[str]] = None):
    import argparse

    parser = argparse.ArgumentParser(description="OSM Overpass downloader for industrial facilities (tiled)")
    sub = parser.add_subparsers(dest="cmd")

    # test-endpoints
    parser.add_argument("--test-endpoints", action="store_true", help="Test Overpass endpoints connectivity")

    # dry-run
    parser.add_argument("--dry-run", action="store_true", help="Dry run: estimate tiles without contacting Overpass")
    parser.add_argument("--input", default="data/firms/processed/firms_india.csv", help="FIRMS India CSV for tiling")
    parser.add_argument("--tile-deg", type=float, default=DEFAULT_TILE_DEG, help="Tile size degrees")
    parser.add_argument("--buffer-deg", type=float, default=DEFAULT_BUFFER_DEG, help="Buffer degrees")

    # download (legacy single bbox)
    parser.add_argument("--force", action="store_true", help="Force re-download even if cached")

    # tiled download
    parser.add_argument("--tiled", action="store_true", help="Use tiled download (detection-driven)")

    args = parser.parse_args(argv)

    # Handle test-endpoints
    if args.test_endpoints:
        print("Testing Overpass endpoints...")
        print(f"User-Agent: {get_user_agent()}")
        results = _test_endpoints()
        for r in results:
            status = "OK" if r["success"] else "FAIL"
            detail = f"{r.get('elements',0)} elements" if r["success"] else r.get("error","")[:200]
            print(f"{status} {r['endpoint']} - {r.get('elapsed','?')}s {detail}")
        print(json.dumps(results, indent=2))
        return

    if args.dry_run:
        input_csv = Path(args.input)
        stats = estimate_tile_stats(input_csv, tile_deg=args.tile_deg, buffer_deg=args.buffer_deg)
        print(json.dumps(stats, indent=2))
        print(f"\nDry run: {stats['num_tiles']} tiles for {stats['total_detections']} detections (tile {args.tile_deg} deg + buffer {args.buffer_deg} deg ~{stats['buffer_km']}km)")
        return

    # If no subcommand and not dry-run/test, show help
    if not args.test_endpoints and not args.dry_run and not args.tiled:
        parser.print_help()
        return

    if args.tiled:
        report = download_tiled_osm(
            input_csv=Path(args.input),
            cache_dir=CACHE_TILED_DIR,
            tile_deg=args.tile_deg,
            buffer_deg=args.buffer_deg,
            force=args.force,
        )
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
