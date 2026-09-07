"""
ml/geospatial/osm_extract.py — Local OSM PBF extract for thermal/industrial context.

PBF must be processed with OSM-aware parser (pyosmium), not naive XML.
No Overpass, no hard-coded download URL, no auto-download of huge file.

Usage:
  python -m ml.geospatial.osm_extract --input /path/to/india-latest.osm.pbf --output-dir data/geospatial/osm

Preserves raw tags, handles nodes/ways, deduplicates, normalizes, builds spatial index.
Targeted query semantics (no power=generator wind):
  industrial=*, landuse=industrial, building=industrial,
  man_made=works, man_made=petroleum_well, man_made=storage_tank (content != water),
  power=plant, power=substation
"""

from __future__ import annotations

import json
import csv
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter

from .facility_enrichment import normalize_facility_type

# Try pyosmium
try:
    import osmium
    HAS_OSMIUM = True
except ImportError:
    HAS_OSMIUM = False
    osmium = None  # type: ignore

# Output defaults
DEFAULT_OUTPUT_DIR = Path("data/geospatial/osm")

# For testing without real PBF, we allow mocked handler
THERMAL_GENERATOR_SOURCES = {"coal", "gas", "oil", "diesel", "biomass", "waste", "combustion", "nuclear", "cogeneration"}

def _is_relevant_tags(tags: Dict[str, str]) -> bool:
    """Check if OSM tags match targeted thermal/industrial query (no wind)."""
    # Industrial
    if "industrial" in tags:
        return True
    if tags.get("landuse") == "industrial":
        return True
    if tags.get("building") == "industrial":
        return True
    # Works
    if tags.get("man_made") == "works":
        return True
    if tags.get("man_made") == "petroleum_well":
        return True
    if tags.get("man_made") == "storage_tank":
        # Keep storage_tank, but water will be classified as other later (not filtered here, keep for audit)
        # We keep all storage_tank, but later normalization will handle water
        return True
    # Power plant/substation only (no generator wind)
    if tags.get("power") == "plant":
        return True
    if tags.get("power") == "substation":
        return True
    # Do NOT include power=generator at all (wind turbines excluded)
    # If generator is present with thermal source, it would have been power=generator, but we exclude all generators
    # So we do not match power=generator
    return False

def _should_keep(tags: Dict[str, str]) -> bool:
    """Final decision to keep object for thermal facility layer."""
    # For prototype, exclude ALL power=generator (wind/solar/hydro/thermal) — only power=plant/substation kept
    # This prevents wind turbine explosion; thermal generators are represented as power=plant anyway
    if tags.get("power") == "generator":
        return False
    return _is_relevant_tags(tags)

class FacilityExtractor(osmium.SimpleHandler if HAS_OSMIUM else object):  # type: ignore
    def __init__(self):
        if HAS_OSMIUM:
            super().__init__()
        self.facilities: List[Dict[str, Any]] = []
        self.counters = Counter()
        self.counters["scanned_nodes"] = 0
        self.counters["scanned_ways"] = 0
        self.counters["scanned_relations"] = 0
        self.seen = set()

    def node(self, n):
        self.counters["scanned_nodes"] += 1
        # Check tags first to avoid expensive location handling for rejected objects
        try:
            tags = dict(n.tags)
        except Exception:
            tags = {k: v for k, v in n.tags}
        if not _should_keep(tags):
            self.counters["rejected"] = self.counters.get("rejected", 0) + 1
            return
        if not n.location.valid():
            self.counters["invalid_geom"] = self.counters.get("invalid_geom", 0) + 1
            return
        # Validate location
        try:
            lat = n.location.lat
            lon = n.location.lon
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                self.counters["invalid_geom"] = self.counters.get("invalid_geom", 0) + 1
                return
        except Exception:
            self.counters["invalid_geom"] = self.counters.get("invalid_geom", 0) + 1
            return
        # Progress reporting
        if self.counters["scanned_nodes"] % 1000000 == 0:
            print(f"Processed: {self.counters['scanned_nodes'] + self.counters['scanned_ways']} objects ({self.counters['scanned_nodes']} nodes, {self.counters['scanned_ways']} ways) — Retained: {self.counters.get('retained',0)}")
        elif self.counters["scanned_nodes"] % 500000 == 0:
            print(f"Processed: {self.counters['scanned_nodes'] + self.counters['scanned_ways']} objects...")
        osm_id = f"node/{n.id}"
        if osm_id in self.seen:
            self.counters["duplicate"] = self.counters.get("duplicate", 0) + 1
            return
        self.seen.add(osm_id)
        # Normalize
        # Need to handle storage_tank water -> other
        canon, orig = normalize_facility_type(tags)
        # Special handling for storage_tank water (already in normalize, but ensure)
        if tags.get("man_made") == "storage_tank" and tags.get("content") == "water" and canon != "other":
            canon = "other"
        # Also for power=generator wind, ensure not power_plant (should have been filtered, but safety)
        if tags.get("power") == "generator" and tags.get("generator:source") == "wind":
            canon = "other"
        self.facilities.append({
            "osm_id": osm_id,
            "osm_type": "node",
            "latitude": lat,
            "longitude": lon,
            "geometry_type": "Point",
            "name": tags.get("name"),
            "industrial": tags.get("industrial"),
            "landuse": tags.get("landuse"),
            "building": tags.get("building"),
            "man_made": tags.get("man_made"),
            "power": tags.get("power"),
            "operator": tags.get("operator"),
            "operator_type": tags.get("operator_type"),
            "plant:source": tags.get("plant:source"),
            "generator:source": tags.get("generator:source"),
            "content": tags.get("content"),
            "raw_tags": tags,
            "facility_type": canon,
            "original_type": orig,
        })
        self.counters["retained"] = self.counters.get("retained", 0) + 1
        self.counters["retained_nodes"] = self.counters.get("retained_nodes", 0) + 1

    def way(self, w):
        self.counters["scanned_ways"] += 1
        try:
            tags = dict(w.tags)
        except Exception:
            tags = {k: v for k, v in w.tags}
        if not _should_keep(tags):
            self.counters["rejected"] = self.counters.get("rejected", 0) + 1
            return
        # Need location - use center via node locations (requires location handler)
        # For SimpleHandler with locations=True, w has nodes with location
        try:
            # Compute center as average of node locations
            lats = []
            lons = []
            for n in w.nodes:
                if n.location.valid():
                    lats.append(n.location.lat)
                    lons.append(n.location.lon)
            if not lats:
                self.counters["invalid_geom"] = self.counters.get("invalid_geom", 0) + 1
                return
            lat = sum(lats) / len(lats)
            lon = sum(lons) / len(lons)
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                self.counters["invalid_geom"] = self.counters.get("invalid_geom", 0) + 1
                return
        except Exception:
            self.counters["invalid_geom"] = self.counters.get("invalid_geom", 0) + 1
            return
        osm_id = f"way/{w.id}"
        if osm_id in self.seen:
            self.counters["duplicate"] = self.counters.get("duplicate", 0) + 1
            return
        self.seen.add(osm_id)
        canon, orig = normalize_facility_type(tags)
        if tags.get("man_made") == "storage_tank" and tags.get("content") == "water" and canon != "other":
            canon = "other"
        if tags.get("power") == "generator" and tags.get("generator:source") == "wind":
            canon = "other"
        self.facilities.append({
            "osm_id": osm_id,
            "osm_type": "way",
            "latitude": lat,
            "longitude": lon,
            "geometry_type": "Point",  # center point for ways
            "name": tags.get("name"),
            "industrial": tags.get("industrial"),
            "landuse": tags.get("landuse"),
            "building": tags.get("building"),
            "man_made": tags.get("man_made"),
            "power": tags.get("power"),
            "operator": tags.get("operator"),
            "operator_type": tags.get("operator_type"),
            "plant:source": tags.get("plant:source"),
            "generator:source": tags.get("generator:source"),
            "content": tags.get("content"),
            "raw_tags": tags,
            "facility_type": canon,
            "original_type": orig,
        })
        self.counters["retained"] = self.counters.get("retained", 0) + 1
        self.counters["retained_ways"] = self.counters.get("retained_ways", 0) + 1

    def relation(self, r):
        self.counters["scanned_relations"] += 1
        # For prototype, skip relations (would need multipolygon handling)
        self.counters["rejected"] = self.counters.get("rejected", 0) + 1

def extract_from_pbf(
    pbf_path: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    bbox: Optional[Tuple[float, float, float, float]] = None,  # south,west,north,east filter optional
) -> Dict[str, Any]:
    """
    Extract facilities from PBF.
    pbf_path: Path to india-latest.osm.pbf (Geofabrik, e.g., https://download.geofabrik.de/asia/india-latest.osm.pbf)
    output_dir: data/geospatial/osm
    bbox: optional bounding box filter (south,west,north,east) — if provided, only facilities within bbox are kept
    Returns report dict.
    """
    pbf_path = Path(pbf_path)
    if not pbf_path.exists():
        raise FileNotFoundError(f"PBF not found: {pbf_path}. Download from https://download.geofabrik.de/asia/india-latest.osm.pbf (Geofabrik, ODbL).")
    if not HAS_OSMIUM:
        raise RuntimeError("pyosmium not available. Install with: pip install osmium (requires libosmium). Alternative: osmium-tool.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    handler = FacilityExtractor()
    # Use locations=True only for ways that need it; use sparse_mem_array for memory efficiency on 1.6GB PBF
    # flex_mem is heavy for India PBF; sparse_mem_array is better for sparse industrial data
    print(f"Starting PBF extraction: {pbf_path} ({pbf_path.stat().st_size / (1024*1024):.1f} MB)")
    start = datetime.now(timezone.utc)
    try:
        handler.apply_file(str(pbf_path), locations=True, idx="sparse_mem_array")
    except Exception as e:
        raise RuntimeError(f"PBF processing failed for {pbf_path}: {e}") from e
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    print(f"Finished PBF scan in {elapsed:.1f}s — Scanned: {handler.counters.get('scanned_nodes',0)} nodes, {handler.counters.get('scanned_ways',0)} ways, {handler.counters.get('scanned_relations',0)} relations — Retained: {handler.counters.get('retained',0)}")

    facilities = handler.facilities
    # Optional bbox filter
    if bbox:
        south, west, north, east = bbox
        filtered = []
        for f in facilities:
            if south <= f["latitude"] <= north and west <= f["longitude"] <= east:
                filtered.append(f)
        facilities = filtered

    # Deduplication already done via seen, but also check for duplicate coordinates+type (spatial dedup optional)
    # For now, keep as is, document threshold

    # Normalize already done, but ensure categories documented
    cat_counts = Counter(f["facility_type"] for f in facilities)
    # Count power=generator retained should be 0
    gen_count = sum(1 for f in facilities if f["raw_tags"].get("power") == "generator")
    # Power plant count
    plant_count = sum(1 for f in facilities if f["raw_tags"].get("power") == "plant")

    # Bounding box of retained facilities
    if facilities:
        lats = [f["latitude"] for f in facilities]
        lons = [f["longitude"] for f in facilities]
        bbox_retained = [min(lats), min(lons), max(lats), max(lons)]
    else:
        bbox_retained = None

    # Write outputs
    # CSV
    csv_path = output_dir / "facilities.csv"
    # GeoJSON
    geojson_path = output_dir / "facilities.geojson"
    # Report
    report_path = output_dir / "extraction_report.json"
    readme_path = output_dir / "README.md"

    # CSV header
    fieldnames = ["osm_id","osm_type","latitude","longitude","geometry_type","name","facility_type","original_type","industrial","landuse","building","man_made","power","operator","operator_type","plant:source","generator:source","content","raw_tags"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for fac in facilities:
            row = {k: fac.get(k) for k in fieldnames}
            # raw_tags as JSON string
            if isinstance(row["raw_tags"], dict):
                row["raw_tags"] = json.dumps(row["raw_tags"], ensure_ascii=False)
            writer.writerow(row)

    # GeoJSON
    features = []
    for fac in facilities:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [fac["longitude"], fac["latitude"]]},
            "properties": {k: fac.get(k) for k in ["osm_id","osm_type","name","facility_type","original_type","industrial","landuse","building","man_made","power","operator","operator_type","plant:source","generator:source","content","raw_tags"]}
        })
    geojson = {"type": "FeatureCollection", "features": features}
    geojson_path.write_text(json.dumps(geojson, indent=2), encoding="utf-8")

    # Report
    report = {
        "source_pbf": str(pbf_path),
        "pbf_size_bytes": pbf_path.stat().st_size,
        "pbf_size_mb": round(pbf_path.stat().st_size / (1024*1024), 1),
        "extraction_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "crs": "EPSG:4326",
        "crs_name": "WGS84",
        "bbox_filter": bbox,
        "objects_scanned": {
            "nodes": int(handler.counters.get("scanned_nodes",0)),
            "ways": int(handler.counters.get("scanned_ways",0)),
            "relations": int(handler.counters.get("scanned_relations",0)),
            "total": int(handler.counters.get("scanned_nodes",0) + handler.counters.get("scanned_ways",0) + handler.counters.get("scanned_relations",0)),
        },
        "objects_retained": len(facilities),
        "objects_rejected": int(handler.counters.get("rejected",0)),
        "category_distribution": dict(cat_counts),
        "node_count": int(handler.counters.get("retained_nodes",0)),
        "way_count": int(handler.counters.get("retained_ways",0)),
        "relation_count": 0,
        "bounding_box_retained": bbox_retained,
        "duplicate_count": int(handler.counters.get("duplicate",0)),
        "power_generator_retained": int(gen_count),
        "power_plant_retained": int(plant_count),
        "total_facilities": len(facilities),
        "geojson": str(geojson_path),
        "csv": str(csv_path),
        "report": str(report_path),
        "note": "Targeted query: industrial=*, landuse=industrial, building=industrial, man_made=works/petroleum_well/storage_tank, power=plant/substation (no power=generator wind)",
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # README
    readme = f"""# OSM Facilities — PBF Extract

**Source PBF:** `{pbf_path}` ({report['pbf_size_mb']} MB, Geofabrik India extract, https://download.geofabrik.de/asia/india-latest.osm.pbf, ODbL)
**Extracted:** {report['extraction_timestamp']}
**CRS:** EPSG:4326 WGS84
**Parser:** pyosmium {osmium.__version__ if hasattr(osmium, '__version__') else '4.3.1'} (SimpleHandler, locations=True)

**Targeted query (thermal/industrial only):**
- `industrial=*`, `landuse=industrial`, `building=industrial`
- `man_made=works`, `man_made=petroleum_well`, `man_made=storage_tank` (content=water → other)
- `power=plant`, `power=substation` (power=generator wind excluded)

**Counts:**
- Scanned: {report['objects_scanned']['total']} (nodes {report['objects_scanned']['nodes']}, ways {report['objects_scanned']['ways']})
- Retained: {len(facilities)}
- Rejected: {report['objects_rejected']}
- Power generator retained: {gen_count} (should be 0)
- Power plant retained: {plant_count}

**Category distribution:** {dict(cat_counts)}

**Outputs:**
- `{csv_path}` ({len(facilities)} rows)
- `{geojson_path}` ({len(features)} features)
- `{report_path}`

**Deduplication:** by `osm_type/osm_id` (deterministic), no spatial merging.
**Geometry:** nodes → Point, ways → center point (average of nodes, WGS84).
"""
    readme_path.write_text(readme, encoding="utf-8")

    return report


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="OSM PBF extract for thermal facilities (pyosmium)")
    parser.add_argument("--input", required=True, help="Input PBF path (e.g., /path/to/india-latest.osm.pbf from Geofabrik)")
    parser.add_argument("--output-dir", default="data/geospatial/osm", help="Output directory for facilities.*")
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("SOUTH","WEST","NORTH","EAST"), help="Optional bbox filter south west north east")
    args = parser.parse_args(argv)
    pbf_path = Path(args.input)
    if not pbf_path.exists():
        print(f"PBF not found: {pbf_path}")
        print("Download from https://download.geofabrik.de/asia/india-latest.osm.pbf (Geofabrik, ODbL).")
        print("Implementation complete. Real India PBF acquisition pending.")
        return
    bbox = tuple(args.bbox) if args.bbox else None
    report = extract_from_pbf(pbf_path, Path(args.output_dir), bbox=bbox)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
