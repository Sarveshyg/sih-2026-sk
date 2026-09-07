import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String, primary_key=True, index=True)
    event_id = Column(String, nullable=False, index=True)
    facility_name = Column(String, nullable=False)
    facility_type = Column(String, nullable=False)
    location = Column(String, nullable=False)
    region = Column(String, nullable=False, index=True)
    fire_type = Column(String, nullable=False)
    classification = Column(String, nullable=False)
    risk_score = Column(Integer, nullable=False, index=True)
    severity = Column(String, nullable=False, index=True)  # critical, high, moderate, low
    confidence = Column(Float, nullable=False)
    frp = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="NEW", index=True)  # NEW, ACKNOWLEDGED, UNDER_REVIEW, IN_PROGRESS, ESCALATED, RESOLVED
    current_tier = Column(Integer, nullable=False, default=1, index=True)  # 1, 2, 3
    previous_tier = Column(Integer, nullable=True, default=0)
    assigned_agency = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
    escalation_history = Column(Text, nullable=False, default="[]")  # JSON list of EscalationLog
    resolution_note = Column(Text, nullable=True)
    resolved_by = Column(String, nullable=True)
    resolved_tier = Column(Integer, nullable=True)
    resolved_at = Column(String, nullable=True)
