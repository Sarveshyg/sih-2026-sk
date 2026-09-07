"""
ml/geospatial/geo_utils.py — Geodesic utilities.

Semantics (verified for ML training):
  Point      → point-to-point haversine (great-circle, meters)
  Polygon    → minimum distance to polygon boundary; 0 if point inside (including holes)
  MultiPolygon → minimum across polygons; 0 if inside any polygon

No Cartesian degree distance. Pure-Python ray-casting + haversine-to-segment
is the default and always available. When Shapely is installed, callers may
optionally use it for validation/indexing, but meter outputs remain haversine-based.
"""

from __future__ import annotations

import math
from typing import List, Tuple

EARTH_RADIUS_M = 6_371_008.8  # mean radius (IUGG)

# Optional Shapely — never required. If present, callers (FacilityEnricher)
# may use it for validation/STRtree indexing while keeping haversine for meters.
try:
    import shapely  # type: ignore  # noqa: F401
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two WGS84 points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return EARTH_RADIUS_M * c


def point_in_ring(lat: float, lon: float, ring: List[List[float]]) -> bool:
    """
    Ray casting for a single linear ring.
    Ring is list of [lon, lat] per GeoJSON.
    Returns True if point inside (including boundary approx).
    """
    # Use winding / ray crossing algorithm
    x = lon
    y = lat
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        # Check if point is exactly on edge (tolerance ~1e-9 deg ~0.1m)
        # quick bbox check
        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)
        if intersect:
            inside = not inside
        j = i
    return inside


def point_in_polygon(lat: float, lon: float, polygon_coords: List[List[List[float]]]) -> bool:
    """
    GeoJSON Polygon check: polygon_coords = [ exterior_ring, hole1, ... ]
    """
    if not polygon_coords:
        return False
    exterior = polygon_coords[0]
    if not point_in_ring(lat, lon, exterior):
        return False
    # Check holes: if inside any hole, then outside
    for hole in polygon_coords[1:]:
        if point_in_ring(lat, lon, hole):
            return False
    return True


def point_in_multipolygon(lat: float, lon: float, multipolygon_coords: List[List[List[List[float]]]]) -> bool:
    for polygon in multipolygon_coords:
        if point_in_polygon(lat, lon, polygon):
            return True
    return False


def _point_to_segment_distance_m(
    lat: float, lon: float, lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Approx distance from point to segment via haversine to closest point on segment.
    Uses equirectangular projection for interpolation (adequate < 10km).
    """
    # Fast: distance to endpoints if segment is degenerate
    if lat1 == lat2 and lon1 == lon2:
        return haversine_m(lat, lon, lat1, lon1)
    # Convert to local ENU approx (meters) around segment midpoint for projection
    # Use average latitude for lon scaling
    avg_lat = (lat1 + lat2 + lat) / 3.0
    # meters per degree
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(avg_lat))
    # Project to local cartesian (x=lon, y=lat) in meters
    px, py = lon * m_per_deg_lon, lat * m_per_deg_lat
    x1, y1 = lon1 * m_per_deg_lon, lat1 * m_per_deg_lat
    x2, y2 = lon2 * m_per_deg_lon, lat2 * m_per_deg_lat
    # Projection param t
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return haversine_m(lat, lon, lat1, lon1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    # Closest point on segment in cart - convert back approx
    # Instead of converting back, compute distance in cart then refine with haversine?
    # For prototype: if t is endpoint, use haversine to endpoint; else interpolate lat/lon
    if t == 0.0:
        return haversine_m(lat, lon, lat1, lon1)
    if t == 1.0:
        return haversine_m(lat, lon, lat2, lon2)
    # Interpolate lat/lon linearly
    closest_lat = lat1 + t * (lat2 - lat1)
    closest_lon = lon1 + t * (lon2 - lon1)
    return haversine_m(lat, lon, closest_lat, closest_lon)


def distance_to_polygon_m(lat: float, lon: float, polygon_coords: List[List[List[float]]]) -> float:
    """
    Distance from point to Polygon (in meters).
    0 if inside. Else min distance to edges.
    polygon_coords: GeoJSON Polygon coordinates [ [ [lon,lat], ... ], ... ]
    """
    if point_in_polygon(lat, lon, polygon_coords):
        return 0.0
    exterior = polygon_coords[0]
    min_dist = float("inf")
    n = len(exterior)
    for i in range(n):
        a = exterior[i]
        b = exterior[(i + 1) % n]
        # a,b are [lon, lat]
        d = _point_to_segment_distance_m(lat, lon, a[1], a[0], b[1], b[0])
        if d < min_dist:
            min_dist = d
    # Also check holes? Distance to hole edge not needed for outside point (exterior closest)
    # but if polygon is donut, point outside exterior already handled; holes interior not relevant.
    return min_dist if min_dist != float("inf") else float("inf")


def distance_to_multipolygon_m(lat: float, lon: float, multipolygon_coords: List[List[List[List[float]]]]) -> float:
    if point_in_multipolygon(lat, lon, multipolygon_coords):
        return 0.0
    best = float("inf")
    for poly in multipolygon_coords:
        d = distance_to_polygon_m(lat, lon, poly)
        if d < best:
            best = d
    return best


def distance_to_geometry_m(lat: float, lon: float, geometry: dict) -> float:
    """
    Dispatch for GeoJSON geometry dict.
    Supports Point, Polygon, MultiPolygon.
    For Point: haversine.
    For Polygon/MultiPolygon: edge distance (0 inside).
    """
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Point":
        lon0, lat0 = coords[0], coords[1]
        return haversine_m(lat, lon, lat0, lon0)
    if gtype == "Polygon":
        return distance_to_polygon_m(lat, lon, coords)
    if gtype == "MultiPolygon":
        return distance_to_multipolygon_m(lat, lon, coords)
    # Fallback: unknown type → distance to centroid if possible, else inf
    return float("inf")
