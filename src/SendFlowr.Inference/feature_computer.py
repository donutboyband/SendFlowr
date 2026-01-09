import redis
from clickhouse_driver import Client
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List
import json

class FeatureComputer:
    def __init__(self, clickhouse_host='localhost', redis_host='localhost'):
        self.ch_client = Client(
            host=clickhouse_host,
            port=9000,
            database='sendflowr',
            user='sendflowr',
            password='sendflowr_dev'
        )
        self.redis_client = redis.Redis(host=redis_host, port=6379, decode_responses=True)
    
    def compute_hourly_histogram(self, recipient_id: str, days_back: int = 90) -> Dict[int, float]:
        """Compute 24-hour histogram of email opens"""
        query = """
            SELECT toHour(timestamp) as hour, count() as count
            FROM email_events
            WHERE recipient_id = %(recipient_id)s
            AND event_type = 'opened'
            AND timestamp >= now() - INTERVAL %(days)d DAY
            GROUP BY hour
            ORDER BY hour
        """
        
        result = self.ch_client.execute(query, {
            'recipient_id': recipient_id,
            'days': days_back
        })
        
        # Create 24-hour histogram with smoothing
        histogram = {h: 0.0 for h in range(24)}
        total_opens = sum(count for _, count in result)
        
        if total_opens == 0:
            # Default uniform distribution if no data
            return {h: 1.0/24.0 for h in range(24)}
        
        # Fill in actual counts
        for hour, count in result:
            histogram[hour] = count
        
        # Laplace smoothing (add 1 to each hour)
        smoothed = {h: (count + 1) / (total_opens + 24) for h, count in histogram.items()}
        
        return smoothed
    
    def compute_weekday_histogram(self, recipient_id: str, days_back: int = 90) -> Dict[int, float]:
        """Compute weekday histogram (0=Monday, 6=Sunday)"""
        query = """
            SELECT toDayOfWeek(timestamp) - 1 as weekday, count() as count
            FROM email_events
            WHERE recipient_id = %(recipient_id)s
            AND event_type = 'opened'
            AND timestamp >= now() - INTERVAL %(days)d DAY
            GROUP BY weekday
            ORDER BY weekday
        """
        
        result = self.ch_client.execute(query, {
            'recipient_id': recipient_id,
            'days': days_back
        })
        
        histogram = {d: 0.0 for d in range(7)}
        total_opens = sum(count for _, count in result)
        
        if total_opens == 0:
            return {d: 1.0/7.0 for d in range(7)}
        
        for weekday, count in result:
            histogram[weekday] = count
        
        # Laplace smoothing
        smoothed = {d: (count + 1) / (total_opens + 7) for d, count in histogram.items()}
        
        return smoothed
    
    def compute_recency_features(self, recipient_id: str) -> Dict[str, any]:
        """Compute recency features: last open/click timestamps and counts"""
        query = """
            SELECT 
                event_type,
                max(timestamp) as last_event,
                countIf(timestamp >= now() - INTERVAL 30 DAY) as count_30d,
                countIf(timestamp >= now() - INTERVAL 7 DAY) as count_7d
            FROM email_events
            WHERE recipient_id = %(recipient_id)s
            AND event_type IN ('opened', 'clicked')
            GROUP BY event_type
        """
        
        result = self.ch_client.execute(query, {'recipient_id': recipient_id})
        
        features = {
            'last_open_ts': None,
            'last_click_ts': None,
            'open_count_30d': 0,
            'click_count_30d': 0,
            'open_count_7d': 0,
            'click_count_7d': 0
        }
        
        for event_type, last_event, count_30d, count_7d in result:
            if event_type == 'opened':
                features['last_open_ts'] = last_event.isoformat() if last_event else None
                features['open_count_30d'] = count_30d
                features['open_count_7d'] = count_7d
            elif event_type == 'clicked':
                features['last_click_ts'] = last_event.isoformat() if last_event else None
                features['click_count_30d'] = count_30d
                features['click_count_7d'] = count_7d
        
        return features
    
    def compute_all_features(self, recipient_id: str) -> Dict:
        """Compute all features for a recipient"""
        print(f"Computing features for {recipient_id}...")
        
        features = {
            'recipient_id': recipient_id,
            'hour_histogram_24': self.compute_hourly_histogram(recipient_id),
            'weekday_histogram_7': self.compute_weekday_histogram(recipient_id),
            **self.compute_recency_features(recipient_id),
            'computed_at': datetime.utcnow().isoformat()
        }
        
        return features
    
    def store_features(self, recipient_id: str, features: Dict, ttl: int = 86400):
        """Store features in Redis with TTL (default 24 hours)"""
        key = f"features:{recipient_id}"
        self.redis_client.setex(
            key,
            ttl,
            json.dumps(features)
        )
        print(f"✅ Stored features for {recipient_id}")
    
    def get_features(self, recipient_id: str) -> Dict | None:
        """Retrieve features from Redis"""
        key = f"features:{recipient_id}"
        data = self.redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    
    def compute_and_store_all_users(self):
        """Compute features for all active users"""
        query = """
            SELECT DISTINCT recipient_id, count() as event_count
            FROM email_events
            WHERE timestamp >= now() - INTERVAL 90 DAY
            GROUP BY recipient_id
            ORDER BY event_count DESC
        """
        
        users = self.ch_client.execute(query)
        print(f"Found {len(users)} active users")
        
        for recipient_id, event_count in users:
            try:
                features = self.compute_all_features(recipient_id)
                self.store_features(recipient_id, features)
            except Exception as e:
                print(f"❌ Error computing features for {recipient_id}: {e}")
        
        print(f"✅ Computed features for {len(users)} users")

if __name__ == "__main__":
    print("🌸 SendFlowr Feature Computer")
    print("=" * 40)
    print()
    
    computer = FeatureComputer()
    computer.compute_and_store_all_users()
    
    print()
    print("🎯 Feature computation complete!")
