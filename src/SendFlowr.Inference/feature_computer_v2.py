"""
SendFlowr Feature Computer - Minute-Level Resolution

Refactored to align with Timing Layer spec:
- Minute-level engagement patterns (10,080 slots)
- Continuous curves, not histograms
- Click/conversion priority (MPP resilient)
- Hourly fallback for backwards compatibility
"""

import redis
from clickhouse_driver import Client
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from timing_model import ContinuousCurve, MinuteSlotGrid, MINUTES_PER_WEEK


class MinuteLevelFeatureComputer:
    """
    Computes minute-level engagement features
    
    Per spec: "All new timing logic must be expressible at minute resolution"
    """
    
    def __init__(self, clickhouse_host='localhost', redis_host='localhost'):
        self.ch_client = Client(
            host=clickhouse_host,
            port=9000,
            database='sendflowr',
            user='sendflowr',
            password='sendflowr_dev'
        )
        self.redis_client = redis.Redis(host=redis_host, port=6379, decode_responses=True)
    
    def compute_minute_level_curve(
        self, 
        recipient_id: str, 
        event_type: str = 'clicked',
        days_back: int = 90
    ) -> ContinuousCurve:
        """
        Compute continuous engagement curve from minute-level event data
        
        Per spec: "Clicks, conversions, replies, and real-time activity 
        dominate all inference."
        
        Default to 'clicked' not 'opened' (MPP resilience)
        """
        query = """
            SELECT timestamp
            FROM email_events
            WHERE recipient_id = %(recipient_id)s
            AND event_type = %(event_type)s
            AND timestamp >= now() - INTERVAL %(days)d DAY
            ORDER BY timestamp
        """
        
        result = self.ch_client.execute(query, {
            'recipient_id': recipient_id,
            'event_type': event_type,
            'days': days_back
        })
        
        if not result or len(result) == 0:
            # Cold start: return uniform curve
            print(f"  No {event_type} events for {recipient_id}, using uniform prior")
            return ContinuousCurve(np.ones(MINUTES_PER_WEEK) / MINUTES_PER_WEEK)
        
        # Extract timestamps
        timestamps = [row[0] for row in result]
        
        # Build curve from click events
        curve = ContinuousCurve.from_click_events(timestamps, sigma_minutes=60)
        
        return curve
    
    def compute_legacy_hourly_histogram(
        self, 
        recipient_id: str, 
        event_type: str = 'opened',
        days_back: int = 90
    ) -> Dict[int, float]:
        """
        Fallback: Compute hourly histogram for backwards compatibility
        
        Per spec: "Hour-level STO must always remain available as a fallback path"
        """
        query = """
            SELECT toHour(timestamp) as hour, count() as count
            FROM email_events
            WHERE recipient_id = %(recipient_id)s
            AND event_type = %(event_type)s
            AND timestamp >= now() - INTERVAL %(days)d DAY
            GROUP BY hour
            ORDER BY hour
        """
        
        result = self.ch_client.execute(query, {
            'recipient_id': recipient_id,
            'event_type': event_type,
            'days': days_back
        })
        
        histogram = {h: 0.0 for h in range(24)}
        total = sum(count for _, count in result)
        
        if total == 0:
            return {h: 1.0/24.0 for h in range(24)}
        
        for hour, count in result:
            histogram[hour] = count
        
        # Laplace smoothing
        smoothed = {h: (count + 1) / (total + 24) for h, count in histogram.items()}
        return smoothed
    
    def compute_recency_features(self, recipient_id: str) -> Dict:
        """
        Compute recency and frequency features
        
        Prioritizes clicks over opens per MPP resilience requirement
        """
        query = """
            SELECT 
                event_type,
                max(timestamp) as last_event,
                countIf(timestamp >= now() - INTERVAL 30 DAY) as count_30d,
                countIf(timestamp >= now() - INTERVAL 7 DAY) as count_7d,
                countIf(timestamp >= now() - INTERVAL 1 DAY) as count_1d
            FROM email_events
            WHERE recipient_id = %(recipient_id)s
            AND event_type IN ('clicked', 'opened', 'delivered')
            GROUP BY event_type
        """
        
        result = self.ch_client.execute(query, {'recipient_id': recipient_id})
        
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
    
    def compute_all_features(self, recipient_id: str) -> Dict:
        """
        Compute complete feature set:
        - Primary: Minute-level click curve
        - Fallback: Hourly histogram (backwards compat)
        - Recency: Click/open/delivery metrics
        """
        print(f"Computing minute-level features for {recipient_id}...")
        
        # Primary: Minute-level click curve
        click_curve = self.compute_minute_level_curve(recipient_id, 'clicked')
        
        # Fallback: Hourly histogram (for STO compatibility)
        hour_hist = self.compute_legacy_hourly_histogram(recipient_id, 'opened')
        
        # Recency features
        recency = self.compute_recency_features(recipient_id)
        
        # Find peak windows
        peak_windows = click_curve.find_peak_window(window_minutes=120, top_k=3)
        
        features = {
            'recipient_id': recipient_id,
            'version': '2.0_minute_level',
            
            # Primary signal: Minute-level curve
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
            
            # Fallback: Hourly (backwards compat)
            'hour_histogram_24': hour_hist,
            
            # Recency & frequency
            **recency,
            
            'computed_at': datetime.utcnow().isoformat()
        }
        
        return features
    
    def store_features(self, recipient_id: str, features: Dict, ttl: int = 86400):
        """Store features in Redis with TTL"""
        key = f"features:v2:{recipient_id}"
        self.redis_client.setex(key, ttl, json.dumps(features, default=str))
        print(f"✅ Stored v2 features for {recipient_id}")
    
    def get_features(self, recipient_id: str) -> Optional[Dict]:
        """Retrieve features from Redis"""
        key = f"features:v2:{recipient_id}"
        data = self.redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    
    def compute_and_store_all_users(self):
        """Compute minute-level features for all active users"""
        query = """
            SELECT DISTINCT recipient_id, count() as event_count
            FROM email_events
            WHERE timestamp >= now() - INTERVAL 90 DAY
            GROUP BY recipient_id
            HAVING event_count >= 3
            ORDER BY event_count DESC
        """
        
        users = self.ch_client.execute(query)
        print(f"Found {len(users)} active users with sufficient data")
        
        for recipient_id, event_count in users:
            try:
                features = self.compute_all_features(recipient_id)
                self.store_features(recipient_id, features)
            except Exception as e:
                print(f"❌ Error computing features for {recipient_id}: {e}")
        
        print(f"✅ Computed minute-level features for {len(users)} users")


if __name__ == "__main__":
    print("🌸 SendFlowr Minute-Level Feature Computer")
    print("=" * 50)
    print()
    
    computer = MinuteLevelFeatureComputer()
    
    # Test with one user
    features = computer.compute_all_features('user_003')
    
    print()
    print("Sample Features:")
    print(f"  Version: {features['version']}")
    print(f"  Curve Confidence: {features['curve_confidence']:.3f}")
    print(f"  Clicks (30d): {features['click_count_30d']}")
    print(f"  Clicks (7d): {features['click_count_7d']}")
    print()
    print("Top 3 Peak Windows:")
    for w in features['peak_windows']:
        print(f"  {w['readable']} - {w['probability']:.4f}")
