"""
VEDAS enrichment - real ISRO/BharatAtlas infrastructure
Uses BallTree haversine for point datasets, handles polygons via centroid
"""
import json
import csv
from pathlib import Path
from typing import Dict, List, Any, Optional
import math
import numpy as np

try:
    from sklearn.neighbors import BallTree
    HAS_BALLTREE = True
except ImportError:
    HAS_BALLTREE = False

from ml.geospatial.vedas_loader import load_all_vedas, normalize_vedas_features, VEDAS_DIR

EARTH_RADIUS_M = 6371008.8
FACILITY_TYPES = ["power_plant", "oil_refinery", "oil_well", "ethanol_plant", "wind_farm", "solar_plant"]

def _haversine_m(lat1, lon1, lat2, lon2):
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return EARTH_RADIUS_M * c

class VEDASIndex:
    def __init__(self, facilities: List[Dict[str, Any]]):
        self.facilities = facilities
        self.by_type = {}
        for ftype in FACILITY_TYPES:
            self.by_type[ftype] = [f for f in facilities if f["facility_type"] == ftype]
        self.trees = {}
        if HAS_BALLTREE:
            for ftype, facs in self.by_type.items():
                if facs:
                    coords = np.radians(np.array([[f["latitude"], f["longitude"]] for f in facs]))
                    self.trees[ftype] = BallTree(coords, metric='haversine')
            if facilities:
                all_coords = np.radians(np.array([[f["latitude"], f["longitude"]] for f in facilities]))
                self.trees["all"] = BallTree(all_coords, metric='haversine')

    def nearest(self, lat: float, lon: float, facility_type: Optional[str] = None):
        target_type = facility_type if facility_type else "all"
        facs = self.by_type.get(target_type) if facility_type else self.facilities
        if not facs:
            return None, None
        if HAS_BALLTREE and target_type in self.trees:
            tree = self.trees[target_type]
            dist_rad, idx = tree.query(np.radians([[lat, lon]]), k=1)
            best_idx = int(idx[0][0])
            best = facs[best_idx]
            dist_m = float(dist_rad[0][0] * EARTH_RADIUS_M)
            d = _haversine_m(lat, lon, best["latitude"], best["longitude"])
            return best, d
        else:
            best = None
            best_d = float('inf')
            for fac in facs:
                d = _haversine_m(lat, lon, fac["latitude"], fac["longitude"])
                if d < best_d:
                    best_d = d
                    best = fac
            return best, best_d if best else (None, None)

    def count_within(self, lat: float, lon: float, radius_m: float, facility_type: Optional[str] = None) -> int:
        target_type = facility_type if facility_type else "all"
        facs = self.by_type.get(target_type) if facility_type else self.facilities
        if not facs:
            return 0
        if HAS_BALLTREE and target_type in self.trees:
            tree = self.trees[target_type]
            radius_rad = radius_m / EARTH_RADIUS_M
            count = tree.query_radius(np.radians([[lat, lon]]), r=radius_rad, count_only=True)[0]
            return int(count)
        else:
            cnt = 0
            for fac in facs:
                if _haversine_m(lat, lon, fac["latitude"], fac["longitude"]) <= radius_m:
                    cnt += 1
            return cnt

def build_vedas_index(vedas_dir: Path = VEDAS_DIR):
    all_data = load_all_vedas(vedas_dir)
    normalized = normalize_vedas_features(all_data)
    return VEDASIndex(normalized), normalized, all_data

def enrich_firms_with_vedas(firms_path: Path, vedas_index: VEDASIndex, output_path: Path = None) -> Path:
    import csv
    firms_path = Path(firms_path)
    if output_path is None:
        output_path = Path("data/firms/processed/firms_enriched_vedas.csv")
    with open(firms_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        firms_rows = list(reader)
        firms_fieldnames = reader.fieldnames
    enriched = []
    for row in firms_rows:
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
        except:
            enriched_row = dict(row)
            enriched_row.update({
                "nearest_facility_distance_m": None,
                "nearest_facility_type": None,
                "facility_count_500m": 0,
                "facility_count_1km": 0,
                "facility_count_5km": 0,
                "power_plant_count_1km": 0,
                "oil_refinery_count_1km": 0,
                "oil_well_count_1km": 0,
                "ethanol_plant_count_1km": 0,
                "wind_farm_count_1km": 0,
                "solar_plant_count_1km": 0,
                "nearest_power_plant_distance_m": None,
                "nearest_oil_refinery_distance_m": None,
                "nearest_oil_well_distance_m": None,
                "nearest_ethanol_plant_distance_m": None,
                "nearest_wind_farm_distance_m": None,
                "nearest_solar_plant_distance_m": None,
            })
            enriched.append(enriched_row)
            continue
        # Use 5km as relevant search radius for nearest distances
        # If no facility within 5km, distance should be null (not 0, not far arbitrary)
        # Also add presence indicators
        nearest, dist = vedas_index.nearest(lat, lon)
        # Only keep dist if within 5km, else null
        if dist is not None and dist > 5000:
            dist = None
            nearest_type = None
            # Also need to find if any facility within 5km at all? dist >5km means no facility within 5km, so nearest should be null
        else:
            nearest_type = nearest["facility_type"] if nearest else None

        fac_500 = vedas_index.count_within(lat, lon, 500)
        fac_1km = vedas_index.count_within(lat, lon, 1000)
        fac_5km = vedas_index.count_within(lat, lon, 5000)

        counts = {}
        for ftype in FACILITY_TYPES:
            counts[ftype] = {
                "1km": vedas_index.count_within(lat, lon, 1000, facility_type=ftype),
                "5km": vedas_index.count_within(lat, lon, 5000, facility_type=ftype),
            }

        nearest_distances = {}
        nearest_present = {}
        for ftype in FACILITY_TYPES:
            _, d = vedas_index.nearest(lat, lon, facility_type=ftype)
            # Only keep if within 5km
            if d is not None and d > 5000:
                d = None
            nearest_distances[ftype] = d
            nearest_present[ftype] = 1 if d is not None else 0

        # Presence indicator for generic nearest
        nearest_present_generic = 1 if dist is not None else 0

        enriched_row = dict(row)
        enriched_row.update({
            "nearest_facility_distance_m": dist,
            "nearest_facility_present": nearest_present_generic,
            "nearest_facility_type": nearest_type,
            "facility_count_500m": fac_500,
            "facility_count_1km": fac_1km,
            "facility_count_5km": fac_5km,
            "power_plant_count_1km": counts["power_plant"]["1km"],
            "oil_refinery_count_1km": counts["oil_refinery"]["1km"],
            "oil_well_count_1km": counts["oil_well"]["1km"],
            "ethanol_plant_count_1km": counts["ethanol_plant"]["1km"],
            "wind_farm_count_1km": counts["wind_farm"]["1km"],
            "solar_plant_count_1km": counts["solar_plant"]["1km"],
            "nearest_power_plant_distance_m": nearest_distances["power_plant"],
            "nearest_power_plant_present": nearest_present["power_plant"],
            "nearest_oil_refinery_distance_m": nearest_distances["oil_refinery"],
            "nearest_oil_refinery_present": nearest_present["oil_refinery"],
            "nearest_oil_well_distance_m": nearest_distances["oil_well"],
            "nearest_oil_well_present": nearest_present["oil_well"],
            "nearest_ethanol_plant_distance_m": nearest_distances["ethanol_plant"],
            "nearest_ethanol_plant_present": nearest_present["ethanol_plant"],
            "nearest_wind_farm_distance_m": nearest_distances["wind_farm"],
            "nearest_wind_farm_present": nearest_present["wind_farm"],
            "nearest_solar_plant_distance_m": nearest_distances["solar_plant"],
            "nearest_solar_plant_present": nearest_present["solar_plant"],
        })
        enriched.append(enriched_row)
    new_fields = [
        "nearest_facility_distance_m", "nearest_facility_present", "nearest_facility_type",
        "facility_count_500m", "facility_count_1km", "facility_count_5km",
        "power_plant_count_1km", "oil_refinery_count_1km", "oil_well_count_1km",
        "ethanol_plant_count_1km", "wind_farm_count_1km", "solar_plant_count_1km",
        "nearest_power_plant_distance_m", "nearest_power_plant_present",
        "nearest_oil_refinery_distance_m", "nearest_oil_refinery_present",
        "nearest_oil_well_distance_m", "nearest_oil_well_present",
        "nearest_ethanol_plant_distance_m", "nearest_ethanol_plant_present",
        "nearest_wind_farm_distance_m", "nearest_wind_farm_present",
        "nearest_solar_plant_distance_m", "nearest_solar_plant_present"
    ]
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = firms_fieldnames + [f for f in new_fields if f not in firms_fieldnames]
    with open(output_path, 'w', newline='', encoding='utf-8') as out:
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()
        for row in enriched:
            for f in new_fields:
                if f not in row:
                    row[f] = None
            writer.writerow({k: row.get(k) for k in fieldnames})
    return output_path

def main():
    import argparse
    parser = argparse.ArgumentParser(description="VEDAS enrichment for FIRMS")
    parser.add_argument("--input", default="data/geospatial/geojson", help="VEDAS input dir")
    parser.add_argument("--output-dir", default="data/geospatial/vedas", help="Output dir for normalized VEDAS")
    parser.add_argument("--firms", default="data/firms/processed/firms_india.csv", help="FIRMS India CSV")
    parser.add_argument("--firms-output", default="data/firms/processed/firms_enriched_vedas.csv", help="Enriched FIRMS output")
    args = parser.parse_args()
    print("Loading VEDAS datasets...")
    all_data = load_all_vedas(Path(args.input))
    for fname, info in all_data.items():
        print(f"{fname}: {info['record_count']} records, geom {info['geometry_types']}, CRS {info['crs']}, bbox {info['bbox']}")
    normalized = normalize_vedas_features(all_data)
    print(f"Normalized total: {len(normalized)} facilities")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    features = []
    for fac in normalized:
        features.append({
            "type": "Feature",
            "geometry": {"type": fac["geometry_type"], "coordinates": [fac["longitude"], fac["latitude"]]},
            "properties": {k: v for k, v in fac.items() if k not in ["longitude", "latitude", "geometry_type"]}
        })
    geojson = {"type": "FeatureCollection", "features": features}
    (output_dir / "vedas_facilities.geojson").write_text(json.dumps(geojson, indent=2), encoding='utf-8')
    print(f"Wrote {output_dir / 'vedas_facilities.geojson'}")
    import csv
    all_keys = set()
    for fac in normalized:
        all_keys.update(fac.keys())
    fieldnames = ["source", "facility_type", "latitude", "longitude", "geometry_type", "crs"] + sorted([k for k in all_keys if k not in ["source", "facility_type", "latitude", "longitude", "geometry_type", "crs", "original_geometry", "original_properties"]]) + ["original_properties"]
    with open(output_dir / "vedas_facilities.csv", 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for fac in normalized:
            row = {k: fac.get(k) for k in fieldnames}
            if isinstance(row.get("original_properties"), dict):
                row["original_properties"] = json.dumps(row["original_properties"], ensure_ascii=False)
            writer.writerow(row)
    print(f"Wrote {output_dir / 'vedas_facilities.csv'}")
    from collections import Counter
    report = {
        "source_files": {fname: info["record_count"] for fname, info in all_data.items()},
        "total_records": len(normalized),
        "geometry_types": list(set(f["geometry_type"] for f in normalized)),
        "crs": "EPSG:4326",
        "bbox": [min(f["longitude"] for f in normalized), min(f["latitude"] for f in normalized), max(f["longitude"] for f in normalized), max(f["latitude"] for f in normalized)] if normalized else None,
        "facility_type_counts": dict(Counter(f["facility_type"] for f in normalized)),
        "invalid_geometry_count": sum(info["invalid_geometry_count"] for info in all_data.values()),
        "missing_coordinate_count": sum(info["missing_coordinate_count"] for info in all_data.values()),
    }
    (output_dir / "vedas_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {output_dir / 'vedas_report.json'}")
    print(json.dumps(report, indent=2))
    firms_path = Path(args.firms)
    if firms_path.exists():
        print(f"Enriching FIRMS {firms_path}...")
        vedas_index, _, _ = build_vedas_index(Path(args.input))
        output_firms = Path(args.firms_output)
        enrich_firms_with_vedas(firms_path, vedas_index, output_firms)
        print(f"Wrote enriched FIRMS {output_firms}")
    else:
        print(f"FIRMS not found: {firms_path}, skipping enrichment")

if __name__ == "__main__":
    main()
