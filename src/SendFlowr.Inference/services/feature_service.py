"""
Feature Service - Business logic for feature computation
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import numpy as np

from repositories.event_repository import EventRepository
from repositories.feature_repository import FeatureRepository
from core.timing_model import ContinuousCurve, MinuteSlotGrid, MINUTES_PER_WEEK
from core.ml_models import MLModels


# Circuit breaker configuration
CIRCUIT_BREAKER_WINDOWS_HOURS = {
    'support_ticket': 48,
    'complaint': 48,
    'unsubscribe_request': 168
}

HOT_PATH_EVENTS = ('site_visit', 'sms_click', 'product_view')


class FeatureService:
    """Service for computing and managing features"""
    
    def __init__(self, event_repo: EventRepository, feature_repo: FeatureRepository):
        self.event_repo = event_repo
        self.feature_repo = feature_repo
        self.ml_models = MLModels()
    
    def get_or_compute_features(self, universal_id: str) -> Dict:
        """Get cached features or compute on-demand"""
        features = self.feature_repo.get_features(universal_id)
        print(f"[FeatureService] Loaded cached features for {universal_id}: {features}")
        
        if not features or features.get('version') != '2.0_minute_level':
            features = self.compute_features(universal_id)
            print(f"[FeatureService] Computed new features for {universal_id}: {features}")
        
        return features
    
    def compute_features(self, universal_id: str) -> Dict:
        """Compute complete feature set"""
        # Get click events
        click_timestamps = self.event_repo.get_click_events(universal_id)
        
        # Build minute-level curve
        if not click_timestamps:
            # Cold start: use ML prior instead of uniform
            cold_start = self.ml_models.generate_cold_start_curve({'universal_id': universal_id})
            click_curve = ContinuousCurve(cold_start)
        else:
            click_curve = ContinuousCurve.from_click_events(click_timestamps, sigma_minutes=60)
        
        # Get peak windows
        peak_windows = click_curve.find_peak_window(window_minutes=120, top_k=3)
        
        # Get recency/frequency metrics
        event_counts = self.event_repo.get_event_counts(universal_id)
        recency = self._parse_event_counts(event_counts)
        
        return {
            'universal_id': universal_id,
            'version': '2.0_minute_level',
            'click_curve_minutes': click_curve.probabilities.tolist(),
            'curve_confidence': click_curve.get_confidence_score(),
            'peak_windows': [
                {
                    'minute_slot': slot,
                    'readable': MinuteSlotGrid.slot_to_readable(slot),
                    'probability': prob
                }
                for slot, prob in peak_windows
            ],
            **recency,
            'computed_at': datetime.utcnow().isoformat()
        }
    
    def compute_all_users(self):
        """Compute features for all active users"""
        users = self.event_repo.get_all_active_users(min_events=3)
        print(f"Computing features for {len(users)} active users...")
        
        for universal_id, event_count in users:
            try:
                features = self.compute_features(universal_id)
                self.feature_repo.store_features(universal_id, features)
            except Exception as e:
                print(f"❌ Error computing features for {universal_id}: {e}")
        
        print(f"✅ Completed feature computation for {len(users)} users")
    
    def get_context_signals(self, universal_id: str) -> Dict:
        """Get real-time contextual signals (hot paths, circuit breakers)"""
        suppression_rows, hot_path_rows = self.event_repo.get_context_signals(
            universal_id,
            tuple(CIRCUIT_BREAKER_WINDOWS_HOURS.keys()),
            HOT_PATH_EVENTS
        )
        
        # Process circuit breakers
        now = datetime.now(timezone.utc)
        suppressed = False
        suppression_reason = None
        suppression_until = None
        
        for event_type, last_ts in suppression_rows:
            last_ts_utc = self._to_utc(last_ts)
            release_at = last_ts_utc + timedelta(hours=CIRCUIT_BREAKER_WINDOWS_HOURS.get(event_type, 0))
            if release_at > now:
                suppressed = True
                suppression_reason = event_type
                suppression_until = release_at
                break
        
        # Process hot paths
        hot_path_active = False
        hot_path_signal = None
        hot_path_weight = 0.0
        
        if hot_path_rows:
            event_type, last_ts = hot_path_rows[0]
            last_ts_utc = self._to_utc(last_ts)
            minutes_ago = (now - last_ts_utc).total_seconds() / 60.0
            
            if minutes_ago < 30:
                hot_path_active = True
                hot_path_signal = event_type
                hot_path_weight = self.ml_models.predict_signal_weight(
                    signal_type=event_type,
                    minutes_ago=minutes_ago,
                    default_weight=1.0
                )
        
        return {
            'suppressed': {
                'active': suppressed,
                'reason': suppression_reason,
                'until': suppression_until
            },
            'hot_path': {
                'active': hot_path_active,
                'signal': hot_path_signal,
                'weight': hot_path_weight
            }
        }
    
    @staticmethod
    def _parse_event_counts(result: List) -> Dict:
        """Parse event count query results into feature dict"""
        features = {
            'last_click_ts': None,
            'last_open_ts': None,
            'last_delivered_ts': None,
            'click_count_30d': 0,
            'click_count_7d': 0,
            'click_count_1d': 0,
            'open_count_30d': 0,
            'open_count_7d': 0,
            'delivery_count_30d': 0
        }
        
        for event_type, last_event, count_30d, count_7d, count_1d in result:
            if event_type == 'clicked':
                features['last_click_ts'] = last_event.isoformat() if last_event else None
                features['click_count_30d'] = count_30d
                features['click_count_7d'] = count_7d
                features['click_count_1d'] = count_1d
            elif event_type == 'opened':
                features['last_open_ts'] = last_event.isoformat() if last_event else None
                features['open_count_30d'] = count_30d
                features['open_count_7d'] = count_7d
            elif event_type == 'delivered':
                features['last_delivered_ts'] = last_event.isoformat() if last_event else None
                features['delivery_count_30d'] = count_30d
        
        return features
    
    @staticmethod
    def _to_utc(dt: datetime) -> datetime:
        """Convert to UTC timezone-aware datetime"""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
