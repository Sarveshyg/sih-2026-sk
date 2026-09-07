import json
import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Query, HTTPException, Body, Depends, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.alert import Alert

router = APIRouter(prefix="/api/alerts", tags=["Alert Center & Tiered Response"])


class EscalationLog(BaseModel):
    from_tier: int
    to_tier: int
    actor: str
    role: str
    reason: str
    timestamp: str


class AlertResponse(BaseModel):
    id: str
    event_id: str
    facility_name: str
    facility_type: str
    location: str
    region: str
    fire_type: str
    classification: str
    risk_score: int
    severity: str
    confidence: float
    frp: float
    temperature: float
    status: str
    current_tier: int
    previous_tier: Optional[int] = 0
    assigned_agency: str
    created_at: str
    updated_at: str
    escalation_history: List[Dict[str, Any]] = []
    resolution_note: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_tier: Optional[int] = None
    resolved_at: Optional[str] = None
    latitude: Optional[float] = 22.47
    longitude: Optional[float] = 70.06


_initial_canonical_alerts: List[Dict[str, Any]] = [
    {
        "id": "ALT-GJ-001",
        "event_id": "FIRMS_001",
        "facility_name": "Reliance Industries Refinery",
        "facility_type": "Petrochemical Refinery",
        "location": "Jamnagar, Gujarat",
        "region": "Gujarat",
        "fire_type": "Industrial Fire",
        "classification": "Industrial Facility Thermal Alert (fossil gas / liquids)",
        "risk_score": 94,
        "severity": "critical",
        "confidence": 95.2,
        "frp": 124.5,
        "temperature": 341.2,
        "status": "NEW",
        "current_tier": 1,
        "previous_tier": 0,
        "assigned_agency": "Jamnagar District Emergency Response",
        "created_at": "2026-09-08 10:30 UTC",
        "updated_at": "2026-09-08 10:30 UTC",
        "escalation_history": [
            {
                "from_tier": 0,
                "to_tier": 1,
                "actor": "THERMOS AI Engine",
                "role": "Automated Satellite Dispatcher",
                "reason": "VIIRS NRT anomaly detected with high radiative power (124.5 MW) near refinery asset.",
                "timestamp": "2026-09-08 10:30 UTC"
            }
        ]
    },
    {
        "id": "ALT-OD-002",
        "event_id": "FIRMS_014",
        "facility_name": "IOCL Paradip Petrochemical Complex",
        "facility_type": "Petrochemical Yard",
        "location": "Paradip, Odisha",
        "region": "Odisha",
        "fire_type": "Persistent Industrial Thermal Source",
        "classification": "Persistent Industrial Thermal Source (+566% deviation)",
        "risk_score": 88,
        "severity": "critical",
        "confidence": 91.8,
        "frp": 96.8,
        "temperature": 329.7,
        "status": "ACKNOWLEDGED",
        "current_tier": 1,
        "previous_tier": 0,
        "assigned_agency": "Jagatsinghpur District Emergency Cell",
        "created_at": "2026-09-08 09:48 UTC",
        "updated_at": "2026-09-08 10:05 UTC",
        "escalation_history": [
            {
                "from_tier": 0,
                "to_tier": 1,
                "actor": "THERMOS AI Engine",
                "role": "Automated Satellite Dispatcher",
                "reason": "Persistence score 0.84 exceeding baseline threshold.",
                "timestamp": "2026-09-08 09:48 UTC"
            },
            {
                "from_tier": 1,
                "to_tier": 1,
                "actor": "District Duty Officer",
                "role": "Tier 1 Local Response",
                "reason": "Acknowledged alert and verified satellite telemetry.",
                "timestamp": "2026-09-08 10:05 UTC"
            }
        ]
    },
    {
        "id": "ALT-CG-003",
        "event_id": "FIRMS_022",
        "facility_name": "NTPC Korba Thermal Power Station",
        "facility_type": "Thermal Power Plant",
        "location": "Korba, Chhattisgarh",
        "region": "Chhattisgarh",
        "fire_type": "Industrial Fire",
        "classification": "Coal Mine / Power Station Thermal Anomaly",
        "risk_score": 86,
        "severity": "critical",
        "confidence": 88.4,
        "frp": 74.2,
        "temperature": 318.4,
        "status": "ESCALATED",
        "current_tier": 2,
        "previous_tier": 1,
        "assigned_agency": "Chhattisgarh State Disaster Management Authority",
        "created_at": "2026-09-08 08:16 UTC",
        "updated_at": "2026-09-08 09:30 UTC",
        "escalation_history": [
            {
                "from_tier": 0,
                "to_tier": 1,
                "actor": "THERMOS AI Engine",
                "role": "Automated Satellite Dispatcher",
                "reason": "Elevated thermal signatures in coal storage zone.",
                "timestamp": "2026-09-08 08:16 UTC"
            },
            {
                "from_tier": 1,
                "to_tier": 2,
                "actor": "Korba Local Response Team",
                "role": "Tier 1 Local Officer",
                "reason": "Thermal emission expanding towards main transformer unit; local capacity insufficient.",
                "timestamp": "2026-09-08 09:30 UTC"
            }
        ]
    },
    {
        "id": "ALT-MH-004",
        "event_id": "FIRMS_044",
        "facility_name": "Bharat Petroleum Mumbai Refinery",
        "facility_type": "Oil Refinery",
        "location": "Mumbai, Maharashtra",
        "region": "Maharashtra",
        "fire_type": "Industrial Fire",
        "classification": "Refinery Storage Flare Anomaly",
        "risk_score": 91,
        "severity": "critical",
        "confidence": 92.4,
        "frp": 110.4,
        "temperature": 336.1,
        "status": "ESCALATED",
        "current_tier": 3,
        "previous_tier": 2,
        "assigned_agency": "National Disaster Management Authority (NDMA Central)",
        "created_at": "2026-09-08 07:22 UTC",
        "updated_at": "2026-09-08 09:50 UTC",
        "escalation_history": [
            {
                "from_tier": 0,
                "to_tier": 1,
                "actor": "THERMOS AI Engine",
                "role": "Automated Satellite Dispatcher",
                "reason": "Acute thermal hotspot detected in high-density urban corridor.",
                "timestamp": "2026-09-08 07:22 UTC"
            },
            {
                "from_tier": 1,
                "to_tier": 2,
                "actor": "Mumbai Municipal Emergency Cell",
                "role": "Tier 1 Local Officer",
                "reason": "Second alarm sounded; requesting regional backup.",
                "timestamp": "2026-09-08 08:10 UTC"
            },
            {
                "from_tier": 2,
                "to_tier": 3,
                "actor": "Maharashtra SDMA Operations Control",
                "role": "Tier 2 Regional Authority",
                "reason": "Critical infrastructure proximity; requesting national emergency authorization.",
                "timestamp": "2026-09-08 09:50 UTC"
            }
        ]
    },
    {
        "id": "ALT-GJ-005",
        "event_id": "FIRMS_031",
        "facility_name": "Dahej Industrial Estate",
        "facility_type": "LNG Chemical Terminal",
        "location": "Bharuch, Gujarat",
        "region": "Gujarat",
        "fire_type": "Gas Flare",
        "classification": "Controlled Hydrocarbon Flare",
        "risk_score": 62,
        "severity": "high",
        "confidence": 82.6,
        "frp": 51.6,
        "temperature": 307.9,
        "status": "IN_PROGRESS",
        "current_tier": 1,
        "previous_tier": 0,
        "assigned_agency": "Bharuch District Industrial Safety Unit",
        "created_at": "2026-09-08 06:54 UTC",
        "updated_at": "2026-09-08 07:30 UTC",
        "escalation_history": [
            {
                "from_tier": 0,
                "to_tier": 1,
                "actor": "THERMOS AI Engine",
                "role": "Automated Satellite Dispatcher",
                "reason": "VIIRS I4 flare detection.",
                "timestamp": "2026-09-08 06:54 UTC"
            }
        ]
    }
]


def _ensure_seed_alerts(db: Session):
    """Seed canonical alerts into SQLite DB if empty."""
    if db.query(Alert).count() == 0:
        for item in _initial_canonical_alerts:
            db.add(
                Alert(
                    id=item["id"],
                    event_id=item["event_id"],
                    facility_name=item["facility_name"],
                    facility_type=item["facility_type"],
                    location=item["location"],
                    region=item["region"],
                    fire_type=item["fire_type"],
                    classification=item["classification"],
                    risk_score=item["risk_score"],
                    severity=item["severity"],
                    confidence=item["confidence"],
                    frp=item["frp"],
                    temperature=item["temperature"],
                    status=item["status"],
                    current_tier=item["current_tier"],
                    previous_tier=item.get("previous_tier", 0),
                    assigned_agency=item["assigned_agency"],
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                    escalation_history=json.dumps(item.get("escalation_history", [])),
                )
            )
        db.commit()


def _format_alert(a: Alert) -> Dict[str, Any]:
    history = []
    if a.escalation_history:
        try:
            history = json.loads(a.escalation_history)
        except Exception:
            history = []
    facility_coords = {
        "Reliance Industries Refinery": (22.47, 70.06),
        "IOCL Paradip Petrochemical Complex": (20.27, 86.68),
        "NTPC Korba Thermal Power Station": (22.36, 82.75),
        "Bharat Petroleum Mumbai Refinery": (19.01, 72.88),
        "Dahej Industrial Estate": (21.70, 72.99),
    }
    coords = facility_coords.get(a.facility_name, (22.47, 70.06))

    return {
        "id": a.id,
        "event_id": a.event_id,
        "facility_name": a.facility_name,
        "facility_type": a.facility_type,
        "location": a.location,
        "region": a.region,
        "fire_type": a.fire_type,
        "classification": a.classification,
        "risk_score": a.risk_score,
        "severity": a.severity,
        "confidence": a.confidence,
        "frp": a.frp,
        "temperature": a.temperature,
        "status": a.status,
        "current_tier": a.current_tier,
        "previous_tier": a.previous_tier or 0,
        "assigned_agency": a.assigned_agency,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
        "escalation_history": history,
        "resolution_note": a.resolution_note,
        "resolved_by": a.resolved_by,
        "resolved_tier": a.resolved_tier,
        "resolved_at": a.resolved_at,
        "latitude": coords[0],
        "longitude": coords[1],
    }


@router.get("", summary="Get persistent operational alerts list")
def get_alerts(
    tier: Optional[int] = Query(None, description="Filter by agency tier (1, 2, 3)"),
    status: Optional[str] = Query(None, description="Filter by status (NEW, ESCALATED, RESOLVED, etc.)"),
    severity: Optional[str] = Query(None, description="Filter by severity (critical, high, moderate)"),
    region: Optional[str] = Query(None, description="Filter by region"),
    include_resolved: bool = Query(True, description="Whether to include resolved alerts in results"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ensure_seed_alerts(db)

    query = db.query(Alert)

    if not include_resolved and (not status or status.upper() != "RESOLVED"):
        query = query.filter(Alert.status != "RESOLVED")

    if tier:
        # Agency at tier N can see alerts at or escalated up to their tier
        query = query.filter(Alert.current_tier <= tier)

    if status and status.lower() != "all":
        if status.upper() == "UNRESOLVED":
            query = query.filter(Alert.status != "RESOLVED")
        elif status.upper() == "ESCALATED":
            query = query.filter((Alert.status == "ESCALATED") | (Alert.current_tier > 1))
        else:
            query = query.filter(Alert.status == status.upper())

    if severity and severity.lower() != "all":
        query = query.filter(Alert.severity == severity.lower())

    if region and region.lower() not in ["all", "all india"]:
        query = query.filter(Alert.region.ilike(f"%{region}%"))

    alerts_list = [_format_alert(a) for a in query.all()]

    # Summary metrics across all alerts in DB
    all_db = db.query(Alert).all()
    critical_count = len([a for a in all_db if a.severity == "critical" and a.status != "RESOLVED"])
    high_count = len([a for a in all_db if a.severity == "high" and a.status != "RESOLVED"])
    unresolved_count = len([a for a in all_db if a.status != "RESOLVED"])
    resolved_count = len([a for a in all_db if a.status == "RESOLVED"])

    return {
        "total": len(alerts_list),
        "summary": {
            "critical": critical_count,
            "high": high_count,
            "unresolved": unresolved_count,
            "resolved": resolved_count,
        },
        "alerts": alerts_list,
    }


@router.get("/{alert_id}", summary="Get detailed persistent alert information")
def get_alert_detail(alert_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    _ensure_seed_alerts(db)
    alert = db.query(Alert).filter((Alert.id == alert_id) | (Alert.event_id == alert_id)).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _format_alert(alert)


@router.post("/{alert_id}/acknowledge", summary="Acknowledge alert at current tier")
def acknowledge_alert(
    alert_id: str,
    actor: str = Body("District Duty Officer", embed=True),
    role: str = Body("Tier 1 Local Response", embed=True),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ensure_seed_alerts(db)
    alert = db.query(Alert).filter((Alert.id == alert_id) | (Alert.event_id == alert_id)).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "ACKNOWLEDGED"
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    alert.updated_at = now_str

    history = []
    if alert.escalation_history:
        try:
            history = json.loads(alert.escalation_history)
        except Exception:
            history = []

    history.append({
        "from_tier": alert.current_tier,
        "to_tier": alert.current_tier,
        "actor": actor,
        "role": role,
        "reason": f"Alert acknowledged by {actor} ({role}).",
        "timestamp": now_str,
    })
    alert.escalation_history = json.dumps(history)
    db.commit()

    return {"status": "success", "alert": _format_alert(alert)}


@router.post("/{alert_id}/escalate", summary="Escalate alert along Tier 1 -> Tier 2 -> Tier 3 hierarchy")
def escalate_alert(
    alert_id: str,
    reason: str = Body(..., embed=True),
    actor: str = Body("Operational Officer", embed=True),
    role: str = Body("Local Response", embed=True),
    caller_tier: Optional[int] = Body(None, embed=True),
    x_user_tier: Optional[int] = Header(None, alias="X-User-Tier"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ensure_seed_alerts(db)
    alert = db.query(Alert).filter((Alert.id == alert_id) | (Alert.event_id == alert_id)).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    current_tier = alert.current_tier

    # Strict Tier Validation
    if current_tier >= 3:
        raise HTTPException(status_code=400, detail="Alert is already at top Tier 3 Central Government authority; cannot escalate higher.")

    # Validate caller tier if provided
    auth_tier = caller_tier or x_user_tier
    if auth_tier is not None and auth_tier != current_tier:
        # A tier 1 user cannot escalate a tier 2 alert, etc.
        raise HTTPException(status_code=403, detail=f"Permission denied: Caller at Tier {auth_tier} cannot escalate alert currently at Tier {current_tier}.")

    next_tier = current_tier + 1
    next_agency = (
        "State Disaster Management Authority (SDMA)"
        if next_tier == 2
        else "National Disaster Management Authority (NDMA Central)"
    )

    alert.previous_tier = current_tier
    alert.current_tier = next_tier
    alert.status = "ESCALATED"
    alert.assigned_agency = next_agency
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    alert.updated_at = now_str

    history = []
    if alert.escalation_history:
        try:
            history = json.loads(alert.escalation_history)
        except Exception:
            history = []

    history.append({
        "from_tier": current_tier,
        "to_tier": next_tier,
        "actor": actor,
        "role": role,
        "reason": reason or f"Escalated from Tier {current_tier} to Tier {next_tier}",
        "timestamp": now_str,
    })
    alert.escalation_history = json.dumps(history)
    db.commit()

    return {"status": "success", "alert": _format_alert(alert)}


@router.post("/{alert_id}/resolve", summary="Resolve alert with operational note")
def resolve_alert(
    alert_id: str,
    note: str = Body(..., embed=True),
    actor: str = Body("Emergency Authority", embed=True),
    role: str = Body("Operational Authority", embed=True),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ensure_seed_alerts(db)
    alert = db.query(Alert).filter((Alert.id == alert_id) | (Alert.event_id == alert_id)).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    alert.status = "RESOLVED"
    alert.updated_at = now_str
    alert.resolution_note = note or "Verified non-hazardous or contained by emergency response unit."
    alert.resolved_by = actor
    alert.resolved_tier = alert.current_tier
    alert.resolved_at = now_str

    history = []
    if alert.escalation_history:
        try:
            history = json.loads(alert.escalation_history)
        except Exception:
            history = []

    history.append({
        "from_tier": alert.current_tier,
        "to_tier": alert.current_tier,
        "actor": actor,
        "role": role,
        "reason": f"Incident marked RESOLVED: {alert.resolution_note}",
        "timestamp": now_str,
    })
    alert.escalation_history = json.dumps(history)
    db.commit()

    return {"status": "success", "alert": _format_alert(alert)}


@router.post("/reset", summary="Reset alerts to initial canonical demo dataset in SQLite")
def reset_alerts(db: Session = Depends(get_db)) -> Dict[str, Any]:
    db.query(Alert).delete()
    db.commit()
    _ensure_seed_alerts(db)
    return {"status": "reset_complete", "count": db.query(Alert).count()}
