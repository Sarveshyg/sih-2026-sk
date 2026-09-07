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
