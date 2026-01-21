"""
SendFlowr ML Support Systems

These helpers implement lightweight, explainable ML-style predictors that
augment the timing physics without owning the decision logic. They should be
easy to replace with true trained models later; current implementations are
deterministic heuristics that mirror the ML-SPEC.md contracts.
"""

from __future__ import annotations

from typing import Dict, Optional
from datetime import datetime, timezone
import math
import numpy as np
import pickle
from pathlib import Path

from core.timing_model import MINUTES_PER_WEEK

# Set REPO_ROOT to the project root (parent of src/)
REPO_ROOT = Path(__file__).resolve().parents[2]


class MLModels:
    """Container for pluggable ML predictors used by the inference service."""

    LATENCY_MODEL_PATH = REPO_ROOT / "models" / "latency_model.pkl"

    def __init__(self, latency_model_path: Optional[str] = None):
        """Initialize ML models, optionally loading trained latency model"""
        self.latency_model = None
        self.latency_feature_cols = None
        self.latency_model_path = Path(latency_model_path) if latency_model_path else self.LATENCY_MODEL_PATH
        print(f"ℹ️  Latency model path resolved to {self.latency_model_path}")
        if self.latency_model_path.exists():
            self._load_latency_model(str(self.latency_model_path))
    
    def _load_latency_model(self, model_path: str):
        """Load trained GBDT latency prediction model"""
        try:
            with open(model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            self.latency_model = model_data['model']
            self.latency_feature_cols = model_data['feature_cols']
            
            print(f"✅ Loaded latency model from {model_path}")
            print(f"   Trained: {model_data.get('trained_at', 'unknown')}")
            print(f"   Test MAE: {model_data.get('test_mae', 0):.2f}s")
            print(f"   Test R²: {model_data.get('test_r2', 0):.3f}")
        except Exception as e:
            print(f"⚠️  Failed to load latency model from {model_path}: {e}")
            print(f"   Falling back to heuristic latency prediction")
            self.latency_model = None

    def predict_latency(
        self,
        *,
        esp: Optional[str],
        event_time: datetime,
        default_latency_seconds: float = 300.0,
        payload_bytes: Optional[int] = None,
        queue_depth: Optional[int] = None,
        campaign_type: Optional[str] = None,
    ) -> float:
        """
        Predict delivery latency (seconds) for any channel.
        Channel-agnostic: works for email (Klaviyo, SendGrid), SMS (Twilio), push, etc.
        If trained model is loaded, uses GBDT prediction.
        Otherwise falls back to heuristic implementation.
        """
        import sys
        if self.latency_model and self.latency_feature_cols:
            try:
                sys.stderr.write(f"[ML] Using trained latency model.\n")
                result = self._predict_latency_ml(
                    esp=esp,
                    event_time=event_time,
                    payload_bytes=payload_bytes,
                    queue_depth=queue_depth,
                    campaign_type=campaign_type
                )
                sys.stderr.write(f"[ML] Predicted latency: {result}s\n")
                sys.stderr.flush()
                return result
            except Exception as e:
                sys.stderr.write(f"⚠️  ML prediction failed: {type(e).__name__}: {e}\n")
                sys.stderr.flush()
                import traceback
                traceback.print_exc(file=sys.stderr)
        sys.stderr.write(f"[ML] Falling back to heuristic latency prediction.\n")
        sys.stderr.flush()
        # Fallback: heuristic implementation
        return self._predict_latency_heuristic(
            event_time=event_time,
            default_latency_seconds=default_latency_seconds
        )

    def _feature_vector(
        self,
        *,
        esp: Optional[str],
        campaign_type: Optional[str],
        event_time: datetime,
        payload_bytes: Optional[int],
        queue_depth: Optional[int],
    ) -> Dict[str, float]:
        """Build feature dict matching training schema."""
        import sys
        hour = event_time.hour
        minute = event_time.minute
        day_of_week = event_time.weekday()
        features = {
            # Providers (multi-channel: email, SMS, push)
            'esp_klaviyo': int(esp == 'klaviyo'),
            'esp_sendgrid': int(esp == 'sendgrid'),
            'esp_mailchimp': int(esp == 'mailchimp'),
            'esp_twilio': int(esp == 'twilio'),
            'esp_messagebird': int(esp == 'messagebird'),
            'esp_onesignal': int(esp == 'onesignal'),
            'esp_firebase': int(esp == 'firebase'),
            # Time features
            'hour_of_day': hour,
            'minute': minute,
            'day_of_week': day_of_week,
            'is_top_of_hour': int(minute in [0, 1, 2]),
            'is_quarter_hour': int(minute in [15, 30, 45]),
            'is_morning_rush': int(hour in [8, 9]),
            'is_evening_rush': int(hour in [18, 19]),
            'is_weekend': int(day_of_week in [5, 6]),
            'is_late_night': int(hour in [0, 1, 2, 3, 4, 5]),
            # Campaign
            'campaign_transactional': int(campaign_type == 'transactional'),
            'campaign_promotional': int(campaign_type == 'promotional'),
            # Payload
            'payload_size_kb': (payload_bytes or 0) / 1024,
            'payload_large': int(((payload_bytes or 0) / 1024) > 200),
            # Queue
            'queue_depth_estimate': float(queue_depth) if queue_depth is not None else 0.0,
            'queue_high': int((queue_depth or 0) > 5000),
            'queue_medium': int(1000 < (queue_depth or 0) <= 5000),
        }
        sys.stderr.write(f"[ML] Feature vector: {features}\n")
        sys.stderr.flush()
        return features

    def _predict_latency_ml(
        self,
        *,
        esp: Optional[str],
        event_time: datetime,
        payload_bytes: Optional[int],
        queue_depth: Optional[int],
        campaign_type: Optional[str]
    ) -> float:
        """
        ML-based latency prediction using trained GBDT model.
        
        NOTE: Current model is trained on email-specific synthetic data.
        For production, retrain with real multi-channel telemetry.
        """
        
        hour = event_time.hour
        minute = event_time.minute
        day_of_week = event_time.weekday()
        
        # Build feature vector matching training schema
        # TODO: Make this truly channel-agnostic when we have SMS/push training data
        features = self._feature_vector(
            # Providers (multi-channel: email, SMS, push)
            esp=esp,
            campaign_type=campaign_type,
            event_time=event_time,
            payload_bytes=payload_bytes,
            queue_depth=queue_depth,
        )
        
        # Build feature array in correct order
        feature_array = np.array([[features[col] for col in self.latency_feature_cols]])
        
        # Predict
        prediction = self.latency_model.predict(feature_array)[0]
        
        # Cap at 15 minutes (900s)
        return float(min(max(prediction, 1.0), 900.0))
    
    def _predict_latency_heuristic(
        self,
        *,
        event_time: datetime,
        default_latency_seconds: float
    ) -> float:
        """
        Heuristic latency prediction (fallback when no trained model).
        
        Channel-agnostic congestion patterns based on time-of-day.
        """
        
        latency = default_latency_seconds
        hour = event_time.hour
        minute = event_time.minute

        # Top-of-hour congestion (universal across channels)
        if minute in (0, 1, 2):
            latency *= 1.8

        # Morning/evening batch pressure
        if hour in (8, 9, 18, 19):
            latency *= 1.5

        return float(min(latency, 900.0))

    def predict_signal_weight(
        self,
        *,
        signal_type: str,
        minutes_ago: float,
        brand: Optional[str] = None,
        segment: Optional[str] = None,
        default_weight: float = 0.0,
    ) -> float:
        """
        Predict contextual weight (ω) for a signal.

        Heuristic implementation:
        - Use exponential decay based on minutes_ago
        - Adjust weight by signal_type defaults
        """
        base = default_weight
        if signal_type in ("site_visit", "product_view"):
            base = 1.2
        elif signal_type in ("sms_click", "push_click"):
            base = 1.5
        elif signal_type:
            base = 1.0

        decay = math.exp(-minutes_ago / 15.0) if minutes_ago is not None else 1.0
        return float(base * decay)

    def calibrate_confidence(self, raw_confidence: float, sample_size: int = 0) -> float:
        """
        Calibrate entropy-derived confidence into a reliability-aware score.

        Heuristic: shrink extreme values toward mean when sample size is small.
        """
        if sample_size <= 0:
            return float(max(0.0, min(1.0, raw_confidence * 0.85)))

        shrink = 1.0 / (1.0 + math.exp(-sample_size / 50.0))
        calibrated = (raw_confidence * shrink) + (0.5 * (1 - shrink))
        return float(max(0.0, min(1.0, calibrated)))

    def generate_cold_start_curve(self, cohort_features: Dict) -> np.ndarray:
        """
        Produce a non-uniform cold-start prior based on cohort hints.

        Heuristic: blend a morning and evening bump; adjust for timezone or industry hints if provided.
        """
        curve = np.ones(MINUTES_PER_WEEK, dtype=float)

        # Morning bump (8-10am)
        for day in range(7):
            start = day * 1440 + 8 * 60
            curve[start : start + 120] *= 1.4

        # Evening bump (6-9pm)
        for day in range(7):
            start = day * 1440 + 18 * 60
            curve[start : start + 180] *= 1.6

        # Weekend adjustment
        for day in (5, 6):  # Sat, Sun
            start = day * 1440
            curve[start : start + 1440] *= 1.1

        return curve

    def suppression_probability(self, context: Dict) -> float:
        """
        Estimate suppression likelihood.

        Heuristic: if an active circuit breaker exists, return high probability; otherwise low.
        """
        suppressed = context.get("suppressed", {})
        if suppressed.get("active"):
            return 0.95
        return 0.05
