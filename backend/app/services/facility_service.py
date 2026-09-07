import json
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.facility import Facility
from app.models.thermal_event import ThermalEvent
from app.models.prediction import Prediction
from app.schemas.facility import FacilityResponse, FacilityDetailResponse


class FacilityService:

    @staticmethod
    def get_all_facilities(db: Session) -> List[FacilityResponse]:
        facilities = db.query(Facility).all()
        return [FacilityResponse.model_validate(fac) for fac in facilities]


    @staticmethod
    def get_facility_detail(db: Session, facility_id: str) -> Optional[FacilityDetailResponse]:
        facility = db.query(Facility).filter(Facility.id == facility_id).first()
        if not facility:
            return None

        # Associated events
        events = db.query(ThermalEvent).filter(ThermalEvent.facility_id == facility.id).all()
        associated_events = []
        active_predictions = []

        total_detections = len(events)
        critical_count = 0

        for ev in events:
            pred = db.query(Prediction).filter(Prediction.event_id == ev.id).first()

            ev_dict = {
                "id": ev.id,
                "latitude": ev.latitude,
                "longitude": ev.longitude,
                "frp": ev.frp,
                "brightness_temperature": ev.brightness_temperature,
                "timestamp": ev.timestamp,
                "distance_to_facility_m": ev.distance_to_facility_m,
            }
            associated_events.append(ev_dict)

            if pred:
                if pred.risk_level == "critical":
                    critical_count += 1
                active_predictions.append({
                    "event_id": ev.id,
                    "classification": pred.classification,
                    "confidence": pred.confidence,
                    "risk_score": pred.risk_score,
                    "risk_level": pred.risk_level,
                })

        baseline_daily_avg = 1.5
        recent_24h_detections = sum((ev.detections_24h or 1) for ev in events) if events else 0
        abnormal_status = "abnormal" if recent_24h_detections > (baseline_daily_avg * 2) or critical_count > 0 else "normal"
        deviation_pct = round(((recent_24h_detections - baseline_daily_avg) / baseline_daily_avg) * 100, 1) if recent_24h_detections > 0 else 0.0

        geometry_obj = facility.geometry
        if facility.geometry:
            try:
                geometry_obj = json.loads(facility.geometry)
            except Exception:
                geometry_obj = facility.geometry

        return FacilityDetailResponse(
            id=facility.id,
            name=facility.name,
            type=facility.type,
            latitude=facility.latitude,
            longitude=facility.longitude,
            geometry=geometry_obj,
            historical_activity={
                "total_detections": total_detections,
                "baseline_daily_avg": baseline_daily_avg,
                "recent_24h_detections": recent_24h_detections,
            },
            associated_events=associated_events,
            active_predictions=active_predictions,
            abnormality_info={
                "abnormality_status": abnormal_status,
                "deviation_percentage": deviation_pct,
                "critical_incidents": critical_count,
            },
        )
