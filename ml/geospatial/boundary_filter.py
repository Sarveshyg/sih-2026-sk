"""
ml/geospatial/boundary_filter.py — India country boundary filtering for FIRMS events.

- Loads India polygon/multipolygon from local GeoJSON (WGS84 EPSG:4326)
- Validates geometry
- Filters FIRMS events by point-in-polygon
- Preserves all original FIRMS columns
- Reports inside vs outside counts
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from .geo_utils import point_in_polygon, point_in_multipolygon, HAS_SHAPELY


def load_boundary(path: str | Path) -> Dict[str, Any]:
    """
    Load India boundary GeoJSON. Accepts:
      - FeatureCollection with single India feature
      - Single Feature
      - Geometry dict
    Validates geometry type Polygon/MultiPolygon and WGS84 coordinate ranges.
    Returns dict with keys: geometry_type, geometry, properties, crs
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Boundary file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    # Unwrap
    geometry = None
    properties = {}
    if data.get("type") == "FeatureCollection":
        feats = data.get("features", [])
        if not feats:
            raise ValueError("Boundary FeatureCollection has no features")
        # Prefer IND feature, else first
        feat = None
        for f in feats:
            props = f.get("properties", {})
            if props.get("ISO_A3") == "IND" or props.get("ADMIN") == "India":
                feat = f
                break
        feat = feat or feats[0]
        geometry = feat.get("geometry")
        properties = feat.get("properties", {})
    elif data.get("type") == "Feature":
        geometry = data.get("geometry")
        properties = data.get("properties", {})
    elif data.get("type") in ("Polygon", "MultiPolygon"):
        geometry = data
    else:
        raise ValueError(f"Unsupported boundary GeoJSON type: {data.get('type')}")

    if not geometry or geometry.get("type") not in ("Polygon", "MultiPolygon"):
        raise ValueError(f"Boundary geometry must be Polygon/MultiPolygon, got {geometry.get('type') if geometry else None}")

    coords = geometry.get("coordinates")
    if not coords:
        raise ValueError("Boundary geometry has no coordinates")

    # Basic WGS84 validation: sample coordinates in range
    def _check_ring(ring):
        for pt in ring:
            if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                raise ValueError(f"Malformed coordinate: {pt}")
            lon, lat = float(pt[0]), float(pt[1])
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise ValueError(f"Coordinate out of WGS84 range: lon={lon}, lat={lat}")

    try:
        if geometry["type"] == "Polygon":
            for ring in coords:
                _check_ring(ring)
        else:  # MultiPolygon
            for poly in coords:
                for ring in poly:
                    _check_ring(ring)
    except Exception as e:
        raise ValueError(f"Boundary geometry validation failed: {e}") from e

    # Optional Shapely validation
    if HAS_SHAPELY:
        try:
            import shapely.geometry as sgeom  # type: ignore
            if geometry["type"] == "Polygon":
                gj = sgeom.Polygon(coords[0], coords[1:] or None)
            else:
                gj = sgeom.MultiPolygon([(poly[0], poly[1:] or None) for poly in coords])
            if not gj.is_valid:
                # Try to fix with buffer(0) validation, but keep original for filtering
                fixed = gj.buffer(0)
                if not fixed.is_valid and fixed.is_empty:
                    raise ValueError("Shapely validation: geometry invalid even after buffer(0)")
        except ImportError:
            pass
        except Exception as e:
            raise ValueError(f"Shapely boundary validation failed: {e}") from e

    return {
        "geometry_type": geometry["type"],
        "geometry": geometry,
        "coordinates": coords,
        "properties": properties,
        "crs": "EPSG:4326",
        "crs_name": "WGS84",
        "path": str(p),
    }


def is_inside(lat: float, lon: float, boundary: Dict[str, Any]) -> bool:
    """Check if point (lat, lon) is inside boundary (WGS84)."""
    gtype = boundary["geometry_type"]
    coords = boundary["coordinates"]
    try:
        if gtype == "Polygon":
            return point_in_polygon(lat, lon, coords)
        elif gtype == "MultiPolygon":
            return point_in_multipolygon(lat, lon, coords)
    except Exception:
        return False
    return False


def filter_events(
    events: List[Dict[str, Any]],
    boundary: Dict[str, Any],
    lat_key: str = "latitude",
    lon_key: str = "longitude",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split events into (inside, outside) preserving all columns."""
    inside: List[Dict[str, Any]] = []
    outside: List[Dict[str, Any]] = []
    for ev in events:
        try:
            lat = float(ev[lat_key])
            lon = float(ev[lon_key])
        except Exception:
            # Malformed lat/lon -> treat as outside (preserve count)
            outside.append(ev)
            continue
        if is_inside(lat, lon, boundary):
            inside.append(ev)
        else:
            outside.append(ev)
    return inside, outside


def filter_csv(
    input_path: str | Path,
    output_path: str | Path,
    boundary_path: str | Path = "data/geospatial/boundaries/india.geojson",
    report_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """
    Filter FIRMS CSV by India boundary.
    Preserves all original columns and header order.
    Reports inside vs outside.
    """
    boundary = load_boundary(boundary_path)
    inp = Path(input_path)
    outp = Path(output_path)
    if not inp.exists():
        raise FileNotFoundError(f"Input FIRMS CSV not found: {inp}")
    outp.parent.mkdir(parents=True, exist_ok=True)

    # Read CSV preserving header order
    with inp.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"No header in {inp}")
        fieldnames = reader.fieldnames
        # Detect lat/lon column variants
        lat_key = None
        lon_key = None
        for cand in ["latitude", "lat", "y"]:
            if cand in fieldnames:
                lat_key = cand
                break
        for cand in ["longitude", "lon", "long", "lng", "x"]:
            if cand in fieldnames:
                lon_key = cand
                break
        if not lat_key or not lon_key:
            raise ValueError(f"Cannot find latitude/longitude columns in {fieldnames}")

        rows = list(reader)

    inside, outside = filter_events(rows, boundary, lat_key=lat_key, lon_key=lon_key)

    # Write inside only to output
    with outp.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(inside)

    report: Dict[str, Any] = {
        "boundary_path": str(boundary_path),
        "boundary_type": boundary["geometry_type"],
        "crs": boundary["crs"],
        "crs_name": boundary["crs_name"],
        "input_path": str(inp),
        "output_path": str(outp),
        "original_records": len(rows),
        "records_inside_india": len(inside),
        "records_outside_india": len(outside),
        "inside_pct": round(100 * len(inside) / len(rows), 2) if rows else 0,
        "outside_pct": round(100 * len(outside) / len(rows), 2) if rows else 0,
    }

    # Derive report_path default: alongside output with _report.json suffix
    if report_path is None:
        report_path = outp.with_name(outp.stem + "_filter_report.json")
        # For firms_india.csv -> firms_india_filter_report.json, but task expects filtering report
        # Also write to processed/india_filter_report.json if output is firms_india.csv
    # If caller passed explicit, use that
    rp = Path(report_path)
    # Task expects data/firms/processed/firms_india.csv + JSON report
    # Write primary report
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Also write to data/firms/processed/filter_report.json for convenience if filtering firms_clean.csv
    if "firms_india" in outp.name:
        alt = outp.parent / "india_filter_report.json"
        alt.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report


def main(argv: Optional[List[str]] = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Filter FIRMS CSV by India boundary (WGS84)")
    parser.add_argument("input", help="Input FIRMS CSV (e.g., data/firms/processed/firms_clean.csv)")
    parser.add_argument("output", help="Output filtered CSV (e.g., data/firms/processed/firms_india.csv)")
    parser.add_argument("--boundary", default="data/geospatial/boundaries/india.geojson", help="India boundary GeoJSON")
    parser.add_argument("--report", default=None, help="Optional JSON report path")
    args = parser.parse_args(argv)
    report = filter_csv(args.input, args.output, boundary_path=args.boundary, report_path=args.report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
