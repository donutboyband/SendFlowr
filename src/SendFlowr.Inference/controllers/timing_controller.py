"""
Timing Controller - HTTP route handlers
"""
from fastapi import HTTPException
from typing import Dict

from services.timing_service import TimingService
from services.feature_service import FeatureService
from models.requests import TimingRequest, LegacyPredictionRequest
from models.responses import TimingDecisionResponse


class TimingController:
    """Controller for timing-related endpoints"""
    
    def __init__(self, timing_service: TimingService, feature_service: FeatureService):
        self.timing_service = timing_service
        self.feature_service = feature_service
    
    def generate_timing_decision(self, request: TimingRequest) -> Dict:
        """POST /timing-decision - Primary endpoint"""
        try:
            decision = self.timing_service.generate_timing_decision(request)
            return decision.to_dict()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate timing decision: {str(e)}")
    
    def legacy_predict(self, request: LegacyPredictionRequest) -> Dict:
        """POST /predict - Legacy STO fallback"""
        try:
            features = self.feature_service.get_or_compute_features(request.recipient_id)
            
            # Use hourly histogram (backwards compat)
            hour_hist = features.get('hour_histogram_24', {})
            
            # Find peak hour
            if hour_hist:
                peak_hour = max(hour_hist.items(), key=lambda x: x[1])[0]
            else:
                peak_hour = 9
            
            return {
                "recipient_id": request.recipient_id,
                "model_version": "hourly_fallback_sto",
                "peak_hour": peak_hour,
                "peak_probability": hour_hist.get(peak_hour, 0),
                "note": "This is a fallback. Use /timing-decision for minute-level precision."
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate prediction: {str(e)}")
    
    def get_features(self, recipient_id: str) -> Dict:
        """GET /features/{recipient_id}"""
        try:
            features = self.feature_service.get_or_compute_features(recipient_id)
            
            # Don't return full 10k array, just metadata
            return {
                "recipient_id": features['recipient_id'],
                "version": features['version'],
                "curve_confidence": features['curve_confidence'],
                "peak_windows": features['peak_windows'],
                "click_count_30d": features.get('click_count_30d', 0),
                "click_count_7d": features.get('click_count_7d', 0),
                "last_click_ts": features.get('last_click_ts'),
                "computed_at": features['computed_at']
            }
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"No features found for {recipient_id}: {str(e)}")
    
    def compute_features(self, recipient_id: str = None) -> Dict:
        """POST /compute-features - Compute features on-demand"""
        try:
            if recipient_id:
                features = self.feature_service.compute_features(recipient_id)
                self.feature_service.feature_repo.store_features(recipient_id, features)
                return {"status": "computed", "recipient_id": recipient_id}
            else:
                # Compute for all users
                self.feature_service.compute_all_users()
                return {"status": "computed", "scope": "all_users"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to compute features: {str(e)}")
