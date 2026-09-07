import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure backend root directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_events():
    response = client.get("/api/events")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    assert len(events) > 0
    first_event = events[0]
    assert "id" in first_event
    assert "latitude" in first_event
    assert "longitude" in first_event
    assert "classification" in first_event
    assert "risk_level" in first_event


def test_get_event_detail_success():
    response = client.get("/api/events/FIRMS_001")
    assert response.status_code == 200
    data = response.json()
    assert "event" in data
    assert "prediction" in data
    assert "facility" in data
    assert "temporal" in data
    assert data["event"]["id"] == "FIRMS_001"
    assert data["prediction"]["classification"] == "industrial_fire"


def test_get_event_detail_not_found():
    response = client.get("/api/events/NON_EXISTENT_999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_facilities():
    response = client.get("/api/facilities")
    assert response.status_code == 200
    facilities = response.json()
    assert isinstance(facilities, list)
    assert len(facilities) > 0
    first_facility = facilities[0]
    assert "id" in first_facility
    assert "name" in first_facility
    assert "type" in first_facility


def test_get_facility_detail_success():
    response = client.get("/api/facilities/FAC_001")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "FAC_001"
    assert "historical_activity" in data
    assert "abnormality_info" in data


def test_get_facility_detail_not_found():
    response = client.get("/api/facilities/NON_EXISTENT_999")
    assert response.status_code == 404


def test_get_analytics():
    response = client.get("/api/analytics")
    assert response.status_code == 200
    data = response.json()
    assert "total_events" in data
    assert "industrial_events" in data
    assert "critical_events" in data
    assert "persistent_sources" in data
    assert data["total_events"] > 0


def test_predict_event_success():
    response = client.post("/api/predict", json={"event_id": "FIRMS_001"})
    assert response.status_code == 200
    data = response.json()
    assert data["classification"] in [
        "industrial_fire",
        "persistent_industrial_source",
        "gas_flare",
        "wildfire",
        "agricultural_fire",
        "unknown",
    ]
    assert 0.0 <= data["confidence"] <= 1.0
    assert 0.0 <= data["risk_score"] <= 100.0
    assert data["risk_level"] in ["low", "moderate", "high", "critical"]
    assert isinstance(data["explanation"], list)


def test_predict_event_not_found():
    response = client.post("/api/predict", json={"event_id": "NON_EXISTENT_999"})
    assert response.status_code == 404


def test_firms_status_and_pipeline_monitor():
    res_status = client.get("/api/firms/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["source"] == "NASA FIRMS"
    assert status_data["raw_detections_fetched"] >= 2000
    assert status_data["priority_anomalies"] > 0
    assert "last_fetch" in status_data
    assert "satellite_sources" in status_data

    res_pipe = client.get("/api/firms/pipeline-monitor")
    assert res_pipe.status_code == 200
    pipe_data = res_pipe.json()
    assert len(pipe_data["stages"]) == 7
    assert pipe_data["stages"][0]["id"] == "fetch"
    assert pipe_data["stages"][-1]["id"] == "alert"


def test_auth_me_role_resolution():
    res_t1 = client.get("/api/me", headers={"X-User-Role": "tier_1"})
    assert res_t1.status_code == 200
    assert res_t1.json()["tier"] == 1

    res_t2 = client.get("/api/me", headers={"X-User-Role": "tier_2"})
    assert res_t2.status_code == 200
    assert res_t2.json()["tier"] == 2

    res_t3 = client.get("/api/me", headers={"X-User-Role": "tier_3"})
    assert res_t3.status_code == 200
    assert res_t3.json()["tier"] == 3


def test_alert_persistent_escalation_lifecycle():
    # 1. Reset alerts to clean seed
    client.post("/api/alerts/reset")

    # 2. Check initial alert ALT-GJ-001 (starts at tier 1)
    res = client.get("/api/alerts/ALT-GJ-001")
    assert res.status_code == 200
    alert = res.json()
    assert alert["current_tier"] == 1
    assert alert["status"] == "NEW"

    # 3. Tier 1 escalates to Tier 2 (RED)
    esc_res = client.post(
        "/api/alerts/ALT-GJ-001/escalate",
        json={"reason": "Local fire suppression capacity exceeded near refinery zone.", "actor": "Jamnagar Duty Officer", "role": "Tier 1 Local Officer", "caller_tier": 1},
    )
    assert esc_res.status_code == 200
    alert = esc_res.json()["alert"]
    assert alert["current_tier"] == 2
    assert alert["previous_tier"] == 1
    assert alert["status"] == "ESCALATED"
    assert "State Disaster Management" in alert["assigned_agency"]

    # 4. Caller at Tier 1 cannot escalate a Tier 2 alert
    err_res = client.post(
        "/api/alerts/ALT-GJ-001/escalate",
        json={"reason": "Unauthorized skip", "actor": "Jamnagar Officer", "role": "Tier 1", "caller_tier": 1},
    )
    assert err_res.status_code == 403

    # 5. Tier 2 escalates to Tier 3 (RED)
    esc2_res = client.post(
        "/api/alerts/ALT-GJ-001/escalate",
        json={"reason": "Hydrocarbon storage tank proximity; requesting national airborne containment.", "actor": "GSDMA Controller", "role": "Tier 2 SDMA", "caller_tier": 2},
    )
    assert esc2_res.status_code == 200
    alert = esc2_res.json()["alert"]
    assert alert["current_tier"] == 3
    assert alert["previous_tier"] == 2
    assert "National Disaster Management" in alert["assigned_agency"]

    # 6. Cannot escalate past Tier 3
    max_res = client.post(
        "/api/alerts/ALT-GJ-001/escalate",
        json={"reason": "Beyond Tier 3", "actor": "NDMA Director", "role": "Tier 3", "caller_tier": 3},
    )
    assert max_res.status_code == 400

    # 7. Tier 3 resolves the alert (GREEN)
    resolve_res = client.post(
        "/api/alerts/ALT-GJ-001/resolve",
        json={"note": "National containment deployed. Thermal signatures contained below threshold.", "actor": "NDMA Director General", "role": "Tier 3 Central Command"},
    )
    assert resolve_res.status_code == 200
    resolved_alert = resolve_res.json()["alert"]
    assert resolved_alert["status"] == "RESOLVED"
    assert resolved_alert["resolved_tier"] == 3
    assert "National containment deployed" in resolved_alert["resolution_note"]

    # 8. Verify it disappears from unresolved queue
    unresolved_res = client.get("/api/alerts?include_resolved=false")
    unresolved_ids = [a["id"] for a in unresolved_res.json()["alerts"]]
    assert "ALT-GJ-001" not in unresolved_ids

    # 9. Verify it persists in historical audit log
    all_res = client.get("/api/alerts?include_resolved=true")
    all_alerts = {a["id"]: a for a in all_res.json()["alerts"]}
    assert "ALT-GJ-001" in all_alerts
    assert len(all_alerts["ALT-GJ-001"]["escalation_history"]) >= 3


def test_ml_inference_metadata_and_latency():
    response = client.post("/api/predict", json={"event_id": "FIRMS_001"})
    assert response.status_code == 200
    data = response.json()
    assert "fused-xgboost" in data["model_name"]
    assert data["model_version"] == "1.0.0"
    assert data["inference_mode"] in ["LIVE ML INFERENCE", "DEMO FALLBACK"]
    assert data["latency_ms"] > 0
    assert "input_features" in data
    assert "frp" in data["input_features"]
    assert "brightness_temperature" in data["input_features"]
    assert "distance_to_plant_km" in data["input_features"]
