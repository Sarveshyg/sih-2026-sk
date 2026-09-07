import json
import os
import sys
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.thermal_event import ThermalEvent
from app.models.prediction import Prediction
from app.schemas.prediction import PredictionResponse

# Ensure root workspace is on python path for importing `ml`
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from ml.predict import predict as ml_predict
    HAS_ML_MODULE = True
except Exception as e:
    print(f"[THERMOS] ML pipeline import warning: {e}")
    HAS_ML_MODULE = False


class PredictionService:

    @staticmethod
    def predict(db: Session, event_id: str) -> Optional[PredictionResponse]:
        # Check if prediction already exists in DB
        existing = db.query(Prediction).filter(Prediction.event_id == event_id).first()
        if existing:
            explanation_list = []
            if existing.explanation:
                try:
                    explanation_list = json.loads(existing.explanation)
                except Exception:
                    explanation_list = [existing.explanation]
            return PredictionResponse(
                event_id=existing.event_id,
                classification=existing.classification,
                confidence=existing.confidence,
                risk_score=existing.risk_score,
                risk_level=existing.risk_level.lower(),
                explanation=explanation_list,
            )

        # Check if thermal event exists to generate prediction
        event = db.query(ThermalEvent).filter(ThermalEvent.id == event_id).first()
        if not event:
            return None

        # Build dictionary for prediction
        event_dict = {
            "id": event.id,
            "latitude": event.latitude,
            "longitude": event.longitude,
            "frp": event.frp,
            "brightness_temperature": event.brightness_temperature,
            "confidence": event.confidence,
            "timestamp": event.timestamp,
            "satellite": event.satellite,
            "nearest_facility_id": event.facility_id,
            "nearest_facility_name": event.nearest_facility_name,
            "facility_type": event.facility_type,
            "distance_to_facility_m": event.distance_to_facility_m,
            "persistence_score": event.persistence_score,
            "detections_24h": event.detections_24h,
            "detections_7d": event.detections_7d,
            "ndvi": event.ndvi,
            "ndbi": event.ndbi,
        }

        classification = "unknown"
        confidence = 0.5
        risk_score = 20.0
        risk_level = "low"
        explanation = []

        if HAS_ML_MODULE:
            try:
                ml_res = ml_predict(event_dict)
                classification = ml_res.get("classification", "unknown")
                confidence = float(ml_res.get("confidence", 0.5))
                risk_score = float(ml_res.get("risk_score", 20.0))
                risk_level = str(ml_res.get("risk_level", "low")).lower()
                explanation = ml_res.get("explanation", [])
            except Exception as ml_err:
                print(f"[THERMOS] ML inference fallback triggered: {ml_err}")
                classification, confidence, risk_score, risk_level, explanation = (
                    PredictionService._run_inference_rules(event)
                )
        else:
            classification, confidence, risk_score, risk_level, explanation = (
                PredictionService._run_inference_rules(event)
            )

        # Store prediction in DB for future lookup
        new_prediction = Prediction(
            event_id=event.id,
            classification=classification,
            confidence=confidence,
            risk_score=risk_score,
            risk_level=risk_level.lower(),
            explanation=json.dumps(explanation),
        )
        db.add(new_prediction)
        db.commit()

        return PredictionResponse(
            event_id=event.id,
            classification=classification,
            confidence=confidence,
            risk_score=risk_score,
            risk_level=risk_level.lower(),
            explanation=explanation,
        )

    @staticmethod
    def _run_inference_rules(event: ThermalEvent):
        """
        Deterministic ML fallback inference function.
        """
        dist = event.distance_to_facility_m if event.distance_to_facility_m is not None else 10000.0
        frp = event.frp
        ndvi = event.ndvi if event.ndvi is not None else 0.5
        persistence = event.persistence_score or 0.0

        explanation: List[str] = []

        if dist < 200 and frp > 150:
            classification = "industrial_fire"
            confidence = 0.942
            risk_score = 87.0
            risk_level = "critical"
            explanation.append(f"High Fire Radiative Power ({frp} MW)")
            explanation.append(f"Immediate industrial facility proximity ({dist:.1f}m)")
            explanation.append("Surge in thermal activity above facility baseline")
            if ndvi < 0.2:
                explanation.append("Low vegetation context (built-up/industrial area)")
        elif dist < 100 and persistence > 0.8:
            classification = "persistent_industrial_source"
            confidence = 0.925
            risk_score = 35.0
            risk_level = "moderate"
            explanation.append("High temporal persistence score")
            explanation.append("Regular industrial heat source pattern")
            explanation.append(f"Close facility match ({dist:.1f}m)")
        elif ndvi > 0.6 and dist > 3000:
            classification = "wildfire"
            confidence = 0.890
            risk_score = 65.0
            risk_level = "high"
            explanation.append(f"High vegetation context index (NDVI {ndvi:.2f})")
            explanation.append("No industrial facility within 3km")
            explanation.append("Spatial spread pattern across vegetation area")
        elif ndvi > 0.3 and dist > 5000:
            classification = "agricultural_fire"
            confidence = 0.850
            risk_score = 25.0
            risk_level = "low"
            explanation.append("Agricultural cropland signature")
            explanation.append("Seasonal crop residue burning window")
        elif event.facility_type in ["refinery", "petrochemical", "power_plant"] and dist < 300:
            classification = "gas_flare"
            confidence = 0.910
            risk_score = 40.0
            risk_level = "moderate"
            explanation.append("Known industrial stack / flaring signature")
            explanation.append("Consistent thermal profile")
        else:
            classification = "unknown"
            confidence = 0.500
            risk_score = 20.0
            risk_level = "low"
            explanation.append("Insufficient distinct features to categorize")

        return classification, confidence, risk_score, risk_level, explanation
