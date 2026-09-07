"""
ml/geospatial/osm_enrich.py — FIRMS enrichment via PBF-derived OSM facilities.

Uses data/geospatial/osm/facilities.geojson (from osm_extract) via OSMIndex (BallTree).
Computes for each FIRMS detection:
  nearest_facility_distance_m, nearest_facility_category,
  facility_count_500m/1km/5km, etc.
If no facility within 5km, distance = None (not 0, not fabricated).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from .osm_index import OSMIndex

DEFAULT_FACILITIES = Path("data/geospatial/osm/facilities.geojson")
DEFAULT_FIRMS = Path("data/firms/processed/firms_india.csv")
DEFAULT_OUTPUT = Path("data/firms/processed/firms_enriched_real_osm.csv")

# Radii
RADIUS_500 = 500
RADIUS_1KM = 1000
RADIUS_5KM = 5000

def enrich_firms(
    firms_path: Path = DEFAULT_FIRMS,
    facilities_path: Path = DEFAULT_FACILITIES,
    output_path: Path = DEFAULT_OUTPUT,
) -> Dict[str, Any]:
    firms_path = Path(firms_path)
    facilities_path = Path(facilities_path)
    output_path = Path(output_path)

    if not firms_path.exists():
        raise FileNotFoundError(f"FIRMS not found: {firms_path}")
    if not facilities_path.exists():
        raise FileNotFoundError(f"Facilities not found: {facilities_path}. Run osm_extract first.")

    # Load OSM index
    index = OSMIndex.from_geojson(facilities_path)
    print(f"Loaded {len(index.facilities)} OSM facilities from {facilities_path}")

    # Read FIRMS
    with firms_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    
    # Check for required columns
    if "latitude" not in fieldnames or "longitude" not in fieldnames:
        raise ValueError(f"FIRMS missing lat/lon: {fieldnames}")

    # Enrich
    enriched = []
    for row in rows:
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
        except Exception:
            # Invalid coords -> keep original with None
            enriched.append({**row, "nearest_facility_distance_m": None, "nearest_facility_category": None, "facility_count_500m": 0, "facility_count_1km": 0, "facility_count_5km": 0})
            continue

        nearest, dist = index.nearest(lat, lon)
        # If no facility within 5km, set distance to None per spec (not arbitrary far)
        # Check if nearest within 5km
        if dist is not None and dist > RADIUS_5KM:
            dist_out = None
            cat_out = None
        else:
            dist_out = dist
            cat_out = nearest["facility_type"] if nearest else None

        # Counts
        cnt500 = index.count_within(lat, lon, RADIUS_500)
        cnt1k = index.count_within(lat, lon, RADIUS_1KM)
        cnt5k = index.count_within(lat, lon, RADIUS_5KM)

        enriched.append({
            **row,
            "nearest_facility_distance_m": dist_out,
            "nearest_facility_category": cat_out,
            "nearest_facility_osm_id": nearest["osm_id"] if nearest and dist_out is not None else None,
            "nearest_facility_name": nearest.get("name") if nearest and dist_out is not None else None,
            "facility_count_500m": cnt500,
            "facility_count_1km": cnt1k,
            "facility_count_5km": cnt5k,
        })

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Preserve original fieldnames + new
    new_fields = ["nearest_facility_distance_m","nearest_facility_category","nearest_facility_osm_id","nearest_facility_name","facility_count_500m","facility_count_1km","facility_count_5km"]
    out_fields = fieldnames + [f for f in new_fields if f not in fieldnames]
    with output_path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(enriched)

    # Coverage analysis
    total = len(enriched)
    within_500 = sum(1 for r in enriched if r["facility_count_500m"] and int(r["facility_count_500m"]) > 0)
    within_1k = sum(1 for r in enriched if r["facility_count_1km"] and int(r["facility_count_1km"]) > 0)
    within_5k = sum(1 for r in enriched if r["facility_count_5km"] and int(r["facility_count_5km"]) > 0)
    # Alternative via distance
    with_500_dist = sum(1 for r in enriched if r["nearest_facility_distance_m"] is not None and float(r["nearest_facility_distance_m"]) <= 500)
    with_1k_dist = sum(1 for r in enriched if r["nearest_facility_distance_m"] is not None and float(r["nearest_facility_distance_m"]) <= 1000)
    with_5k_dist = sum(1 for r in enriched if r["nearest_facility_distance_m"] is not None and float(r["nearest_facility_distance_m"]) <= 5000)

    # Median/p95 distance
    dists = [float(r["nearest_facility_distance_m"]) for r in enriched if r["nearest_facility_distance_m"] is not None]
    median = None
    p95 = None
    if dists:
        import numpy as np
        median = float(np.median(dists))
        p95 = float(np.percentile(dists, 95))

    # Category distribution of nearest
    from collections import Counter
    cat_dist = Counter(r["nearest_facility_category"] for r in enriched if r["nearest_facility_category"])

    report = {
        "firms_input": str(firms_path),
        "facilities": str(facilities_path),
        "output": str(output_path),
        "total_firms": total,
        "within_500m": with_500_dist,
        "within_1km": with_1k_dist,
        "within_5km": with_5k_dist,
        "pct_500m": round(100*with_500_dist/total,2) if total else 0,
        "pct_1km": round(100*with_1k_dist/total,2) if total else 0,
        "pct_5km": round(100*with_5k_dist/total,2) if total else 0,
        "facility_count_500m_nonzero": within_500,
        "facility_count_1km_nonzero": within_1k,
        "facility_count_5km_nonzero": within_5k,
        "median_nearest_distance_m": median,
        "p95_nearest_distance_m": p95,
        "nearest_category_distribution": dict(cat_dist),
        "no_facility_within_5km": total - with_5k_dist,
        "facility_total": len(index.facilities),
    }
    # Write report
    report_path = Path("data/firms/processed/osm_coverage_report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Enriched {total} FIRMS -> {output_path}")
    print(f"500m: {with_500_dist} ({report['pct_500m']}%), 1km: {with_1k_dist} ({report['pct_1km']}%), 5km: {with_5k_dist} ({report['pct_5km']}%)")
    print(f"Median distance: {median}, p95: {p95}")
    return report

def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Enrich FIRMS with PBF OSM facilities")
    parser.add_argument("--firms", default=str(DEFAULT_FIRMS), help="FIRMS India CSV")
    parser.add_argument("--facilities", default=str(DEFAULT_FACILITIES), help="OSM facilities.geojson")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output enriched CSV")
    args = parser.parse_args(argv)
    report = enrich_firms(Path(args.firms), Path(args.facilities), Path(args.output))
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
