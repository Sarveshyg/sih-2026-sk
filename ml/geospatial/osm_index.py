"""
ml/geospatial/osm_index.py — Spatial index for OSM facilities.

Uses BallTree (haversine) for efficient nearest and radius queries.
WGS84, meters via haversine, not Cartesian.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import math
import numpy as np

try:
    from sklearn.neighbors import BallTree
    HAS_BALLTREE = True
except ImportError:
    HAS_BALLTREE = False

from .geo_utils import haversine_m

EARTH_RADIUS_M = 6371008.8

class OSMIndex:
    def __init__(self, facilities: List[Dict[str, Any]]):
        self.facilities = facilities or []
        self.lats = np.array([f["latitude"] for f in self.facilities], dtype=float) if facilities else np.array([])
        self.lons = np.array([f["longitude"] for f in self.facilities], dtype=float) if facilities else np.array([])
        self.types = [f.get("facility_type", "other") for f in self.facilities]
        self.tree = None
        if HAS_BALLTREE and len(self.facilities) > 0:
            # BallTree expects radians, lat/lon in radians, haversine distance in radians
            coords = np.radians(np.column_stack((self.lats, self.lons)))
            # Use haversine metric
            self.tree = BallTree(coords, metric="haversine")
        else:
            self.tree = None

    @classmethod
    def from_geojson(cls, path: Path) -> "OSMIndex":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        features = data.get("features", []) if isinstance(data, dict) else []
        facs = []
        for feat in features:
            geom = feat.get("geometry", {})
            props = feat.get("properties", {})
            if geom.get("type") != "Point":
                continue
            lon, lat = geom["coordinates"]
            facs.append({
                "osm_id": props.get("osm_id", ""),
                "latitude": float(lat),
                "longitude": float(lon),
                "facility_type": props.get("facility_type", "other"),
                "name": props.get("name"),
                "raw_tags": props.get("raw_tags", {}),
            })
        return cls(facs)

    def nearest(self, lat: float, lon: float) -> Tuple[Optional[Dict[str, Any]], Optional[float]]:
        if not self.facilities:
            return None, None
        if self.tree is not None:
            # Query nearest 1
            query = np.radians([[lat, lon]])
            dist_rad, idx = self.tree.query(query, k=1)
            best_idx = int(idx[0][0])
            # dist is in radians, convert to meters
            dist_m = float(dist_rad[0][0] * EARTH_RADIUS_M)
            # Verify with haversine for accuracy (BallTree haversine is same, but use our function for consistency)
            # Use haversine for final distance
            d = haversine_m(lat, lon, self.lats[best_idx], self.lons[best_idx])
            return self.facilities[best_idx], d
        else:
            # Brute force
            best = None
            best_d = float("inf")
            best_fac = None
            for i, fac in enumerate(self.facilities):
                d = haversine_m(lat, lon, fac["latitude"], fac["longitude"])
                if d < best_d:
                    best_d = d
                    best_fac = fac
            return best_fac, best_d if best_fac else (None, None)

    def count_within(self, lat: float, lon: float, radius_m: float, facility_type: Optional[str] = None) -> int:
        if not self.facilities:
            return 0
        if self.tree is not None:
            # BallTree radius is in radians
            radius_rad = radius_m / EARTH_RADIUS_M
            query = np.radians([[lat, lon]])
            indices = self.tree.query_radius(query, r=radius_rad, count_only=False)[0]
            if facility_type:
                # Filter by type
                cnt = 0
                for idx in indices:
                    if self.types[idx] == facility_type:
                        cnt += 1
                return cnt
            return len(indices)
        else:
            cnt = 0
            for fac in self.facilities:
                d = haversine_m(lat, lon, fac["latitude"], fac["longitude"])
                if d <= radius_m:
                    if facility_type is None or fac["facility_type"] == facility_type:
                        cnt += 1
            return cnt

    def nearest_for_type(self, lat: float, lon: float, facility_type: str) -> Optional[float]:
        # Find nearest of specific type
        best = None
        for fac in self.facilities:
            if fac["facility_type"] == facility_type:
                d = haversine_m(lat, lon, fac["latitude"], fac["longitude"])
                if best is None or d < best:
                    best = d
        return best

    def query_radius(self, lat: float, lon: float, radius_m: float) -> List[Dict[str, Any]]:
        if not self.facilities:
            return []
        if self.tree is not None:
            radius_rad = radius_m / EARTH_RADIUS_M
            query = np.radians([[lat, lon]])
            indices = self.tree.query_radius(query, r=radius_rad, count_only=False)[0]
            return [self.facilities[i] for i in indices]
        else:
            res = []
            for fac in self.facilities:
                if haversine_m(lat, lon, fac["latitude"], fac["longitude"]) <= radius_m:
                    res.append(fac)
            return res
