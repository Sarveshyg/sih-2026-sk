import json
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.thermal_event import ThermalEvent
from app.models.facility import Facility
from app.models.prediction import Prediction
from app.schemas.thermal_event import ThermalEventSummary, EventIntelligenceResponse


class EventService:

    @staticmethod
    def get_events(
        db: Session,
        classification: Optional[str] = None,
        risk_level: Optional[str] = None,
        facility_id: Optional[str] = None,
    ) -> List[ThermalEventSummary]:
        query = db.query(ThermalEvent)

        if facility_id:
            query = query.filter(ThermalEvent.facility_id == facility_id)

        events = query.all()
        summaries: List[ThermalEventSummary] = []

        for event in events:
            pred = db.query(Prediction).filter(Prediction.event_id == event.id).first()
            fac = db.query(Facility).filter(Facility.id == event.facility_id).first() if event.facility_id else None

            event_classification = pred.classification if pred else "unknown"
            event_confidence = pred.confidence if pred else 0.0
            event_risk_score = pred.risk_score if pred else 0.0
            event_risk_level = pred.risk_level if pred else "low"

            # Apply filters if requested
            if classification and event_classification.lower() != classification.lower():
                continue
            if risk_level and event_risk_level.lower() != risk_level.lower():
                continue

            summaries.append(
                ThermalEventSummary(
                    id=event.id,
                    latitude=event.latitude,
                    longitude=event.longitude,
                    classification=event_classification,
                    confidence=event_confidence,
                    risk_score=event_risk_score,
                    risk_level=event_risk_level,
                    frp=event.frp,
                    brightness_temperature=event.brightness_temperature,
                    timestamp=event.timestamp,
                    satellite=event.satellite,
                    facility_id=event.facility_id,
                    facility_name=fac.name if fac else event.nearest_facility_name,
                    facility_type=fac.type if fac else event.facility_type,
                )
            )

        return summaries

    @staticmethod
    def get_event_detail(db: Session, event_id: str) -> Optional[EventIntelligenceResponse]:
        event = db.query(ThermalEvent).filter(ThermalEvent.id == event_id).first()
        if not event:
            return None

        pred = db.query(Prediction).filter(Prediction.event_id == event.id).first()
        fac = db.query(Facility).filter(Facility.id == event.facility_id).first() if event.facility_id else None

        explanation_list = []
        if pred and pred.explanation:
            try:
                explanation_list = json.loads(pred.explanation)
            except Exception:
                explanation_list = [pred.explanation]

        event_data = {
            "id": event.id,
            "latitude": event.latitude,
            "longitude": event.longitude,
            "frp": event.frp,
            "brightness_temperature": event.brightness_temperature,
            "confidence": event.confidence,
            "timestamp": event.timestamp,
            "satellite": event.satellite,
        }

        prediction_data = {
            "classification": pred.classification if pred else "unknown",
            "confidence": pred.confidence if pred else 0.0,
            "risk_score": pred.risk_score if pred else 0.0,
            "risk_level": pred.risk_level if pred else "low",
            "explanation": explanation_list,
        }

        facility_data = {
            "id": fac.id if fac else event.facility_id,
            "name": fac.name if fac else event.nearest_facility_name,
            "type": fac.type if fac else event.facility_type,
            "distance_to_facility_m": event.distance_to_facility_m,
        }

        temporal_data = {
            "detections_24h": event.detections_24h or 1,
            "detections_7d": event.detections_7d or 1,
            "persistence_score": event.persistence_score or 0.0,
        }

        return EventIntelligenceResponse(
            event=event_data,
            prediction=prediction_data,
            facility=facility_data,
            temporal=temporal_data,
        )
