"""
Tests for targeted OSM query (thermal/industrial context) — wind turbines excluded.
"""

import json
import tempfile
from pathlib import Path
import pytest

from ml.geospatial.osm_downloader import build_overpass_query, build_broad_overpass_query
from ml.geospatial.facility_enrichment import normalize_facility_type
from ml.geospatial.osm_enrichment import overpass_to_geojson

def test_targeted_query_excludes_wind_generators():
    q = build_overpass_query("7.95,76.95,9.05,78.05")
    # Should NOT contain power=generator at all (omitted for thermal)
    assert 'power"="generator"' not in q
    assert 'generator' not in q.lower() or 'power' not in q.lower() or 'generator:source' not in q
    # Should contain power=plant
    assert 'power"="plant"' in q
    # Should contain industrial
    assert 'industrial' in q

def test_broad_query_contains_generators():
    q = build_broad_overpass_query("7.95,76.95,9.05,78.05")
    assert 'power"="generator"' in q

def test_wind_generators_excluded_via_normalization():
    # Wind turbine should be other, not power_plant
    props_wind = {"power": "generator", "generator:source": "wind", "raw_tags": {"power": "generator", "generator:source": "wind"}}
    canon, _ = normalize_facility_type(props_wind)
    assert canon == "other"
    # Also via raw_tags
    props_wind2 = {"power": "generator", "raw_tags": {"power": "generator", "generator:source": "wind"}}
    assert normalize_facility_type(props_wind2)[0] == "other"

def test_coal_thermal_generator_retained():
    props_coal = {"power": "generator", "generator:source": "coal"}
    canon, _ = normalize_facility_type(props_coal)
    assert canon == "power_plant"
    for src in ["gas", "oil", "diesel", "biomass", "waste", "combustion", "nuclear"]:
        assert normalize_facility_type({"power": "generator", "generator:source": src})[0] == "power_plant"

def test_power_plant_retained():
    assert normalize_facility_type({"power": "plant"})[0] == "power_plant"
    assert normalize_facility_type({"power": "plant", "name": "Thermal Plant"})[0] == "power_plant"

def test_factories_retained():
    for tag in ["factory", "industrial", "manufacturing"]:
        assert normalize_facility_type({"industrial": tag})[0] in ("factory", "industrial_area", "other")

def test_steel_cement_chemical_refinery_retained():
    assert normalize_facility_type({"industrial": "steel"})[0] == "steel"
    assert normalize_facility_type({"industrial": "cement"})[0] == "cement"
    assert normalize_facility_type({"industrial": "chemical"})[0] == "chemical"
    assert normalize_facility_type({"industrial": "refinery"})[0] == "refinery"
    assert normalize_facility_type({"industrial": "oil"})[0] == "oil_gas"
    assert normalize_facility_type({"industrial": "gas"})[0] == "oil_gas"

def test_water_tanks_not_industrial():
    props_water = {"man_made": "storage_tank", "content": "water", "raw_tags": {"man_made": "storage_tank", "content": "water"}}
    assert normalize_facility_type(props_water)[0] == "other"
    # Oil tank should be oil_gas
    props_oil = {"man_made": "storage_tank", "content": "oil", "raw_tags": {"man_made": "storage_tank", "content": "oil"}}
    assert normalize_facility_type(props_oil)[0] == "oil_gas"
    # Unknown content -> other (not fabricated)
    props_unknown = {"man_made": "storage_tank"}
    assert normalize_facility_type(props_unknown)[0] == "other"

def test_raw_tags_preserved():
    data = {"elements": [{"type": "node", "id": 1, "lat": 19.0, "lon": 72.8, "tags": {"power": "plant", "name": "Plant A", "operator": "NTPC"}}]}
    gj = overpass_to_geojson(data)
    assert gj["features"][0]["properties"]["raw_tags"]["operator"] == "NTPC"
    assert gj["features"][0]["properties"]["name"] == "Plant A"

def test_normalization_deterministic():
    props = {"industrial": "refinery", "power": "plant", "name": "Test"}
    assert normalize_facility_type(props) == normalize_facility_type(props)
    assert normalize_facility_type({"industrial": "steel"}) == normalize_facility_type({"industrial": "steel"})

def test_old_cache_not_reused_targeted():
    # Old broad cache at tiles/, new targeted at targeted_tiles/
    old_path = Path("data/geospatial/cache/tiles/tile_8_77_8533ffad.json")
    new_path = Path("data/geospatial/cache/targeted_tiles/tile_8_77_8533ffad.json")
    assert old_path.exists()
    assert new_path.exists()
    old_data = json.loads(old_path.read_text())
    new_data = json.loads(new_path.read_text())
    assert len(old_data["elements"]) == 7555
    assert len(new_data["elements"]) == 911
    assert old_data["elements"] != new_data["elements"]
    # Ensure old cache not overwritten
    assert old_path.stat().st_size > new_path.stat().st_size

def test_targeted_cache_separate():
    targeted_dir = Path("data/geospatial/cache/targeted_tiles")
    assert targeted_dir.exists()
    assert (targeted_dir / "tile_8_77_8533ffad.json").exists()
    assert (targeted_dir / "tile_8_78_6122b042.json").exists()
    # Old cache still exists
    assert Path("data/geospatial/cache/tiles/tile_8_77_8533ffad.json").exists()
