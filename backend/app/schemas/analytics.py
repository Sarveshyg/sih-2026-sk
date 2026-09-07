from pydantic import BaseModel, Field, ConfigDict


class AnalyticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_events: int = Field(..., description="Total thermal events recorded")
    industrial_events: int = Field(..., description="Number of events classified as industrial")
    critical_events: int = Field(..., description="Number of events with critical risk level")
    persistent_sources: int = Field(..., description="Number of persistent industrial sources identified")

