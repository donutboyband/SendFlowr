"""
Request models for SendFlowr Timing API
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TimingRequest(BaseModel):
    """
    Request for timing decision with identity resolution.
    
    Per LLM-spec.md §7: Identity Resolution
    - Accepts multiple identity keys (email, phone, ESP IDs, etc.)
    - System resolves to Universal SendFlowr ID before timing decision
    - Deterministic keys: email, phone
    - Probabilistic keys: klaviyo_id, shopify_customer_id, etc.
    """
    # Pre-resolved Universal ID (if you already have it)
    universal_id: Optional[str] = Field(
        None,
        description="Pre-resolved SendFlowr Universal ID (use if already resolved)",
        example="sf_a1b2c3d4e5f6g7h8"
    )
    
    # Identity resolution keys (preferred)
    email: Optional[str] = Field(
        None,
        description="Email address (deterministic key)",
        example="user@example.com"
    )
    phone: Optional[str] = Field(
        None,
        description="Phone number in E.164 format (deterministic key)",
        example="+14155551234"
    )
    klaviyo_id: Optional[str] = Field(
        None,
        description="Klaviyo user ID (probabilistic key)",
        example="k_abc123xyz"
    )
    shopify_customer_id: Optional[str] = Field(
        None,
        description="Shopify customer ID (probabilistic key)",
        example="12345678"
    )
    esp_user_id: Optional[str] = Field(
        None,
        description="ESP-specific user ID (probabilistic key)",
        example="esp_user_999"
    )
    
    # Timing constraints
    send_after: Optional[datetime] = Field(
        None, 
        description="Earliest allowed send time (UTC)",
        example="2026-01-10T00:00:00Z"
    )
    send_before: Optional[datetime] = Field(
        None, 
        description="Latest allowed send time (UTC)",
        example="2026-01-17T00:00:00Z"
    )
    latency_estimate_seconds: float = Field(
        300.0, 
        description="Estimated ESP latency in seconds",
        example=300.0,
        ge=0,
        le=3600
    )
    
    class Config:
        schema_extra = {
            "example": {
                "email": "user@example.com",
                "phone": "+14155551234",
                "klaviyo_id": "k_abc123",
                "send_after": "2026-01-10T00:00:00Z",
                "send_before": "2026-01-17T00:00:00Z",
                "latency_estimate_seconds": 300
            }
        }


class LegacyPredictionRequest(BaseModel):
    """Backwards compatible hourly prediction request"""
    recipient_id: str = Field(..., example="user_12345")
    hours_ahead: int = Field(24, ge=1, le=168, example=24)
    
    class Config:
        schema_extra = {
            "example": {
                "recipient_id": "user_12345",
                "hours_ahead": 24
            }
        }

