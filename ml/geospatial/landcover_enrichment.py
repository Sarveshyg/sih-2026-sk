"""
ml/geospatial/landcover_enrichment.py — Land-cover and environmental distance enrichment.

Supports local vector polygons (GeoJSON) for classes:
  forest, agriculture, industrial/built-up, water, bare land, other, unknown

Design:
- Single landcover GeoJSON with property 'class' / 'landcover' / 'type' / 'landuse'
  is mapped to canonical vocabulary.
- Separate forest/agriculture distance datasets are optional; if a dedicated
  forest polygon file is not supplied, the forest subset of landcover is used
  for distance_to_forest (same for agriculture).
- No fabrication: missing dataset → None / "unknown".
- Polygons are checked via point-in-polygon (ray casting); distances via haversine edge.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Optional, Any

from .geo_utils import distance_to_geometry_m, point_in_polygon, point_in_multipolygon

CANONICAL_LANDCOVER = {"forest", "agriculture", "industrial", "water", "bare", "other", "unknown"}

_LANDCOVER_MAP = {
    # forest
    "forest": "forest",
    "wood": "forest",
    "woods": "forest",
    "tree": "forest",
    "trees": "forest",
    "forestry": "forest",
    "jungle": "forest",
    # agriculture
    "agriculture": "agriculture",
    "agricultural": "agriculture",
    "farmland": "agriculture",
    "farm": "agriculture",
    "cropland": "agriculture",
    "field": "agriculture",
    "meadow": "agriculture",
    "orchard": "agriculture",
    "plantation": "agriculture",
    # industrial / built-up
    "industrial": "industrial",
    "built-up": "industrial",
    "builtup": "industrial",
    "urban": "industrial",
    "residential": "industrial",
    "commercial": "industrial",
    "built_up": "industrial",
    # water
    "water": "water",
    "lake": "water",
    "river": "water",
    "sea": "water",
    "ocean": "water",
    "wetland": "water",
    # bare
    "bare": "bare",
    "barren": "bare",
    "desert": "bare",
    "bare_land": "bare",
    "sand": "bare",
    # other fallback
    "grass": "other",
    "grassland": "other",
    "shrub": "other",
}


def normalize_landcover_class(properties: Dict[str, Any]) -> str:
    """
    Map landcover feature properties to canonical class.
    Checks keys: class, landcover, land_cover, type, landuse, category, natural.
    Preserves raw lowercased value for fuzzy matching.
    """
    candidates: List[str] = []
    for key in ("class", "landcover", "land_cover", "type", "landuse", "category", "natural", "cover"):
        v = properties.get(key)
        if v not in (None, ""):
            candidates.append(str(v).strip().lower())
    # Also check 'name' heuristics? Not reliable.
    if not candidates:
        return "unknown"
    for c in candidates:
        if c in _LANDCOVER_MAP:
            return _LANDCOVER_MAP[c]
        # fuzzy: substring
        for k, canon in _LANDCOVER_MAP.items():
            if k in c:
                return canon
        # direct canonical passthrough
        if c in CANONICAL_LANDCOVER:
            return c
    return "other"


class LandcoverEnricher:
    """
    Loads landcover polygons (GeoJSON) and answers:
      landcover_class (point-in-polygon)
      distance_to_forest, distance_to_agriculture (nearest edge, meters)
    """

    def __init__(self, polygons: Optional[List[Dict[str, Any]]] = None):
        # polygons: List[{geometry, canonical_class, properties}]
        self.polygons: List[Dict[str, Any]] = polygons or []
        self.forest_geoms: List[Dict[str, Any]] = [p for p in self.polygons if p["canonical_class"] == "forest"]
        self.agri_geoms: List[Dict[str, Any]] = [p for p in self.polygons if p["canonical_class"] == "agriculture"]

    @classmethod
    def from_geojson(
        cls,
        path: str | Path | Dict[str, Any] | List[Dict[str, Any]] | None,
        *,
        class_filter: Optional[str] = None,
    ) -> "LandcoverEnricher":
        if path is None:
            return cls([])
        if isinstance(path, dict):
            data = path
        elif isinstance(path, list):
            data = {"type": "FeatureCollection", "features": path}
        elif isinstance(path, (str, Path)) and Path(path).exists():
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        elif isinstance(path, (str, Path)) and str(path).strip().startswith("{"):
            data = json.loads(str(path))
        else:
            raise FileNotFoundError(f"Landcover GeoJSON not found: {path}")

        features: List[Dict[str, Any]] = []
        if data.get("type") == "FeatureCollection":
            features = data.get("features", [])
        elif data.get("type") == "Feature":
            features = [data]
        elif isinstance(data, list):
            features = data

        parsed: List[Dict[str, Any]] = []
        for feat in features:
            geom = feat.get("geometry")
            if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
                continue
            props = feat.get("properties") or {}
            canon = normalize_landcover_class(props)
            if class_filter and canon != class_filter:
                continue
            parsed.append({"geometry": geom, "canonical_class": canon, "properties": props})
        return cls(parsed)

    def enrich(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Returns dict:
          landcover_class (str), distance_to_forest (float|None), distance_to_agriculture (float|None)
        Missing datasets → None / "unknown" (no fabrication).
        """
        if not self.polygons:
            return {
                "landcover_class": "unknown",
                "distance_to_forest": None,
                "distance_to_agriculture": None,
                "distance_to_forest_m": None,
                "distance_to_agriculture_m": None,
            }

        # Landcover class: point-in-polygon first hit (topmost). If multiple overlap, first wins.
        lc_class = "unknown"
        for poly in self.polygons:
            geom = poly["geometry"]
            gtype = geom["type"]
            coords = geom["coordinates"]
            inside = False
            if gtype == "Polygon":
                inside = point_in_polygon(lat, lon, coords)
            elif gtype == "MultiPolygon":
                inside = point_in_multipolygon(lat, lon, coords)
            if inside:
                lc_class = poly["canonical_class"]
                break

        # Distances: use forest/agri subsets; if empty, compute from polygons directly? We already filtered.
        # For this enricher, forest/agri distances are computed from respective subsets.
        forest_dist: Optional[float] = None
        agri_dist: Optional[float] = None

        if self.forest_geoms:
            best = float("inf")
            for poly in self.forest_geoms:
                d = distance_to_geometry_m(lat, lon, poly["geometry"])
                if d < best:
                    best = d
            forest_dist = float(best) if best != float("inf") else None
        if self.agri_geoms:
            best = float("inf")
            for poly in self.agri_geoms:
                d = distance_to_geometry_m(lat, lon, poly["geometry"])
                if d < best:
                    best = d
            agri_dist = float(best) if best != float("inf") else None

        return {
            "landcover_class": lc_class,
            "distance_to_forest": forest_dist,
            "distance_to_agriculture": agri_dist,
            "distance_to_forest_m": forest_dist,
            "distance_to_agriculture_m": agri_dist,
        }

    def distance_to_forest_m(self, lat: float, lon: float) -> Optional[float]:
        return self.enrich(lat, lon)["distance_to_forest"]

    def distance_to_agriculture_m(self, lat: float, lon: float) -> Optional[float]:
        return self.enrich(lat, lon)["distance_to_agriculture"]

    def is_loaded(self) -> bool:
        return len(self.polygons) > 0
