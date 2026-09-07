from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

router = APIRouter(prefix="/api/simulation", tags=["Simulation & Hackathon Scenarios"])

class ScenarioInfo(BaseModel):
    id: str
    title: str
    fire_type: str
    description: str
    expected_classification: str
    expected_risk: str
    key_features: List[str]
    is_main_demo: bool = False

SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "scenario-1",
        "title": "Industrial Fire (Refinery Acute Thermal Anomaly)",
        "fire_type": "Industrial Fire",
        "description": "High radiative power emission (124.5 MW) detected adjacent to petrochemical refining unit.",
        "expected_classification": "Industrial Facility Thermal Alert (fossil gas/liquids)",
        "expected_risk": "CRITICAL (Risk 94/100)",
        "key_features": [
            "High Radiative Power (124.5 MW)",
            "VIIRS I4 Temp: 341.2 K",
            "Distance to Refinery: 0.08 km",
            "Abnormal baseline (+600% deviation)"
        ],
        "is_main_demo": False
    },
    {
        "id": "scenario-2",
        "title": "Persistent Industrial Thermal Source",
        "fire_type": "Persistent Industrial Thermal Source",
        "description": "Recurring heat signatures over 7-day observation window near petrochemical complex.",
        "expected_classification": "Persistent Industrial Thermal Source",
        "expected_risk": "CRITICAL (Risk 88/100)",
        "key_features": [
            "Spatial Persistence Score: 0.84",
            "Detections in 7 Days: 18",
            "Distance to Plant: 0.45 km",
            "Abnormal activity (+566% deviation)"
        ],
        "is_main_demo": False
    },
    {
        "id": "scenario-3",
        "title": "Gas Flare (Controlled Upstream Flaring)",
        "fire_type": "Gas Flare",
        "description": "Thermal anomaly associated with active offshore gas field flaring stack.",
        "expected_classification": "Gas Flare / Upstream Thermal Source",
        "expected_risk": "HIGH (Risk 62/100)",
        "key_features": [
            "Nearest Flare Field: Dahej Field",
            "Thermal Contrast (ΔT): 22.4 K",
            "Demonstrates non-fire industrial flaring differentiation"
        ],
        "is_main_demo": False
    },
    {
        "id": "scenario-4",
        "title": "Wildfire (Forest / Vegetation Fire)",
        "fire_type": "Wildfire/Natural Fire",
        "description": "High FRP thermal cluster spreading through dense forest canopy with zero industrial infrastructure nearby.",
        "expected_classification": "Active Wildfire / Forest Fire",
        "expected_risk": "HIGH (Risk 78/100)",
        "key_features": [
            "Distance to Industrial: > 15.0 km",
            "High Vegetation Context",
            "Rapid Spatial Expansion"
        ],
        "is_main_demo": False
    },
    {
        "id": "scenario-5",
        "title": "Agricultural Crop Residue Fire",
        "fire_type": "Agricultural Fire",
        "description": "Localized seasonal thermal activity on agricultural farmland.",
        "expected_classification": "Agricultural Crop Residue Thermal Activity",
        "expected_risk": "MODERATE (Risk 45/100)",
        "key_features": [
            "Localized low-intensity FRP (14.2 MW)",
            "Farmland land-use context",
            "No infrastructure threat"
        ],
        "is_main_demo": False
    },
    {
        "id": "scenario-6",
        "title": "Critical Industrial Escalation (SIH Main Presentation)",
        "fire_type": "Industrial Fire",
        "description": "Full end-to-end operational emergency lifecycle: Satellite detection → AI classification → Tier 1 local response → Tier 2 escalation → Tier 3 Central Government emergency resolution.",
        "expected_classification": "Industrial Fire (Critical Asset Threat)",
        "expected_risk": "CRITICAL (Risk 96/100)",
        "key_features": [
            "Demonstrates 3-Tier Escalation Workflow",
            "Live Audit Trail Logging",
            "Complete End-to-End Decision Support Lifecycle"
        ],
        "is_main_demo": True
    }
]

# Active simulation state
_current_sim = {
    "active": False,
    "scenario_id": "scenario-6",
    "step": 0,
    "max_steps": 10,
    "timeline": [
        {"step": 0, "title": "T+00: VIIRS Satellite Hotspot Detection", "desc": "VIIRS NRT satellite detects high-temperature radiative anomaly."},
        {"step": 1, "title": "T+05: Geospatial Spatial Enrichment", "desc": "BallTree haversine distance identifies Reliance Industries Refinery at 0.08 km."},
        {"step": 2, "title": "T+10: AI Classification & Risk Engine", "desc": "fused-xgboost-v1 classifies Industrial Fire with 95.2% confidence and 96/100 Critical Risk."},
        {"step": 3, "title": "T+15: Critical Alert Created", "desc": "Alert ALT-SIM-999 generated and routed to Jamnagar Local Response Cell."},
        {"step": 4, "title": "T+20: Tier 1 Local Acknowledgement", "desc": "Jamnagar Duty Officer acknowledges alert and verifies telemetry."},
        {"step": 5, "title": "T+30: Tier 1 Escalates to Tier 2", "desc": "Thermal power increases; local capacity exceeded. Escalated to Gujarat SDMA (Tier 2)."},
        {"step": 6, "title": "T+40: Tier 2 Escalates to Tier 3", "desc": "Refinery storage tank at risk. Escalated to NDMA Central (Tier 3)."},
        {"step": 7, "title": "T+45: Central Emergency Command Intervention", "desc": "NDMA Central authorizes national fire suppressant aircraft dispatch."},
        {"step": 8, "title": "T+50: Incident Contained & Resolved", "desc": "Thermal emission drops below baseline threshold. Marked RESOLVED by Tier 3 Authority."},
        {"step": 9, "title": "T+60: Audit Trail & Historical Archival", "desc": "Complete incident timeline preserved in central historical audit record."}
    ]
}

@router.get("/scenarios", summary="Get list of curated hackathon scenarios")
def get_scenarios() -> Dict[str, Any]:
    return {"scenarios": SCENARIOS}

@router.get("/state", summary="Get active simulation state")
def get_sim_state() -> Dict[str, Any]:
    return _current_sim

@router.post("/start", summary="Start simulation scenario")
def start_simulation(scenario_id: str = Body(..., embed=True)) -> Dict[str, Any]:
    scenario = next((s for s in SCENARIOS if s["id"] == scenario_id), SCENARIOS[-1])
    _current_sim["active"] = True
    _current_sim["scenario_id"] = scenario["id"]
    _current_sim["step"] = 0
    return {"status": "started", "scenario": scenario, "state": _current_sim}

@router.post("/step", summary="Advance simulation by 1 step")
def advance_step() -> Dict[str, Any]:
    if not _current_sim["active"]:
        _current_sim["active"] = True
    if _current_sim["step"] < _current_sim["max_steps"] - 1:
        _current_sim["step"] += 1
    return {"status": "advanced", "current_step": _current_sim["step"], "step_data": _current_sim["timeline"][_current_sim["step"]]}

@router.post("/reset", summary="Reset simulation state")
def reset_simulation() -> Dict[str, Any]:
    _current_sim["active"] = False
    _current_sim["step"] = 0
    return {"status": "reset", "state": _current_sim}
