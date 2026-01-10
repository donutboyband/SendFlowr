"""
Feature Repository - Redis cache for computed features
"""
import redis
import json
import os
from typing import Dict, Optional


class FeatureRepository:
    """Repository for feature cache in Redis"""
    
    def __init__(self, host: str = None, port: int = None):
        self.client = redis.Redis(
            host=host or os.getenv('REDIS_HOST', 'localhost'),
            port=int(port or os.getenv('REDIS_PORT', '6379')),
            decode_responses=True
        )
    
    def get_features(self, universal_id: str) -> Optional[Dict]:
        """Retrieve features from Redis"""
        key = f"features:v2:{universal_id}"
        data = self.client.get(key)
        if data:
            return json.loads(data)
        return None
    
    def store_features(self, universal_id: str, features: Dict, ttl: int = 86400):
        """Store features in Redis with TTL"""
        key = f"features:v2:{universal_id}"
        self.client.setex(key, ttl, json.dumps(features, default=str))
    
    def cache_decision(self, universal_id: str, decision_id: str, decision_dict: Dict, ttl: int = 3600):
        """Cache a timing decision"""
        cache_key = f"decision:{universal_id}:{decision_id}"
        self.client.setex(cache_key, ttl, json.dumps(decision_dict, default=str))
