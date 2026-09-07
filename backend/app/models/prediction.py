from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, ForeignKey("thermal_events.id"), nullable=False, unique=True, index=True)
    classification = Column(String, nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False, index=True)
    risk_level = Column(String, nullable=False, index=True)
    explanation = Column(Text, nullable=True)  # JSON serialized list of strings
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    event = relationship("ThermalEvent", back_populates="prediction")
