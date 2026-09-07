"""
ml/geospatial/osm_enrichment.py — OSM facility enrichment with counts & per-category distances.

- Converts Overpass JSON → normalized facility list (handles nodes/ways/relations)
- Deduplicates by osm_id, handles missing names, invalid geometries
- Computes for each FIRMS point:
    nearest_facility_distance_m, nearest_facility_type/id/name
    facility_count_500m/1km
    industrial/power/oil_gas counts
    nearest per-category distances (power, refinery, oil_gas, steel, cement)

Reuses facility_enrichment.normalize_facility_type and geo_utils.haversine_m
No live Overpass calls in tests — mocked.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

from .geo_utils import haversine_m, distance_to_geometry_m
from .facility_enrichment import normalize_facility_type, CANONICAL_FACILITY_TYPES

# For OSM
OSM_CACHE_GEOJSON = Path("data/geospatial/cache/osm_india.geojson")

# Category definitions for counts
INDUSTRIAL_TYPES = {"refinery", "factory", "industrial_area", "chemical", "steel", "cement", "oil_gas"}
POWER_TYPES = {"power_plant"}
OIL_GAS_TYPES = {"oil_gas", "refinery"}  # oil_gas includes refinery per mapping

# For per-category nearest
CATEGORY_QUERIES = {
    "power": {"power_plant"},
    "refinery": {"refinery"},
    "oil_gas": {"oil_gas", "refinery"},
    "steel": {"steel"},
    "cement": {"cement"},
}


def overpass_to_geojson(overpass_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert Overpass JSON (elements with type node/way, tags, lat/lon or center) to GeoJSON FeatureCollection.
    Handles nodes (lat/lon) and ways (center lat/lon). Relations skipped for prototype.
    Deduplicates by osm_id, skips invalid geometries.
    Returns GeoJSON dict with Point features.
    """
    elements = overpass_data.get("elements", [])
    features: List[Dict[str, Any]] = []
    seen = set()
    for el in elements:
        typ = el.get("type")
        osm_id = el.get("id")
        key = f"{typ}/{osm_id}"
        if key in seen:
            continue
        seen.add(key)
        tags = el.get("tags", {}) or {}
        # Determine lat/lon
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            center = el.get("center")
            if center:
                lat = center.get("lat")
                lon = center.get("lon")
        if lat is None or lon is None:
            continue
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
                continue
        except Exception:
            continue
        # Build properties with raw tags
        props: Dict[str, Any] = {"osm_id": key, "osm_type": typ}
        # Preserve name
        if "name" in tags:
            props["name"] = tags["name"]
        # Copy relevant tags for normalization
        for k in ("industrial", "landuse", "man_made", "power", "building", "amenity", "shop", "name"):
            if k in tags:
                props[k] = tags[k]
        # Also preserve raw_tags
        props["raw_tags"] = tags
        # Normalize type
        canon, orig = normalize_facility_type(props)
        props["facility_type"] = canon
        props["original_type"] = orig

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon_f, lat_f]},
                "properties": props,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def load_osm_facilities(
    cache_geojson: Path = OSM_CACHE_GEOJSON,
    overpass_json: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Load normalized OSM facilities from cached GeoJSON (or Overpass JSON).
    Returns list of {osm_id, latitude, longitude, name, facility_type, raw_tags, geometry_type}
    Handles Point, Polygon, MultiPolygon (polygon centroid used for distance).
    """
    # Prefer GeoJSON cache
    if cache_geojson and Path(cache_geojson).exists():
        data = json.loads(Path(cache_geojson).read_text(encoding="utf-8"))
        features = data.get("features", []) if isinstance(data, dict) else []
        facilities: List[Dict[str, Any]] = []
        seen_ids = set()
        for feat in features:
            props = feat.get("properties", {}) or {}
            geom = feat.get("geometry", {})
            gtype = geom.get("type")
            if gtype not in ("Point", "Polygon", "MultiPolygon"):
                continue
            # Extract lat/lon: for Point use coordinates, for Polygon use centroid (average)
            try:
                if gtype == "Point":
                    lon, lat = geom["coordinates"][0], geom["coordinates"][1]
                elif gtype == "Polygon":
                    # Use centroid of exterior ring
                    ring = geom["coordinates"][0]
                    lons = [c[0] for c in ring]
                    lats = [c[1] for c in ring]
                    lon = sum(lons) / len(lons)
                    lat = sum(lats) / len(lats)
                else:  # MultiPolygon
                    # Use first polygon centroid
                    ring = geom["coordinates"][0][0]
                    lons = [c[0] for c in ring]
                    lats = [c[1] for c in ring]
                    lon = sum(lons) / len(lons)
                    lat = sum(lats) / len(lats)
                # Normalize facility_type if missing or other but tags suggest
                fac_type = props.get("facility_type")
                if not fac_type or fac_type == "other":
                    # Try to normalize from tags
                    canon, _ = normalize_facility_type(props)
                    fac_type = canon
                # Also try raw_tags if present
                if fac_type == "other" and props.get("raw_tags"):
                    canon2, _ = normalize_facility_type(props.get("raw_tags", {}))
                    if canon2 != "other":
                        fac_type = canon2
            except Exception:
                continue
            osm_id = props.get("osm_id") or f"OSM_{len(facilities)}"
            if osm_id in seen_ids:
                continue
            seen_ids.add(osm_id)
            try:
                lat_f = float(lat)
                lon_f = float(lon)
                if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
                    continue
            except Exception:
                continue
            facilities.append(
                {
                    "osm_id": osm_id,
                    "latitude": lat_f,
                    "longitude": lon_f,
                    "name": props.get("name"),
                    "facility_type": fac_type or "other",
                    "raw_tags": props.get("raw_tags", props),
                    "geometry_type": gtype,
                    "properties": props,
                    "geometry": geom,
                }
            )
        return facilities

    # Fallback to Overpass JSON
    if overpass_json and Path(overpass_json).exists():
        data = json.loads(Path(overpass_json).read_text(encoding="utf-8"))
        gj = overpass_to_geojson(data)
        # Recursively call with temp GeoJSON
        tmp_path = Path(overpass_json).with_suffix(".geojson")
        tmp_path.write_text(json.dumps(gj), encoding="utf-8")
        return load_osm_facilities(cache_geojson=tmp_path)

    return []


class OSMEnricher:
    """
    Enriches FIRMS points with OSM facility context.
    Uses haversine for all distances (meters), grid-hashed for counts.
    """

    def __init__(self, facilities: Optional[List[Dict[str, Any]]] = None):
        self.facilities: List[Dict[str, Any]] = facilities or []
        # Precompute for speed
        self.lats = [f["latitude"] for f in self.facilities]
        self.lons = [f["longitude"] for f in self.facilities]
        self.types = [f["facility_type"] for f in self.facilities]

    @classmethod
    def from_cache(cls, cache_geojson: Path = OSM_CACHE_GEOJSON) -> "OSMEnricher":
        facs = load_osm_facilities(cache_geojson=cache_geojson)
        return cls(facs)

    @classmethod
    def from_geojson(cls, path: Path | Dict[str, Any]) -> "OSMEnricher":
        # Load via FacilityEnricher path but convert to OSM format
        if isinstance(path, dict):
            data = path
            tmp = Path("/tmp/osm_temp.geojson")
            tmp.write_text(json.dumps(data))
            facs = load_osm_facilities(cache_geojson=tmp)
            tmp.unlink(missing_ok=True)
            return cls(facs)
        return cls.from_cache(cache_geojson=Path(path))

    def enrich(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Returns dict with OSM features for point (lat,lon).
        All distances meters; counts ints; None if no facilities.
        """
        if not self.facilities:
            return {
                "nearest_facility_distance_m": None,
                "nearest_facility_type": None,
                "nearest_facility_osm_id": None,
                "nearest_facility_name": None,
                "facility_count_500m": 0,
                "facility_count_1km": 0,
                "industrial_facility_count_500m": 0,
                "industrial_facility_count_1km": 0,
                "power_facility_count_1km": 0,
                "oil_gas_facility_count_1km": 0,
                "nearest_powerplant_distance_m": None,
                "nearest_refinery_distance_m": None,
                "nearest_oil_gas_distance_m": None,
                "nearest_steel_facility_distance_m": None,
                "nearest_cement_facility_distance_m": None,
            }

        # Compute all distances
        dists: List[Tuple[float, int]] = []
        for idx, (flat, flon) in enumerate(zip(self.lats, self.lons)):
            d = haversine_m(lat, lon, flat, flon)
            dists.append((d, idx))

        # Nearest
        dists_sorted = sorted(dists, key=lambda x: x[0])
        nearest_d, nearest_idx = dists_sorted[0]
        nearest_fac = self.facilities[nearest_idx]

        # Counts
        fac_500 = sum(1 for d, _ in dists if d <= 500)
        fac_1000 = sum(1 for d, _ in dists if d <= 1000)

        # Category counts
        industrial_500 = sum(1 for d, idx in dists if d <= 500 and self.types[idx] in INDUSTRIAL_TYPES)
        industrial_1000 = sum(1 for d, idx in dists if d <= 1000 and self.types[idx] in INDUSTRIAL_TYPES)
        power_1000 = sum(1 for d, idx in dists if d <= 1000 and self.types[idx] in POWER_TYPES)
        oil_gas_1000 = sum(1 for d, idx in dists if d <= 1000 and self.types[idx] in OIL_GAS_TYPES)

        # Per-category nearest
        def nearest_for(cat: set) -> Optional[float]:
            best = None
            for d, idx in dists:
                if self.types[idx] in cat:
                    if best is None or d < best:
                        best = d
            return best

        return {
            "nearest_facility_distance_m": float(nearest_d),
            "nearest_facility_type": nearest_fac["facility_type"],
            "nearest_facility_osm_id": nearest_fac["osm_id"],
            "nearest_facility_name": nearest_fac["name"],
            "facility_count_500m": int(fac_500),
            "facility_count_1km": int(fac_1000),
            "industrial_facility_count_500m": int(industrial_500),
            "industrial_facility_count_1km": int(industrial_1000),
            "power_facility_count_1km": int(power_1000),
            "oil_gas_facility_count_1km": int(oil_gas_1000),
            "nearest_powerplant_distance_m": float(nearest_for(POWER_TYPES)) if nearest_for(POWER_TYPES) is not None else None,
            "nearest_refinery_distance_m": float(nearest_for({"refinery"})) if nearest_for({"refinery"}) is not None else None,
            "nearest_oil_gas_distance_m": float(nearest_for(OIL_GAS_TYPES)) if nearest_for(OIL_GAS_TYPES) is not None else None,
            "nearest_steel_facility_distance_m": float(nearest_for({"steel"})) if nearest_for({"steel"}) is not None else None,
            "nearest_cement_facility_distance_m": float(nearest_for({"cement"})) if nearest_for({"cement"}) is not None else None,
        }

    def is_loaded(self) -> bool:
        return len(self.facilities) > 0

    def stats(self) -> Dict[str, Any]:
        if not self.facilities:
            return {"facility_count": 0, "unique_osm_ids": 0, "by_category": {}, "by_type": {}}
        by_type = Counter(self.types)
        # Map to broader categories
        by_cat = {
            "industrial": sum(v for k, v in by_type.items() if k in INDUSTRIAL_TYPES),
            "power": by_type.get("power_plant", 0),
            "oil_gas": sum(v for k, v in by_type.items() if k in OIL_GAS_TYPES),
            "other": by_type.get("other", 0),
        }
        return {
            "facility_count": len(self.facilities),
            "unique_osm_ids": len(set(f["osm_id"] for f in self.facilities)),
            "by_category": by_cat,
            "by_type": dict(by_type),
        }
