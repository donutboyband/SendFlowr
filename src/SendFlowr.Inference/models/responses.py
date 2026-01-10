"""
Response models for SendFlowr Timing API
"""
from pydantic import BaseModel, Field
from typing import Dict
from datetime import datetime


class TimingDecisionResponse(BaseModel):
    """Response matching spec.json"""
    decision_id: str
    universal_id: str
    target_minute_utc: int = Field(..., ge=0, le=10079, description="Canonical minute slot (0-10079)")
    trigger_timestamp_utc: datetime
    latency_estimate_seconds: float
    confidence_score: float = Field(..., ge=0, le=1)
    model_version: str
    explanation_ref: str
    created_at_utc: datetime
    debug: Dict
