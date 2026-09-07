"""
Tests for AI Core pipeline — covering Step 11 synthetic scenarios.

Run: pytest ml/tests -v
"""

import pytest
from ml.inference.pipeline import InferencePipeline
from ml.schemas import ClassificationLabel

pipeline = InferencePipeline()

VALID_CLASSES = {e.value for e in ClassificationLabel}
# Canonical set expected after normalisation
CANONICAL_CLASSES = {
    "industrial_fire",
    "persistent_industrial_thermal_source",
    "gas_flare",
    "wildfire",
    "agricultural_fire",
    "unknown",
}


def base_event(**overrides):
    """Helper: minimal valid event with sensible defaults, then overrides."""
    evt = {
        "id": "TEST_001",
        "latitude": 19.076,
        "longitude": 72.877,
        "frp": 50.0,
        "brightness_temperature": 340.0,
        "confidence": 80,
        "timestamp": "2026-09-06T10:30:00Z",
        "satellite": "VIIRS",
    }
    evt.update(overrides)
    return evt


def test_scenario_A_industrial_fire():
    """Scenario A — High FRP + nearby refinery + persistent activity => industrial_fire, Tier 1."""
    evt = base_event(
        id="FIRMS_A",
        frp=184.0,
        brightness_temperature=412,
        confidence=94,
        facility_type="refinery",
        distance_to_facility_m=76.4,
        persistence_score=0.82,
        detections_24h=5,
        detections_7d=18,
        detections_30d=40,
        ndvi=0.12,
        ndbi=0.68,
        facility_baseline=2,
        current_activity=14,
        hotspot_cluster_size=1,
        inside_industrial_area=True,
    )
    result = pipeline.predict(evt)
    assert result["classification"] == "industrial_fire"
    assert 0 <= result["confidence"] <= 1
    assert result["confidence"] > 0.6
    assert result["risk_score"] >= 75, f"Expected critical/high risk, got {result['risk_score']}"
    assert result["risk_level"] == "CRITICAL"
    assert result["triage_required"] is True
    assert result["recommended_tier"] == 1
    assert len(result["explanation"]) > 0
    assert result["event_id"] == "FIRMS_A"


def test_scenario_B_wildfire():
    """Scenario B — Forest proximity + high NDVI + clustered hotspots + no industrial."""
    evt = base_event(
        id="FIRMS_B",
        frp=85.0,
        brightness_temperature=355,
        confidence=88,
        distance_to_facility_m=15000,
        distance_to_forest_m=300,
        ndvi=0.65,
        ndbi=-0.1,
        hotspot_cluster_size=7,
        persistence_score=0.25,
        detections_7d=4,
        facility_type=None,
        distance_to_agriculture_m=5000,
    )
    result = pipeline.predict(evt)
    assert result["classification"] == "wildfire"
    assert 0 <= result["confidence"] <= 1
    assert 0 <= result["risk_score"] <= 100
    assert result["risk_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
    assert len(result["explanation"]) > 0


def test_scenario_C_agricultural_fire():
    """Scenario C — Agri land + temporary activity + low industrial proximity."""
    evt = base_event(
        id="FIRMS_C",
        frp=18.0,
        brightness_temperature=315,
        confidence=65,
        distance_to_facility_m=8000,
        distance_to_agriculture_m=200,
        distance_to_forest_m=6000,
        ndvi=0.45,
        ndbi=0.05,
        persistence_score=0.15,
        detections_7d=2,
        detections_24h=1,
        hotspot_cluster_size=1,
    )
    result = pipeline.predict(evt)
    assert result["classification"] == "agricultural_fire"
    assert 0 <= result["confidence"] <= 1
    assert len(result["explanation"]) > 0


def test_scenario_D_persistent_industrial_source():
    """Scenario D — Repeated detections over multiple days => persistent."""
    evt = base_event(
        id="FIRMS_D",
        frp=35.0,
        brightness_temperature=335,
        confidence=82,
        facility_type="industrial",
        distance_to_facility_m=120,
        persistence_score=0.88,
        detections_24h=4,
        detections_7d=22,
        detections_30d=55,
        ndvi=0.18,
        ndbi=0.55,
        hotspot_cluster_size=2,
        facility_baseline=3,
        current_activity=4,  # not anomalous but persistent
    )
    result = pipeline.predict(evt)
    assert result["classification"] in ("persistent_industrial_thermal_source", "persistent_industrial_source")
    assert result["confidence"] > 0.5
    assert len(result["explanation"]) > 0
    # persistent without anomaly should be MODERATE/HIGH but not necessarily CRITICAL
    assert 0 <= result["risk_score"] <= 100


def test_scenario_E_gas_flare():
    """Scenario E — Persistent thermal source at oil/gas facility => gas_flare."""
    evt = base_event(
        id="FIRMS_E",
        frp=45.0,
        brightness_temperature=360,
        confidence=85,
        facility_type="gas",
        distance_to_facility_m=45,
        persistence_score=0.92,
        detections_7d=28,
        detections_30d=90,
        ndvi=0.10,
        ndbi=0.60,
        hotspot_cluster_size=1,
        inside_industrial_area=True,
    )
    result = pipeline.predict(evt)
    assert result["classification"] == "gas_flare"
    assert 0 <= result["confidence"] <= 1
    assert len(result["explanation"]) > 0


def test_scenario_F_unknown():
    """Scenario F — Insufficient contextual information => unknown."""
    evt = base_event(
        id="FIRMS_F",
        frp=12.0,
        brightness_temperature=305,
        confidence=40,
        # no contextual fields at all
    )
    result = pipeline.predict(evt)
    assert result["classification"] == "unknown"
    assert 0 <= result["confidence"] <= 1
    # triage should NOT be required for unknown low risk
    assert result["triage_required"] is False
    assert result["risk_score"] < 50
    assert len(result["explanation"]) > 0


def test_missing_optional_features_do_not_crash():
    """Missing optional features should not crash pipeline."""
    minimal = base_event(id="MIN_001")
    result = pipeline.predict(minimal)
    assert result["classification"] in CANONICAL_CLASSES or result["classification"] == "unknown"
    assert 0 <= result["confidence"] <= 1
    assert 0 <= result["risk_score"] <= 100
    assert result["risk_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
    assert "explanation" in result and len(result["explanation"]) > 0
    assert "triage_required" in result
    # recommended_tier may be None or int
    assert result["recommended_tier"] in (None, 1)


def test_valid_class_and_ranges():
    """Generic contract validation."""
    for evt in [
        base_event(distance_to_facility_m=100, facility_type="refinery", frp=150, persistence_score=0.9),
        base_event(distance_to_forest_m=200, ndvi=0.7, hotspot_cluster_size=6),
    ]:
        r = pipeline.predict(evt)
        assert r["classification"] in CANONICAL_CLASSES
        assert 0.0 <= r["confidence"] <= 1.0
        assert 0 <= r["risk_score"] <= 100
        assert r["risk_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
        assert isinstance(r["explanation"], list) and len(r["explanation"]) > 0
        assert isinstance(r["triage_required"], bool)


def test_triage_thresholds():
    """Prototype thresholds: >=75 Tier1, 50-74 monitoring, <50 store."""
    # High risk event should trigger triage
    high = base_event(
        id="HIGH_RISK",
        frp=200,
        brightness_temperature=400,
        confidence=95,
        facility_type="refinery",
        distance_to_facility_m=50,
        persistence_score=0.9,
        facility_baseline=1,
        current_activity=12,
        ndvi=0.1,
        ndbi=0.7,
        inside_industrial_area=True,
    )
    r_high = pipeline.predict(high)
    assert r_high["risk_score"] >= 75
    assert r_high["triage_required"] is True
    assert r_high["recommended_tier"] == 1

    low = base_event(id="LOW_RISK", frp=5, brightness_temperature=305, confidence=30)
    r_low = pipeline.predict(low)
    assert r_low["risk_score"] < 50
    assert r_low["triage_required"] is False
    assert r_low["recommended_tier"] is None


def test_anomaly_calculation():
    """Facility anomaly should strongly increase risk evidence."""
    base = base_event(
        id="ANO_BASE",
        frp=60,
        brightness_temperature=340,
        confidence=80,
        facility_type="refinery",
        distance_to_facility_m=200,
        persistence_score=0.6,
        facility_baseline=2,
        current_activity=14,  # 6x increase
        ndvi=0.2,
        ndbi=0.5,
    )
    r = pipeline.predict(base)
    # anomaly = (14-2)/2 = 6
    assert r["anomaly_ratio"] == 7.0
    # Risk should be boosted by anomaly
    assert r["risk_score"] >= 60
    # Explanation should mention baseline
    assert any("baseline" in ex.lower() for ex in r["explanation"])


def test_explainability_flag_distance_alias():
    """Distance aliases should be resolved without crash."""
    evt = base_event(
        id="ALIAS",
        distance_to_industry=100,  # alias field
        facility_type="chemical",
        frp=70,
        persistence_score=0.5,
    )
    r = pipeline.predict(evt)
    assert r["classification"] in CANONICAL_CLASSES
    assert len(r["explanation"]) > 0
