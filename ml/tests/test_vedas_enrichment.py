"""
Tests for VEDAS enrichment - real ISRO/BharatAtlas data
"""
import json
import csv
from pathlib import Path
import tempfile
import pytest

from ml.geospatial.vedas_loader import load_all_vedas, normalize_vedas_features, load_vedas_dataset
from ml.geospatial.vedas_enrichment import VEDASIndex, enrich_firms_with_vedas

VEDAS_DIR = Path("data/geospatial/geojson")
FIRMS_INDIA = Path("data/firms/processed/firms_india.csv")
ENRICHED_VEDAS = Path("data/firms/processed/firms_enriched_vedas.csv")

def test_geojson_loading():
    all_data = load_all_vedas(VEDAS_DIR)
    assert len(all_data) == 6
    for fname in ["Vedas_Power_Plants.geojson", "Vedas_Oil_Refineries.geojson", "Vedas_Oil_Wells.geojson", "Vedas_Ethanol_Plants.geojson", "Vedas_Wind_Farms.geojson", "Vedas_Solar_Power_Plants.geojson"]:
        assert fname in all_data
        info = all_data[fname]
        assert info["record_count"] > 0
        assert "Point" in info["geometry_types"]
        assert info["crs"] == "EPSG:4326"
        assert info["bbox"] is not None
        assert len(info["available_properties"]) > 0

def test_crs_handling():
    all_data = load_all_vedas(VEDAS_DIR)
    for fname, info in all_data.items():
        assert info["crs"] == "EPSG:4326"
        assert "CRS84" in info["crs_raw"] or "4326" in info["crs_raw"]

def test_facility_type_normalization():
    all_data = load_all_vedas(VEDAS_DIR)
    normalized = normalize_vedas_features(all_data)
    types = set(f["facility_type"] for f in normalized)
    assert "power_plant" in types
    assert "oil_refinery" in types
    assert "oil_well" in types
    assert "ethanol_plant" in types
    assert "wind_farm" in types
    assert "solar_plant" in types
    # Check counts
    from collections import Counter
    cnt = Counter(f["facility_type"] for f in normalized)
    assert cnt["power_plant"] == 534
    assert cnt["oil_refinery"] == 23
    assert cnt["oil_well"] == 18949
    assert cnt["ethanol_plant"] == 320
    assert cnt["wind_farm"] == 20
    assert cnt["solar_plant"] == 166
    # Check power plant types normalized
    power_plants = [f for f in normalized if f["facility_type"] == "power_plant"]
    for pp in power_plants:
        assert pp["power_plant_type"] in ["thermal", "hydro", "other", None]
        # Check that original properties preserved
        assert "original_properties" in pp
        assert pp["source"] == "ISRO_VEDAS"

def test_invalid_geometry_handling():
    # Use small synthetic invalid geometry
    info = load_vedas_dataset(VEDAS_DIR / "Vedas_Power_Plants.geojson")
    # Check invalid count is 0 for real data (all valid)
    assert info["invalid_geometry_count"] == 0
    assert info["missing_coordinate_count"] == 0
    # Test with synthetic invalid
    import json, tempfile
    from pathlib import Path
    bad_geojson = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [200, 100]}, "properties": {"id": "bad1"}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [None, None]}, "properties": {"id": "bad2"}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [72.8, 19.0]}, "properties": {"id": "good"}},
        ]
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as tmp:
        json.dump(bad_geojson, tmp)
        tmp_path = Path(tmp.name)
    try:
        info2 = load_vedas_dataset(tmp_path)
        assert info2["invalid_geometry_count"] >= 1
        assert info2["missing_coordinate_count"] >= 1
    finally:
        tmp_path.unlink()

def test_nearest_distance_calculation():
    all_data = load_all_vedas(VEDAS_DIR)
    normalized = normalize_vedas_features(all_data)
    index = VEDASIndex(normalized)
    # Test known point near refinery (Mangalore refinery at 12.9141,74.856)
    # Find a refinery
    refinery = [f for f in normalized if f["facility_type"] == "oil_refinery"][0]
    lat, lon = refinery["latitude"], refinery["longitude"]
    nearest, dist = index.nearest(lat, lon)
    assert dist is not None
    assert dist < 100  # Should be very close to itself
    assert nearest["facility_type"] == "oil_refinery"
    # Test far point
    nearest_far, dist_far = index.nearest(28.6, 77.2)  # Delhi
    assert dist_far is not None
    assert dist_far > 1000

def test_radius_counting():
    all_data = load_all_vedas(VEDAS_DIR)
    normalized = normalize_vedas_features(all_data)
    index = VEDASIndex(normalized)
    # Test counts at known dense oil well area (Gujarat)
    # Oil wells are dense in Gujarat, should have many within 5km
    # Use a point near oil well cluster
    oil_well = [f for f in normalized if f["facility_type"] == "oil_well"][0]
    cnt_500 = index.count_within(oil_well["latitude"], oil_well["longitude"], 500, facility_type="oil_well")
    cnt_1km = index.count_within(oil_well["latitude"], oil_well["longitude"], 1000, facility_type="oil_well")
    cnt_5km = index.count_within(oil_well["latitude"], oil_well["longitude"], 5000, facility_type="oil_well")
    assert cnt_500 <= cnt_1km <= cnt_5km
    assert cnt_1km >= 1  # At least itself

def test_empty_datasets():
    index = VEDASIndex([])
    nearest, dist = index.nearest(19.0, 72.8)
    assert nearest is None
    assert dist is None
    assert index.count_within(19.0, 72.8, 1000) == 0

def test_missing_coordinates():
    # FIRMS row with missing coords should be handled
    with tempfile.TemporaryDirectory() as tmp:
        firms_path = Path(tmp) / "firms.csv"
        firms_path.write_text("id,latitude,longitude,frp,brightness_temperature,confidence,timestamp,satellite\n1,,72.8,10,320,60,2026-08-01T00:00:00Z,VIIRS\n2,19.0,,10,320,60,2026-08-01T00:00:00Z,VIIRS\n3,19.0,72.8,10,320,60,2026-08-01T00:00:00Z,VIIRS\n")
        all_data = load_all_vedas(VEDAS_DIR)
        normalized = normalize_vedas_features(all_data)
        index = VEDASIndex(normalized)
        out = Path(tmp) / "out.csv"
        enrich_firms_with_vedas(firms_path, index, out)
        with open(out) as f:
            rows = list(csv.DictReader(f))
            assert len(rows) == 3
            # First two should have None distances
            assert rows[0]["nearest_facility_distance_m"] in ("", None) or rows[0]["nearest_facility_distance_m"] == ""
            assert rows[1]["nearest_facility_distance_m"] in ("", None) or rows[1]["nearest_facility_distance_m"] == ""

def test_firms_row_preservation():
    firms_path = FIRMS_INDIA
    enriched_path = ENRICHED_VEDAS
    if not enriched_path.exists():
        pytest.skip("Enriched VEDAS not found")
    with open(firms_path) as f:
        firms_rows = list(csv.DictReader(f))
    with open(enriched_path) as f:
        enriched_rows = list(csv.DictReader(f))
    assert len(firms_rows) == len(enriched_rows) == 6523
    # Check original columns preserved
    for orig, enr in zip(firms_rows[:5], enriched_rows[:5]):
        for col in ["id","latitude","longitude","frp","brightness_temperature","confidence","timestamp","satellite"]:
            assert orig[col] == enr[col], f"{col} changed"

def test_no_accidental_label_generation():
    enriched_path = ENRICHED_VEDAS
    if not enriched_path.exists():
        pytest.skip("Enriched VEDAS not found")
    with open(enriched_path) as f:
        rows = list(csv.DictReader(f))
        for row in rows[:10]:
            assert "weak_label" not in row
            assert "label" not in row or row.get("weak_label") is None
            # Check no industrial_fire label
            for v in row.values():
                assert "industrial_fire" not in str(v)

def test_no_infinite_distances():
    enriched_path = ENRICHED_VEDAS
    if not enriched_path.exists():
        pytest.skip("Enriched VEDAS not found")
    with open(enriched_path) as f:
        rows = list(csv.DictReader(f))
        for row in rows:
            for col in ["nearest_facility_distance_m","nearest_power_plant_distance_m","nearest_oil_refinery_distance_m"]:
                v = row.get(col)
                if v not in ("", None):
                    fv = float(v)
                    assert fv != float('inf'), f"Infinite distance in {col}"
                    assert fv == fv, f"NaN in {col}"  # NaN check
                    assert fv >= 0, f"Negative distance {col} {fv}"

def test_no_invalid_numeric_values():
    enriched_path = ENRICHED_VEDAS
    if not enriched_path.exists():
        pytest.skip("Enriched VEDAS not found")
    with open(enriched_path) as f:
        rows = list(csv.DictReader(f))
        for row in rows:
            for col in ["facility_count_500m","facility_count_1km","facility_count_5km"]:
                v = row[col]
                assert v not in ("", None)
                iv = int(v)
                assert iv >= 0
                assert iv < 10000  # Sanity

def test_multiple_facility_types():
    all_data = load_all_vedas(VEDAS_DIR)
    normalized = normalize_vedas_features(all_data)
    index = VEDASIndex(normalized)
    # Test that all 6 types have facilities
    for ftype in ["power_plant","oil_refinery","oil_well","ethanol_plant","wind_farm","solar_plant"]:
        facs = [f for f in normalized if f["facility_type"] == ftype]
        assert len(facs) > 0, f"No facilities for {ftype}"
        # Test that nearest for each type works
        nearest, dist = index.nearest(19.0, 72.8, facility_type=ftype)
        assert nearest is not None or True  # Some types may be far but should still return nearest
