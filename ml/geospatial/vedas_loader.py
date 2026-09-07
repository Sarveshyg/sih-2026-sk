"""
VEDAS loader - loads six ISRO VEDAS GeoJSON datasets

Uses GeoPandas if available, else falls back to json + manual handling.
All datasets are EPSG:4326 (OGC:CRS84) Point geometries.
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
import math

VEDAS_DIR = Path("data/geospatial/geojson")
# Mapping from filename to facility_type
FILENAME_TO_TYPE = {
    "Vedas_Power_Plants.geojson": "power_plant",
    "Vedas_Oil_Refineries.geojson": "oil_refinery",
    "Vedas_Oil_Wells.geojson": "oil_well",
    "Vedas_Ethanol_Plants.geojson": "ethanol_plant",
    "Vedas_Wind_Farms.geojson": "wind_farm",
    "Vedas_Solar_Power_Plants.geojson": "solar_plant",
}

# For power plants, normalize layer to power_plant_type
POWER_LAYER_MAP = {
    "coal_power_plants": "thermal",
    "natural_gas_power_plants": "thermal",
    "diesel_power_plants": "thermal",
    "hydro_power_plants": "hydro",
    "small_hydro_power_plants": "hydro",
    "pumped_storage_hydro_power_plants": "hydro",
}

def _is_valid_coord(lon: float, lat: float) -> bool:
    return -180 <= lon <= 180 and -90 <= lat <= 90

def load_vedas_dataset(filepath: Path) -> Dict[str, Any]:
    """Load single GeoJSON file, return normalized info"""
    data = json.loads(filepath.read_text(encoding='utf-8'))
    features = data.get("features", [])
    # CRS
    crs = data.get("crs", {})
    crs_name = crs.get("properties", {}).get("name", "urn:ogc:def:crs:OGC::CRS84") if crs else "urn:ogc:def:crs:OGC::CRS84"
    # Determine EPSG
    if "CRS84" in crs_name or "4326" in crs_name:
        epsg = "EPSG:4326"
    else:
        epsg = crs_name

    record_count = len(features)
    geom_types = set()
    invalid_geom = 0
    missing_coord = 0
    lons = []
    lats = []
    properties_sets = []

    for feat in features:
        geom = feat.get("geometry", {})
        gtype = geom.get("type")
        geom_types.add(gtype)
        coords = geom.get("coordinates")
        # Handle Point and Polygon
        if gtype == "Point":
            if not coords or len(coords) < 2:
                invalid_geom += 1
                continue
            lon, lat = coords[0], coords[1]
            # also check xmin/ymin etc. but primary is geometry
            if lon is None or lat is None:
                missing_coord += 1
            elif not _is_valid_coord(lon, lat):
                invalid_geom += 1
            else:
                lons.append(lon)
                lats.append(lat)
        elif gtype in ("Polygon", "MultiPolygon"):
            # For polygon, check coordinates validity, use centroid for bbox
            try:
                # Extract all points
                pts = []
                if gtype == "Polygon":
                    pts = coords[0]
                else:  # MultiPolygon
                    for poly in coords:
                        pts.extend(poly[0])
                for lon, lat in pts:
                    if not _is_valid_coord(lon, lat):
                        invalid_geom += 1
                        break
                    lons.append(lon)
                    lats.append(lat)
                else:
                    # Only executed if no break
                    pass
            except Exception:
                invalid_geom += 1
        else:
            invalid_geom += 1

        props = feat.get("properties", {})
        properties_sets.append(set(props.keys()))

    # Bounding box
    if lons and lats:
        bbox = [min(lons), min(lats), max(lons), max(lats)]  # minx, miny, maxx, maxy
    else:
        bbox = None

    # Available properties union
    all_props = set()
    for s in properties_sets:
        all_props.update(s)

    return {
        "filepath": str(filepath),
        "filename": filepath.name,
        "record_count": record_count,
        "geometry_types": list(geom_types),
        "crs": epsg,
        "crs_raw": crs_name,
        "available_properties": sorted(list(all_props)),
        "invalid_geometry_count": invalid_geom,
        "missing_coordinate_count": missing_coord,
        "bbox": bbox,
        "features": features  # Keep for downstream
    }

def load_all_vedas(vedas_dir: Path = VEDAS_DIR) -> Dict[str, Dict[str, Any]]:
    """Load all six datasets"""
    result = {}
    for fname in FILENAME_TO_TYPE.keys():
        fpath = Path(vedas_dir) / fname
        if not fpath.exists():
            raise FileNotFoundError(f"VEDAS file not found: {fpath}")
        info = load_vedas_dataset(fpath)
        result[fname] = info
    return result

def normalize_vedas_features(all_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize all datasets into common internal representation"""
    normalized = []
    for fname, info in all_data.items():
        ftype = FILENAME_TO_TYPE.get(fname, "other")
        for feat in info["features"]:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            # Extract coordinates - handle Point and Polygon
            lon, lat = None, None
            geom_type = geom.get("type")
            coords = geom.get("coordinates")
            if geom_type == "Point":
                lon, lat = coords[0], coords[1]
            elif geom_type == "Polygon":
                # Use centroid (average of exterior ring)
                ring = coords[0]
                lons = [c[0] for c in ring]
                lats = [c[1] for c in ring]
                lon = sum(lons) / len(lons) if lons else None
                lat = sum(lats) / len(lats) if lats else None
                geom_type = "Point"  # Normalize polygon to point for BallTree
            elif geom_type == "MultiPolygon":
                # Use first polygon centroid
                ring = coords[0][0]
                lons = [c[0] for c in ring]
                lats = [c[1] for c in ring]
                lon = sum(lons) / len(lons) if lons else None
                lat = sum(lats) / len(lats) if lats else None
                geom_type = "Point"
            else:
                continue

            if lon is None or lat is None or not _is_valid_coord(lon, lat):
                continue

            # Build normalized record
            norm = {
                "source": "ISRO_VEDAS",
                "facility_type": ftype,
                "original_file": fname,
                "geometry_type": geom_type,
                "longitude": lon,
                "latitude": lat,
                "crs": "EPSG:4326",
            }
            # Preserve useful original properties
            # For each dataset, preserve relevant fields
            if ftype == "power_plant":
                norm["plant_name"] = props.get("plant_name")
                norm["state"] = props.get("state")
                norm["district"] = props.get("district")
                norm["inst_cap"] = props.get("inst_cap")
                norm["layer"] = props.get("layer")
                # Normalize power_plant_type
                layer = props.get("layer", "")
                norm["power_plant_type"] = POWER_LAYER_MAP.get(layer, "other" if layer else None)
                norm["original_properties"] = props
            elif ftype == "oil_refinery":
                norm["company"] = props.get("ppaccompan")
                norm["location"] = props.get("location")
                norm["district"] = props.get("ppacdistri")
                norm["capacity"] = props.get("distillati") or props.get("distilla_1")
                norm["original_properties"] = props
            elif ftype == "oil_well":
                norm["well_name"] = props.get("well_name")
                norm["operator"] = props.get("operator")
                norm["original_properties"] = props
            elif ftype == "ethanol_plant":
                norm["utilname"] = props.get("utilname")
                norm["statename"] = props.get("statename")
                norm["original_properties"] = props
            elif ftype == "wind_farm":
                norm["plant_name"] = props.get("plant_name")
                norm["state"] = props.get("state")
                norm["inst_cap"] = props.get("inst_cap")
                norm["primary_fu"] = props.get("primary_fu")
                norm["original_properties"] = props
            elif ftype == "solar_plant":
                norm["state_name"] = props.get("state_name")
                norm["location"] = props.get("location")
                norm["inst_cap_m"] = props.get("inst_cap_m")
                norm["original_properties"] = props

            # Also keep raw geometry for audit
            norm["original_geometry"] = geom
            # Keep original properties for audit
            if "original_properties" not in norm:
                norm["original_properties"] = props

            normalized.append(norm)
    return normalized
