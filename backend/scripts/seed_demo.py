import json
import os
import sys

# Ensure backend root directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import engine, Base, SessionLocal
from app.models.facility import Facility
from app.models.thermal_event import ThermalEvent
from app.models.prediction import Prediction


def seed_demo_data():
    print("[THERMOS] Creating database tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    demo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "demo"))

    try:
        # Clear existing records
        db.query(Prediction).delete()
        db.query(ThermalEvent).delete()
        db.query(Facility).delete()
        db.commit()
        print("[THERMOS] Cleared old database records.")

        # Seed Facilities
        facilities_path = os.path.join(demo_dir, "facilities.json")
        with open(facilities_path, "r", encoding="utf-8") as f:
            facilities_data = json.load(f)
            for item in facilities_data:
                db.add(
                    Facility(
                        id=item["id"],
                        name=item["name"],
                        type=item["type"],
                        latitude=item["latitude"],
                        longitude=item["longitude"],
                        geometry=item.get("geometry"),
                    )
                )
        db.commit()
        print(f"[THERMOS] Seeded {len(facilities_data)} industrial facilities.")

        # Seed Thermal Events
        events_path = os.path.join(demo_dir, "events.json")
        with open(events_path, "r", encoding="utf-8") as f:
            events_data = json.load(f)
            for item in events_data:
                db.add(
                    ThermalEvent(
                        id=item["id"],
                        latitude=item["latitude"],
                        longitude=item["longitude"],
                        frp=item["frp"],
                        brightness_temperature=item["brightness_temperature"],
                        confidence=item["confidence"],
                        timestamp=item["timestamp"],
                        satellite=item["satellite"],
                        facility_id=item.get("facility_id"),
                        nearest_facility_name=item.get("nearest_facility_name"),
                        facility_type=item.get("facility_type"),
                        distance_to_facility_m=item.get("distance_to_facility_m"),
                        persistence_score=item.get("persistence_score"),
                        detections_24h=item.get("detections_24h"),
                        detections_7d=item.get("detections_7d"),
                        ndvi=item.get("ndvi"),
                        ndbi=item.get("ndbi"),
                    )
                )
        db.commit()
        print(f"[THERMOS] Seeded {len(events_data)} thermal events.")

        # Seed Predictions
        predictions_path = os.path.join(demo_dir, "predictions.json")
        with open(predictions_path, "r", encoding="utf-8") as f:
            predictions_data = json.load(f)
            for item in predictions_data:
                db.add(
                    Prediction(
                        event_id=item["event_id"],
                        classification=item["classification"],
                        confidence=item["confidence"],
                        risk_score=item["risk_score"],
                        risk_level=item["risk_level"],
                        explanation=json.dumps(item.get("explanation", [])),
                    )
                )
        db.commit()
        print(f"[THERMOS] Seeded {len(predictions_data)} AI predictions.")

        print("[THERMOS] Demo seeding completed successfully!")
    except Exception as e:
        db.rollback()
        print(f"[THERMOS] Error seeding database: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
