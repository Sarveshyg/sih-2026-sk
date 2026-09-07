import json
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models.facility import Facility
from app.models.thermal_event import ThermalEvent
from app.models.prediction import Prediction
from app.routes.events import router as events_router
from app.routes.facilities import router as facilities_router
from app.routes.prediction import router as prediction_router
from app.routes.analytics import router as analytics_router


def seed_demo_data_if_empty():
    """Automatically populates DB with demo datasets if empty on startup."""
    db = SessionLocal()
    try:
        # Check if tables exist and are populated
        if db.query(Facility).count() == 0:
            demo_dir = os.path.join(os.path.dirname(__file__), "..", "data", "demo")

            facilities_path = os.path.join(demo_dir, "facilities.json")
            events_path = os.path.join(demo_dir, "events.json")
            predictions_path = os.path.join(demo_dir, "predictions.json")

            if os.path.exists(facilities_path):
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

            if os.path.exists(events_path):
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

            if os.path.exists(predictions_path):
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
    except Exception as e:
        print(f"[THERMOS] Auto-seed warning: {e}")
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    seed_demo_data_if_empty()


# Ensure DB schema and seeds are initialized when app module is loaded
init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="THERMOS - Thermal Hazard Intelligence API",
    description="Backend service for Smart India Hackathon 2026 PS 26162. Provides APIs for thermal events, industrial facilities, AI predictions, and dashboard analytics.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
origins = settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint to verify backend service status."""
    return {"status": "ok"}


# Include routers
app.include_router(events_router)
app.include_router(facilities_router)
app.include_router(prediction_router)
app.include_router(analytics_router)
