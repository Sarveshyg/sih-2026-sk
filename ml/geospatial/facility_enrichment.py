"""
ml/geospatial/facility_enrichment.py — Industrial facility enrichment.

- Loads local GeoJSON (Point/Polygon) facility datasets (no Overpass live calls)
- Normalizes facility types into controlled vocabulary (preserving original)
- Nearest facility via geodesic haversine (not Cartesian), with polygon edge handling
- Returns meters; None if no dataset supplied (no fabrication)

Discovery note: this module is intentionally file-based so Yash can swap
industrial_facilities.geojson without touching AI code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

from .geo_utils import haversine_m, distance_to_geometry_m, point_in_polygon, point_in_multipolygon, HAS_SHAPELY

# Controlled vocabulary — canonical facility types
CANONICAL_FACILITY_TYPES = {
    "refinery",
    "power_plant",
    "factory",
    "industrial_area",
    "oil_gas",
    "chemical",
    "steel",
    "cement",
    "warehouse",
    "other",
}

# OSM tag → canonical mapping (documented, not assumed universal)
# Precedence: explicit industrial value > building/landuse/power/man_made heuristics
_OSM_INDUSTRIAL_MAP = {
    # industrial=*
    "refinery": "refinery",
    "oil": "oil_gas",
    "gas": "oil_gas",
    "petroleum": "oil_gas",
    "chemical": "chemical",
    "steel": "steel",
    "cement": "cement",
    "factory": "factory",
    "warehouse": "warehouse",
    "industrial": "industrial_area",
    # landuse/industrial area
    "industrial_area": "industrial_area",
    # power
    "plant": "power_plant",
    "power_plant": "power_plant",
    # generic
    "works": "factory",
    "manufacturing": "factory",
}

_POWER_MAP = {
    "plant": "power_plant",
    # generator is handled specially below (wind → other, thermal → power_plant)
    "power_plant": "power_plant",
}

# Thermally relevant generator sources — only these should be power_plant
_THERMAL_GENERATOR_SOURCES = {
    "coal", "gas", "oil", "diesel", "biomass", "waste", "combustion",
    "nuclear", "cogeneration",
}

_LANDUSE_MAP = {
    "industrial": "industrial_area",
}

_MAN_MADE_MAP = {
    "works": "factory",
    "factory": "factory",
    "industrial": "industrial_area",
}


def normalize_facility_type(properties: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """
    Map OSM-like properties to canonical facility type.

    Returns (canonical_type, original_type) where original is preserved for audit.

    Priority:
      1. industrial tag
      2. power tag
      3. landuse tag
      4. man_made tag
      5. building/amenity fallback → other
      6. explicit 'facility_type' or 'type' field already provided
    """
    # Direct canonical field already supplied (e.g., Yash's pre-normalized GeoJSON)
    for key in ("facility_type", "type", "canonical_type"):
        if properties.get(key) and str(properties[key]).lower() in CANONICAL_FACILITY_TYPES:
            return str(properties[key]).lower(), str(properties[key])

    # Check industrial
    industrial = properties.get("industrial")
    if industrial:
        v = str(industrial).strip().lower()
        if v in _OSM_INDUSTRIAL_MAP:
            return _OSM_INDUSTRIAL_MAP[v], v
        # fuzzy: contains keyword
        for k, canon in _OSM_INDUSTRIAL_MAP.items():
            if k in v:
                return canon, v

    # power tag — handle generator specially to avoid wind turbines
    power = properties.get("power")
    if power:
        v = str(power).strip().lower()
        if v == "generator":
            # Check generator:source — only thermal sources are power_plant
            source = str(properties.get("generator:source", "")).strip().lower()
            # Also check raw_tags if present
            if not source and isinstance(properties.get("raw_tags"), dict):
                source = str(properties["raw_tags"].get("generator:source", "")).strip().lower()
            if source in _THERMAL_GENERATOR_SOURCES:
                return "power_plant", v
            # Wind/solar/hydro or unknown → not thermal
            if source in ("wind", "solar", "hydro", "photovoltaic", "tidal"):
                return "other", v
            # Unknown source → treat as other to avoid polluting thermal layer
            return "other", v
        if v in _POWER_MAP:
            return _POWER_MAP[v], v

    # landuse
    landuse = properties.get("landuse")
    if landuse:
        v = str(landuse).strip().lower()
        if v in _LANDUSE_MAP:
            return _LANDUSE_MAP[v], v

    # man_made — handle storage_tank with content check
    man_made = properties.get("man_made")
    if man_made:
        v = str(man_made).strip().lower()
        if v == "storage_tank":
            content = str(properties.get("content", "")).strip().lower()
            if not content and isinstance(properties.get("raw_tags"), dict):
                content = str(properties["raw_tags"].get("content", "")).strip().lower()
            if content == "water":
                return "other", v
            if content in ("oil", "gas", "chemical", "petroleum", "fuel"):
                return "oil_gas", v
            # Unknown content → keep as other (not industrial thermal)
            return "other", v
        if v in _MAN_MADE_MAP:
            return _MAN_MADE_MAP[v], v
        if "works" in v:
            return "factory", v

    # Explicit OSM tags like building=industrial, amenity etc → fallback heuristic
    building = properties.get("building")
    if building and str(building).lower() in ("industrial", "warehouse"):
        return ("warehouse" if "warehouse" in str(building).lower() else "factory"), str(building)

    # If any industrial-ish string present, classify as industrial_area
    for k in ("industrial", "landuse", "man_made", "building"):
        if properties.get(k):
            v = str(properties[k]).lower()
            if "industrial" in v:
                return "industrial_area", v

    return "other", properties.get("industrial") or properties.get("landuse") or properties.get("man_made") or None


def _extract_facility_id(feature: Dict[str, Any], idx: int) -> str:
    props = feature.get("properties") or {}
    for key in ("id", "facility_id", "fid", "osm_id"):
        if props.get(key) not in (None, ""):
            return str(props[key])
    # fallback deterministic: OSM_<hash or idx>
    return f"OSM_{idx}"


def _extract_facility_name(feature: Dict[str, Any]) -> Optional[str]:
    props = feature.get("properties") or {}
    for key in ("name", "facility_name", "plant_name", "title"):
        if props.get(key) not in (None, ""):
            return str(props[key])
    return None


class FacilityEnricher:
    """
    Loads facility GeoJSON and answers nearest-facility queries.

    Supports Point, Polygon, MultiPolygon facilities.
    Distance semantics (meters, geodesic):
      Point       → point-to-point haversine
      Polygon     → minimum distance to polygon boundary; 0 if inside
      MultiPolygon→ minimum across polygons; 0 if inside any

    Performance: O(N) per query in pure Python; acceptable for thousands.
    When Shapely is available, validation and optional STRtree indexing are
    used, but meter outputs remain haversine-based (no Cartesian deg math).
    Invalid geometries are skipped safely (no crash).
    """

    def __init__(self, facilities: Optional[List[Dict[str, Any]]] = None):
        # Each entry: {id, name, geometry, canonical_type, original_type, properties}
        self.facilities: List[Dict[str, Any]] = facilities or []
        # Optional Shapely validation/indexing (never required)
        self._shapely_index = None
        if HAS_SHAPELY and self.facilities:
            try:
                import shapely.geometry as sgeom  # type: ignore
                from shapely.strtree import STRtree  # type: ignore

                # Build validated shapely geoms for indexing; invalid skipped
                shapely_geoms = []
                for fac in self.facilities:
                    try:
                        g = fac["geometry"]
                        if g["type"] == "Point":
                            geom = sgeom.Point(g["coordinates"])
                        elif g["type"] == "Polygon":
                            geom = sgeom.Polygon(g["coordinates"][0], g["coordinates"][1:] or None)
                        elif g["type"] == "MultiPolygon":
                            geom = sgeom.MultiPolygon(
                                [(poly[0], poly[1:] or None) for poly in g["coordinates"]]
                            )
                        else:
                            continue
                        if not geom.is_valid:
                            geom = geom.buffer(0)
                            if not geom.is_valid:
                                continue
                        fac["_shapely_geom"] = geom
                        shapely_geoms.append(geom)
                    except Exception:
                        continue
                if shapely_geoms:
                    self._shapely_index = STRtree(shapely_geoms)
            except Exception:
                self._shapely_index = None

    @classmethod
    def from_geojson(cls, path: str | Path | Dict[str, Any] | List[Dict[str, Any]]) -> "FacilityEnricher":
        if path is None:
            return cls([])
        # Accept already-loaded dict/list or file path
        if isinstance(path, dict):
            data = path
        elif isinstance(path, list):
            # list of features
            data = {"type": "FeatureCollection", "features": path}
        elif isinstance(path, (str, Path)) and Path(path).exists():
            p = Path(path)
            # Try GeoJSON; fallback to try reading as JSON
            text = p.read_text(encoding="utf-8")
            data = json.loads(text)
        else:
            # If path string looks like JSON inline
            if isinstance(path, (str, Path)) and str(path).strip().startswith("{"):
                data = json.loads(str(path))
            else:
                raise FileNotFoundError(f"Facility GeoJSON not found: {path}")

        # Handle FeatureCollection, single Feature, or raw list under data
        features: List[Dict[str, Any]] = []
        if data.get("type") == "FeatureCollection":
            features = data.get("features", [])
        elif data.get("type") == "Feature":
            features = [data]
        elif isinstance(data, list):
            features = data
        else:
            # Might be dict with facilities key
            features = data.get("features") or data.get("facilities") or []

        parsed: List[Dict[str, Any]] = []
        for idx, feat in enumerate(features):
            geom = feat.get("geometry")
            if not geom or geom.get("type") not in ("Point", "Polygon", "MultiPolygon"):
                continue
            props = feat.get("properties") or {}
            fid = _extract_facility_id(feat, idx)
            name = _extract_facility_name(feat)
            canon, orig = normalize_facility_type(props)
            parsed.append(
                {
                    "id": fid,
                    "name": name,
                    "geometry": geom,
                    "canonical_type": canon,
                    "original_type": orig,
                    "properties": props,
                }
            )
        return cls(parsed)

    @classmethod
    def from_file(
        cls,
        path: str | Path | None,
        *,
        encoding: str = "utf-8",
    ) -> "FacilityEnricher":
        if path is None:
            return cls([])
        return cls.from_geojson(path)

    def enrich(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Returns dict with:
          nearest_facility_id, nearest_facility_name, facility_type (canonical),
          original_facility_type, distance_to_industry (m), inside_industrial_area (bool or None)
        All None if no facilities loaded.
        """
        if not self.facilities:
            return {
                "nearest_facility_id": None,
                "nearest_facility_name": None,
                "facility_type": None,
                "original_facility_type": None,
                "distance_to_industry": None,
                "distance_to_facility_m": None,
                "inside_industrial_area": None,
            }

        best = None
        best_dist = float("inf")
        best_fac = None

        for fac in self.facilities:
            d = distance_to_geometry_m(lat, lon, fac["geometry"])
            if d < best_dist:
                best_dist = d
                best_fac = fac

        if best_fac is None:
            return {
                "nearest_facility_id": None,
                "nearest_facility_name": None,
                "facility_type": None,
                "original_facility_type": None,
                "distance_to_industry": None,
                "distance_to_facility_m": None,
                "inside_industrial_area": None,
            }

        # inside check: distance 0 means inside polygon (for polygon facilities)
        is_inside = None
        gtype = best_fac["geometry"]["type"]
        if gtype in ("Polygon", "MultiPolygon"):
            is_inside = best_dist == 0.0
        else:
            is_inside = False

        return {
            "nearest_facility_id": best_fac["id"],
            "nearest_facility_name": best_fac["name"],
            "facility_type": best_fac["canonical_type"],
            "original_facility_type": best_fac["original_type"],
            "distance_to_industry": float(best_dist),
            "distance_to_facility_m": float(best_dist),
            "inside_industrial_area": bool(is_inside) if is_inside is not None else None,
        }

    def distance_to_nearest_m(self, lat: float, lon: float) -> Optional[float]:
        info = self.enrich(lat, lon)
        return info["distance_to_industry"]

    def is_loaded(self) -> bool:
        return len(self.facilities) > 0
