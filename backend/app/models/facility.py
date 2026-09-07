from sqlalchemy import Column, String, Float, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Facility(Base):
    __tablename__ = "facilities"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    geometry = Column(Text, nullable=True)  # GeoJSON string or polygon coords

    # Relationships
    events = relationship("ThermalEvent", back_populates="facility")
