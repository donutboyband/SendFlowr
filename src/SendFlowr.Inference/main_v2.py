"""
SendFlowr Inference API v2 - Timing Layer Compliant

Refactored to output TimingDecision objects per spec.json
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import redis
import json
import uuid
from feature_computer_v2 import MinuteLevelFeatureComputer
from timing_model import ContinuousCurve, MinuteSlotGrid, TimingDecision, MINUTES_PER_WEEK
import numpy as np

app = FastAPI(
    title="SendFlowr Timing Layer API",
    version="2.0.0",
    description="Minute-level timing intelligence with latency awareness"
)

# Initialize services
feature_computer = MinuteLevelFeatureComputer()
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Request/Response models
class TimingRequest(BaseModel):
    """Request for timing decision"""
    recipient_id: str = Field(..., description="SendFlowr universal user ID")
    send_after: Optional[datetime] = Field(None, description="Earliest allowed send time (UTC)")
    send_before: Optional[datetime] = Field(None, description="Latest allowed send time (UTC)")
    latency_estimate_seconds: float = Field(300.0, description="Estimated ESP latency in seconds")
    
class TimingDecisionResponse(BaseModel):
    """Response matching spec.json"""
    decision_id: str
    universal_user_id: str
    target_minute_utc: int = Field(..., ge=0, le=10079, description="Canonical minute slot (0-10079)")
    trigger_timestamp_utc: datetime
    latency_estimate_seconds: float
    confidence_score: float = Field(..., ge=0, le=1)
    model_version: str
    explanation_ref: str
    created_at_utc: datetime
    debug: Dict

class LegacyPredictionRequest(BaseModel):
    """Backwards compatible hourly prediction request"""
    recipient_id: str
    hours_ahead: int = 24

@app.get("/")
def root():
    return {
        "service": "SendFlowr Timing Layer API",
        "version": "2.0.0",
        "compliance": "Minute-level resolution with latency awareness",
        "endpoints": {
            "timing_decision": "/timing-decision (primary)",
            "predict": "/predict (legacy STO fallback)",
            "features": "/features/{recipient_id}",
            "compute_features": "/compute-features",
            "health": "/health"
        }
    }

@app.get("/health")
def health_check():
    try:
        redis_client.ping()
        feature_computer.ch_client.execute("SELECT 1")
        return {
            "status": "healthy",
            "redis": "ok",
            "clickhouse": "ok",
            "compliance": "timing_layer_v2"
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.post("/timing-decision", response_model=TimingDecisionResponse)
def generate_timing_decision(request: TimingRequest):
    """
    Primary endpoint: Generate timing decision per spec.json
    
    Output format:
    - target_minute_utc: Canonical minute slot (0-10079)
    - trigger_timestamp_utc: Actual trigger time accounting for latency
    - confidence_score: Based on curve sharpness
    - Explainable with debug payload
    """
    
    # Get features (v2 minute-level)
    features = feature_computer.get_features(request.recipient_id)
    
    if not features or features.get('version') != '2.0_minute_level':
        # Compute on-demand
        try:
            features = feature_computer.compute_all_features(request.recipient_id)
            feature_computer.store_features(request.recipient_id, features)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to compute features: {str(e)}")
    
    # Reconstruct continuous curve
    curve_probs = np.array(features['click_curve_minutes'])
    curve = ContinuousCurve(curve_probs)
    
    # Find optimal minute slot
    now = datetime.utcnow()
    send_after = request.send_after or now
    send_before = request.send_before or (now + timedelta(days=7))
    
    # Convert time constraints to minute slots
    send_after_slot = MinuteSlotGrid.datetime_to_minute_slot(send_after)
    send_before_slot = MinuteSlotGrid.datetime_to_minute_slot(send_before)
    
    # Find best slot within constraints
    if send_before_slot > send_after_slot:
        valid_slots = range(send_after_slot, send_before_slot)
    else:
        # Handle week wrap
        valid_slots = list(range(send_after_slot, MINUTES_PER_WEEK)) + list(range(0, send_before_slot))
    
    # Find highest probability slot
    best_slot = max(valid_slots, key=lambda s: curve.get_probability(s))
    best_prob = curve.get_probability(best_slot)
    
    # Calculate trigger time accounting for latency
    # Per spec: trigger_timestamp = target_minute - latency_estimate
    
    # Find next occurrence of target slot
    current_slot = MinuteSlotGrid.datetime_to_minute_slot(now)
    slots_ahead = (best_slot - current_slot) % MINUTES_PER_WEEK
    
    target_datetime = now + timedelta(minutes=slots_ahead)
    trigger_datetime = target_datetime - timedelta(seconds=request.latency_estimate_seconds)
    
    # Ensure trigger is in the future
    if trigger_datetime < now:
        # Use next week's occurrence
        target_datetime += timedelta(days=7)
        trigger_datetime = target_datetime - timedelta(seconds=request.latency_estimate_seconds)
    
    # Generate decision
    decision = TimingDecision(
        decision_id=str(uuid.uuid4()),
        universal_user_id=request.recipient_id,
        target_minute_utc=best_slot,
        trigger_timestamp_utc=trigger_datetime,
        latency_estimate_seconds=request.latency_estimate_seconds,
        confidence_score=curve.get_confidence_score(),
        model_version="minute_level_v2.0_click_based",
        explanation_ref=f"explain:{request.recipient_id}:{best_slot}",
        base_curve_peak_minute=int(np.argmax(curve.probabilities)),
        applied_weights=[],
        suppressed=False
    )
    
    # Cache decision
    cache_key = f"decision:{request.recipient_id}:{decision.decision_id}"
    redis_client.setex(cache_key, 3600, json.dumps(decision.to_dict(), default=str))
    
    return TimingDecisionResponse(**decision.to_dict())

@app.post("/predict")
def legacy_predict(request: LegacyPredictionRequest):
    """
    Legacy STO fallback endpoint
    
    Per spec: "Hour-level Send Time Optimization MUST remain supported"
    """
    features = feature_computer.get_features(request.recipient_id)
    
    if not features:
        features = feature_computer.compute_all_features(request.recipient_id)
        feature_computer.store_features(request.recipient_id, features)
    
    # Use hourly histogram (backwards compat)
    hour_hist = features.get('hour_histogram_24', {})
    
    # Find peak hour
    peak_hour = max(hour_hist.items(), key=lambda x: x[1])[0] if hour_hist else 9
    
    return {
        "recipient_id": request.recipient_id,
        "model_version": "hourly_fallback_sto",
        "peak_hour": peak_hour,
        "peak_probability": hour_hist.get(peak_hour, 0),
        "note": "This is a fallback. Use /timing-decision for minute-level precision."
    }

@app.get("/features/{recipient_id}")
def get_features(recipient_id: str):
    """Get cached features (v2 minute-level)"""
    features = feature_computer.get_features(recipient_id)
    
    if not features:
        raise HTTPException(status_code=404, detail=f"No features found for {recipient_id}")
    
    # Don't return full 10k array in response, just metadata
    return {
        "recipient_id": features['recipient_id'],
        "version": features['version'],
        "curve_confidence": features['curve_confidence'],
        "peak_windows": features['peak_windows'],
        "click_count_30d": features['click_count_30d'],
        "click_count_7d": features['click_count_7d'],
        "last_click_ts": features['last_click_ts'],
        "computed_at": features['computed_at']
    }

@app.post("/compute-features")
def compute_all_features():
    """Compute minute-level features for all active users"""
    try:
        feature_computer.compute_and_store_all_users()
        return {"status": "success", "message": "Minute-level features computed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
