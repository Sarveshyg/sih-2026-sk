from sqlalchemy import Column, String, Float, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base


class ThermalEvent(Base):
    __tablename__ = "thermal_events"

    id = Column(String, primary_key=True, index=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    frp = Column(Float, nullable=False)
    brightness_temperature = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    timestamp = Column(String, nullable=False, index=True)
    satellite = Column(String, nullable=False)

    facility_id = Column(String, ForeignKey("facilities.id"), nullable=True, index=True)

    # Optional enriched fields
    nearest_facility_name = Column(String, nullable=True)
    facility_type = Column(String, nullable=True, index=True)
    distance_to_facility_m = Column(Float, nullable=True)
    persistence_score = Column(Float, nullable=True)
    detections_24h = Column(Integer, nullable=True)
    detections_7d = Column(Integer, nullable=True)
    ndvi = Column(Float, nullable=True)
    ndbi = Column(Float, nullable=True)

    # Relationships
    facility = relationship("Facility", back_populates="events")
    prediction = relationship("Prediction", back_populates="event", uselist=False, cascade="all, delete-orphan")


Index("idx_thermal_events_lat_lon", ThermalEvent.latitude, ThermalEvent.longitude)
