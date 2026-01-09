from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import redis
import json
from feature_computer import FeatureComputer
from baseline_model import BaselineModel

app = FastAPI(title="SendFlowr Inference API", version="1.0.0")

# Initialize services
feature_computer = FeatureComputer()
model = BaselineModel()
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Request/Response models
class PredictionRequest(BaseModel):
    recipient_id: str
    send_time: Optional[datetime] = None
    hours_ahead: int = 24
    
class TimeWindow(BaseModel):
    start: datetime
    end: datetime
    probability: float

class PredictionResponse(BaseModel):
    recipient_id: str
    curve: List[Dict[str, Any]]
    optimal_windows: List[TimeWindow]
    explanation: Dict[str, Any]
    features_used: Dict[str, Any]
    model_version: str

class FeatureResponse(BaseModel):
    recipient_id: str
    hour_histogram_24: Dict[int, float]
    weekday_histogram_7: Dict[int, float]
    last_open_ts: Optional[str]
    last_click_ts: Optional[str]
    open_count_30d: int
    click_count_30d: int
    open_count_7d: int
    click_count_7d: int
    computed_at: str

@app.get("/")
def root():
    return {
        "service": "SendFlowr Inference API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "predict": "/predict",
            "features": "/features/{recipient_id}",
            "compute_features": "/compute-features/{recipient_id}",
            "health": "/health"
        }
    }

@app.get("/health")
def health_check():
    try:
        # Check Redis
        redis_client.ping()
        # Check ClickHouse
        feature_computer.ch_client.execute("SELECT 1")
        return {"status": "healthy", "redis": "ok", "clickhouse": "ok"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.post("/predict", response_model=PredictionResponse)
def predict_engagement(request: PredictionRequest):
    """
    Predict optimal engagement windows for a recipient
    """
    # Get features from cache or compute
    features = feature_computer.get_features(request.recipient_id)
    
    if not features:
        # Compute features on-demand
        try:
            features = feature_computer.compute_all_features(request.recipient_id)
            feature_computer.store_features(request.recipient_id, features)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to compute features: {str(e)}")
    
    # Convert string keys to integers for histograms
    hour_hist = {int(k): v for k, v in features['hour_histogram_24'].items()}
    weekday_hist = {int(k): v for k, v in features['weekday_histogram_7'].items()}
    
    # Use current time if not specified
    send_time = request.send_time or datetime.utcnow()
    
    # Generate prediction curve
    curve = model.predict_engagement_curve(
        hour_histogram=hour_hist,
        weekday_histogram=weekday_hist,
        send_time=send_time,
        hours_ahead=request.hours_ahead
    )
    
    # Find optimal windows
    windows = model.find_optimal_send_window(curve, window_size_hours=2, top_k=3)
    
    # Generate explanation
    explanation = model.explain_prediction(
        hour_histogram=hour_hist,
        weekday_histogram=weekday_hist
    )
    
    # Cache prediction
    cache_key = f"prediction:{request.recipient_id}"
    redis_client.setex(cache_key, 3600, json.dumps({
        'curve': [(t.isoformat(), p) for t, p in curve],
        'windows': [(s.isoformat(), e.isoformat(), p) for s, e, p in windows],
        'cached_at': datetime.utcnow().isoformat()
    }))
    
    return PredictionResponse(
        recipient_id=request.recipient_id,
        curve=[{"time": t.isoformat(), "probability": p} for t, p in curve],
        optimal_windows=[
            TimeWindow(start=s, end=e, probability=p) 
            for s, e, p in windows
        ],
        explanation=explanation,
        features_used={
            'hour_histogram_24': hour_hist,
            'weekday_histogram_7': weekday_hist,
            'open_count_30d': features.get('open_count_30d', 0),
            'click_count_30d': features.get('click_count_30d', 0)
        },
        model_version=model.name
    )

@app.get("/features/{recipient_id}", response_model=FeatureResponse)
def get_features(recipient_id: str):
    """
    Get cached features for a recipient
    """
    features = feature_computer.get_features(recipient_id)
    
    if not features:
        raise HTTPException(status_code=404, detail=f"No features found for {recipient_id}")
    
    return FeatureResponse(**features)

@app.post("/compute-features/{recipient_id}")
def compute_features(recipient_id: str):
    """
    Compute and store features for a recipient
    """
    try:
        features = feature_computer.compute_all_features(recipient_id)
        feature_computer.store_features(recipient_id, features)
        return {"status": "success", "recipient_id": recipient_id, "features": features}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/compute-all-features")
def compute_all_features():
    """
    Compute features for all active users
    """
    try:
        feature_computer.compute_and_store_all_users()
        return {"status": "success", "message": "Features computed for all users"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
