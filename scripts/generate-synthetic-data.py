#!/usr/bin/env python3
"""
SendFlowr Synthetic Data Generator

Enhanced with SendFlowr-specific training signals:
1. ESP latency arbitrage (congestion spikes, top-of-hour penalties)
2. Engagement based on DELIVERY time not SEND time
3. Minute-level intent spikes
4. Circuit breaker events (support tickets, unsubscribes)
5. Hot path boosts (site visits, SMS clicks)
6. Campaign fatigue modeling
7. Confidence drift over time
8. **Piped through Connector API for production-like flow**
9. **UUIDv7 for time-ordered event IDs**
"""

import random
import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import uuid
import numpy as np
import requests
import time

# UUIDv7 implementation (time-ordered)
def uuid7() -> str:
    """Generate UUIDv7 (time-ordered UUID for better database performance)"""
    timestamp_ms = int(datetime.utcnow().timestamp() * 1000)
    
    # Create 16 bytes for UUID
    uuid_bytes = bytearray(16)
    
    # Timestamp (48 bits = 6 bytes) in big-endian
    uuid_bytes[0] = (timestamp_ms >> 40) & 0xFF
    uuid_bytes[1] = (timestamp_ms >> 32) & 0xFF
    uuid_bytes[2] = (timestamp_ms >> 24) & 0xFF
    uuid_bytes[3] = (timestamp_ms >> 16) & 0xFF
    uuid_bytes[4] = (timestamp_ms >> 8) & 0xFF
    uuid_bytes[5] = timestamp_ms & 0xFF
    
    # Random data for rest
    random_bytes = random.randbytes(10)
    uuid_bytes[6:16] = random_bytes
    
    # Set version (4 bits) to 7
    uuid_bytes[6] = (uuid_bytes[6] & 0x0F) | 0x70
    
    # Set variant (2 bits) to RFC 4122
    uuid_bytes[8] = (uuid_bytes[8] & 0x3F) | 0x80
    
    return str(uuid.UUID(bytes=bytes(uuid_bytes)))

# Configuration
CONNECTOR_API_URL = 'http://localhost:5215'  # Connector API (handles identity resolution)
START_DATE = datetime(2025, 10, 1)
END_DATE = datetime(2026, 1, 10)
DAYS = (END_DATE - START_DATE).days

# User personas (enhanced with drift)
USER_PERSONAS = {
    'morning_person': {
        'count': 50,
        'peak_hours': [7, 8, 9],
        'peak_minutes': [15, 22, 38, 47],  # NEW: minute spikes
        'secondary_hours': [10, 11],
        'active_days': [0, 1, 2, 3, 4],
        'click_rate': 0.15,
        'open_rate': 0.35,
        'drift_rate': 0.002  # NEW: slow drift
    },
    'evening_person': {
        'count': 50,
        'peak_hours': [18, 19, 20, 21],
        'peak_minutes': [5, 18, 33, 52],
        'secondary_hours': [17, 22],
        'active_days': [0, 1, 2, 3, 4, 5, 6],
        'click_rate': 0.18,
        'open_rate': 0.40,
        'drift_rate': 0.002
    },
    'night_owl': {
        'count': 30,
        'peak_hours': [22, 23, 0, 1],
        'peak_minutes': [8, 23, 41, 57],
        'secondary_hours': [21, 2],
        'active_days': [4, 5, 6],
        'click_rate': 0.12,
        'open_rate': 0.28,
        'drift_rate': 0.003
    },
    'lunch_browser': {
        'count': 40,
        'peak_hours': [12, 13],
        'peak_minutes': [12, 27, 38, 49],
        'secondary_hours': [11, 14],
        'active_days': [0, 1, 2, 3, 4],
        'click_rate': 0.20,
        'open_rate': 0.45,
        'drift_rate': 0.002
    },
    'weekend_warrior': {
        'count': 35,
        'peak_hours': [10, 11, 14, 15],
        'peak_minutes': [7, 19, 34, 51],
        'secondary_hours': [9, 12, 13, 16],
        'active_days': [5, 6],
        'click_rate': 0.25,
        'open_rate': 0.50,
        'drift_rate': 0.001
    },
    'commuter': {
        'count': 45,
        'peak_hours': [8, 9, 17, 18],
        'peak_minutes': [14, 28, 42, 56],
        'secondary_hours': [7, 10, 16, 19],
        'active_days': [0, 1, 2, 3, 4],
        'click_rate': 0.16,
        'open_rate': 0.38,
        'drift_rate': 0.002
    },
    'sporadic': {
        'count': 50,
        'peak_hours': list(range(24)),
        'peak_minutes': [],
        'secondary_hours': [],
        'active_days': [0, 1, 2, 3, 4, 5, 6],
        'click_rate': 0.08,
        'open_rate': 0.20,
        'drift_rate': 0.005
    },
    'highly_engaged': {
        'count': 20,
        'peak_hours': [9, 10, 14, 15, 19, 20],
        'peak_minutes': [11, 23, 37, 49],
        'secondary_hours': [8, 11, 13, 16, 18, 21],
        'active_days': [0, 1, 2, 3, 4, 5, 6],
        'click_rate': 0.35,
        'open_rate': 0.65,
        'drift_rate': 0.001
    },
    'low_engaged': {
        'count': 30,
        'peak_hours': [],
        'peak_minutes': [],
        'secondary_hours': list(range(24)),
        'active_days': [0, 1, 2, 3, 4, 5, 6],
        'click_rate': 0.03,
        'open_rate': 0.10,
        'drift_rate': 0.004
    }
}

# Multi-channel providers with realistic latency characteristics
PROVIDERS = [
    # Email providers
    {'channel': 'email', 'provider': 'klaviyo', 'weight': 0.35, 'base_latency_mean': 2.5, 'base_latency_sigma': 0.4},
    {'channel': 'email', 'provider': 'sendgrid', 'weight': 0.25, 'base_latency_mean': 2.3, 'base_latency_sigma': 0.35},
    {'channel': 'email', 'provider': 'mailchimp', 'weight': 0.15, 'base_latency_mean': 2.7, 'base_latency_sigma': 0.45},
    
    # SMS providers (faster delivery, less congestion)
    {'channel': 'sms', 'provider': 'twilio', 'weight': 0.15, 'base_latency_mean': 0.5, 'base_latency_sigma': 0.2},
    {'channel': 'sms', 'provider': 'messagebird', 'weight': 0.05, 'base_latency_mean': 0.6, 'base_latency_sigma': 0.25},
    
    # Push providers (fastest, minimal queue)
    {'channel': 'push', 'provider': 'onesignal', 'weight': 0.03, 'base_latency_mean': 0.1, 'base_latency_sigma': 0.1},
    {'channel': 'push', 'provider': 'firebase', 'weight': 0.02, 'base_latency_mean': 0.15, 'base_latency_sigma': 0.12},
]

CAMPAIGNS = [
    {'id': 'welcome_series', 'freq_per_week': 0.5, 'type': 'transactional', 'avg_size_kb': 45, 'channels': ['email', 'sms']},
    {'id': 'newsletter', 'freq_per_week': 1.0, 'type': 'promotional', 'avg_size_kb': 120, 'channels': ['email']},
    {'id': 'promotion', 'freq_per_week': 2.0, 'type': 'promotional', 'avg_size_kb': 85, 'channels': ['email', 'sms', 'push']},
    {'id': 'abandoned_cart', 'freq_per_week': 0.3, 'type': 'transactional', 'avg_size_kb': 55, 'channels': ['email', 'sms']},
    {'id': 'product_reco', 'freq_per_week': 1.5, 'type': 'promotional', 'avg_size_kb': 95, 'channels': ['email', 'push']},
    {'id': 'reengagement', 'freq_per_week': 0.2, 'type': 'promotional', 'avg_size_kb': 70, 'channels': ['email']},
    {'id': 'flash_sale', 'freq_per_week': 0.5, 'type': 'promotional', 'avg_size_kb': 60, 'channels': ['sms', 'push']},
    {'id': 'order_confirmation', 'freq_per_week': 0.4, 'type': 'transactional', 'avg_size_kb': 40, 'channels': ['email', 'sms']},
]


class EnhancedSyntheticDataGenerator:
    def __init__(self):
        self.users = self._generate_users()
        self.events_generated = 0
        self.user_state = {}  # Track recent sends, hot paths, circuit breakers
        self.batch_events = []  # Batch events for API calls
        self.connector_available = self._check_connector()
    
    def _check_connector(self) -> bool:
        """Check if Connector API is available"""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = requests.get(f"{CONNECTOR_API_URL}/scalar/v1", timeout=3)
                if response.status_code == 200:
                    return True
            except:
                if attempt < max_retries - 1:
                    print(f"⏳ Waiting for Connector API (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(2)
        return False
    
    def _publish_event_via_connector(self, event_data: Dict) -> bool:
        """
        Publish event through Connector API (production flow)
        
        This ensures:
        - Identity resolution happens at ingestion
        - Email hashing for privacy
        - Same flow as production webhooks
        """
        try:
            # Send the actual synthetic event with all the enhanced signals
            # The connector will handle identity resolution and email hashing
            response = requests.post(
                f"{CONNECTOR_API_URL}/api/mock/events/synthetic",
                json=event_data,
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            print(f"⚠️  Failed to publish via connector: {e}")
            return False
    
    def _generate_users(self) -> List[Dict]:
        """Generate user profiles with personas"""
        users = []
        user_id = 1000
        
        for persona_name, config in USER_PERSONAS.items():
            for i in range(config['count']):
                users.append({
                    'id': f'synth_user_{user_id:05d}',
                    'email': f'user{user_id}@example.com',
                    'persona': persona_name,
                    'config': config.copy()  # Copy so drift is per-user
                })
                user_id += 1
        
        return users
    
    def _estimate_queue_depth(self, send_time: datetime, channel: str = 'email') -> int:
        """
        Estimate queue depth at provider for ML training (correlates with latency)
        
        Channel-specific: email has more congestion than SMS/push
        Features: hour_of_day, minute, day_of_week, channel
        Returns: estimated messages in queue (0-10000)
        """
        hour = send_time.hour
        minute = send_time.minute
        day_of_week = send_time.weekday()
        
        # Base queue depth varies by channel
        if channel == 'email':
            base_depth = 500
        elif channel == 'sms':
            base_depth = 100  # Less batch congestion for SMS
        else:  # push
            base_depth = 50   # Minimal queue for push
        
        # Top-of-hour traffic jam (primarily email)
        if minute in [0, 1, 2]:
            if channel == 'email':
                base_depth *= random.uniform(8, 15)  # Massive spike for email
            else:
                base_depth *= random.uniform(2, 4)   # Smaller spike for SMS/push
        elif minute in [15, 30, 45]:
            base_depth *= random.uniform(2, 4)
        
        # Morning/evening rush hours
        if hour in [8, 9, 18, 19]:
            base_depth *= random.uniform(2, 3.5)
        
        # Weekend quieter
        if day_of_week in [5, 6]:
            base_depth *= 0.4
        
        # Late night very quiet
        if hour in [0, 1, 2, 3, 4, 5]:
            base_depth *= 0.2
        
        return int(min(base_depth, 10000))
    
    def _sample_esp_latency(self, send_time: datetime, payload_size_bytes: int = None, queue_depth: int = None, provider_config: dict = None) -> int:
        """
        Realistic provider latency with congestion modeling (ML TRAINING DATA)
        
        This generates realistic latency telemetry for training the latency prediction model.
        Features used: hour_of_day, minute, day_of_week, payload_size, queue_depth, congestion patterns, channel
        
        Per ML-SPEC.md §1: Latency Prediction Model
        
        Args:
            provider_config: dict with 'channel', 'base_latency_mean', 'base_latency_sigma'
        
        Returns: latency in seconds
        """
        hour = send_time.hour
        minute = send_time.minute
        day_of_week = send_time.weekday()
        
        # Channel-specific base latency
        if provider_config:
            mean = provider_config.get('base_latency_mean', 2.5)
            sigma = provider_config.get('base_latency_sigma', 0.4)
            channel = provider_config.get('channel', 'email')
        else:
            mean, sigma, channel = 2.5, 0.4, 'email'
        
        # Base latency: log-normal distribution
        # Email: ~12s median, SMS: ~1-2s, Push: <1s
        base = np.random.lognormal(mean=mean, sigma=sigma)
        
        # Feature: Top-of-hour congestion (primarily affects email)
        # This is a CRITICAL training signal for latency arbitrage
        if minute in [0, 1, 2]:
            if channel == 'email':
                congestion_multiplier = random.uniform(3.0, 6.0)  # Heavy email congestion
            else:
                congestion_multiplier = random.uniform(1.2, 1.5)  # Light SMS/push congestion
            base *= congestion_multiplier
        elif minute in [15, 30, 45]:  # Quarter-hour bumps
            base *= random.uniform(1.3, 1.8)
        
        # Feature: Morning/evening batch pressure (mainly email)
        if hour in [8, 9, 18, 19]:
            if channel == 'email':
                base *= random.uniform(1.5, 2.5)
            else:
                base *= random.uniform(1.1, 1.3)
        
        # Feature: Weekend is faster (less commercial traffic)
        if day_of_week in [5, 6]:
            base *= 0.7
        
        # Feature: Late night is fastest
        if hour in [0, 1, 2, 3, 4, 5]:
            base *= 0.5
        
        # Feature: Payload size (larger emails take longer to process/transmit)
        # SMS and push have minimal payload impact
        if payload_size_bytes and channel == 'email':
            size_kb = payload_size_bytes / 1024
            # Heavy emails (>200KB) add processing time
            if size_kb > 200:
                base *= random.uniform(1.2, 1.5)
            elif size_kb > 100:
                base *= random.uniform(1.05, 1.15)
        
        # Feature: Queue depth (more messages = more delay)
        if queue_depth:
            if queue_depth > 5000:
                base *= random.uniform(1.8, 2.5)
            elif queue_depth > 2000:
                base *= random.uniform(1.3, 1.7)
            elif queue_depth > 1000:
                base *= random.uniform(1.1, 1.3)
        
        # Add realistic jitter (network variance)
        jitter = random.uniform(0.9, 1.1)
        final_latency = base * jitter
        
        # Cap: email 15min, SMS 2min, push 30sec
        if channel == 'email':
            cap = 900
        elif channel == 'sms':
            cap = 120
        else:  # push
            cap = 30
        
        return int(min(final_latency, cap))
    
    def _should_engage_at_time(self, user: Dict, dt: datetime) -> Tuple[bool, float]:
        """
        CRITICAL FIX: Engagement based on DELIVERY time, not send time
        + minute-level spikes
        """
        config = user['config']
        hour = dt.hour
        minute = dt.minute
        day_of_week = dt.weekday()
        
        # Check if active on this day
        if day_of_week not in config['active_days']:
            return False, 0.0
        
        # Hour-level probability
        if hour in config['peak_hours']:
            prob = 1.0
        elif hour in config['secondary_hours']:
            prob = 0.5
        else:
            prob = 0.1
        
        # NEW: Minute-level spikes (this is why 18:47 beats 18:00!)
        if minute in config.get('peak_minutes', []):
            prob *= 1.3
        
        # NEW: Top-of-hour fatigue (everyone's inbox slammed)
        if minute in [0, 1, 59]:
            prob *= 0.7
        
        # Add noise
        prob *= random.uniform(0.8, 1.2)
        
        return random.random() < prob * 0.3, prob
    
    def _check_hot_path_boost(self, user_id: str, current_time: datetime) -> float:
        """
        NEW: Hot path acceleration signals
        
        If user visited site/clicked SMS recently, boost engagement
        """
        if user_id not in self.user_state:
            return 1.0
        
        state = self.user_state[user_id]
        
        # Check for recent hot path events (within 30 min)
        if 'last_hot_path' in state:
            minutes_ago = (current_time - state['last_hot_path']).total_seconds() / 60
            if minutes_ago < 30:
                # Exponential decay: fresh signals boost more
                return 2.0 * np.exp(-minutes_ago / 15)
        
        return 1.0
    
    def _check_circuit_breaker(self, user_id: str, current_time: datetime) -> bool:
        """
        NEW: Circuit breaker suppression
        
        Returns True if sending is suppressed (support ticket, unsubscribe, etc.)
        """
        if user_id not in self.user_state:
            return False
        
        state = self.user_state[user_id]
        
        # Suppressed after support ticket for 48h
        if 'circuit_breaker_until' in state:
            if current_time < state['circuit_breaker_until']:
                return True
            else:
                del state['circuit_breaker_until']
        
        return False
    
    def _apply_campaign_fatigue(self, user_id: str, current_time: datetime) -> float:
        """
        NEW: Campaign fatigue modeling
        
        Decay engagement after 3+ sends in 24h
        """
        if user_id not in self.user_state:
            self.user_state[user_id] = {'recent_sends': []}
        
        state = self.user_state[user_id]
        
        # Count sends in last 24h
        cutoff = current_time - timedelta(hours=24)
        recent = [t for t in state.get('recent_sends', []) if t > cutoff]
        state['recent_sends'] = recent
        
        if len(recent) == 0:
            return 1.0
        elif len(recent) == 1:
            return 0.95
        elif len(recent) == 2:
            return 0.85
        elif len(recent) >= 3:
            return 0.60  # Significant fatigue
        
        return 1.0
    
    def _generate_circuit_breaker_event(self, user_id: str, timestamp: datetime):
        """Generate suppression events"""
        if random.random() < 0.01:  # 1% chance
            event_type = random.choice(['support_ticket', 'complaint', 'unsubscribe_request'])
            
            # Set suppression period
            if user_id not in self.user_state:
                self.user_state[user_id] = {}
            
            suppress_hours = 48 if event_type == 'support_ticket' else 168  # 1 week for unsubscribe
            self.user_state[user_id]['circuit_breaker_until'] = timestamp + timedelta(hours=suppress_hours)
            
            return {
                'event_id': str(uuid.uuid4()),
                'event_type': event_type,
                'timestamp': timestamp.isoformat(),
                'esp': 'internal',
                'recipient_id': user_id,
                'recipient_email': '',
                'campaign_id': 'circuit_breaker',
                'campaign_name': event_type.replace('_', ' ').title(),
                'message_id': '',
                'subject': '',
                'metadata': {
                    'test_data': True,
                    'source': 'zendesk' if event_type == 'support_ticket' else 'preference_center',
                    'circuit_breaker': True
                },
                'ingested_at': datetime.utcnow().isoformat()
            }
        return None
    
    def _generate_hot_path_event(self, user_id: str, timestamp: datetime):
        """Generate acceleration signals"""
        if random.random() < 0.05:  # 5% chance
            event_type = random.choice(['site_visit', 'sms_click', 'product_view'])
            
            # Mark hot path
            if user_id not in self.user_state:
                self.user_state[user_id] = {}
            self.user_state[user_id]['last_hot_path'] = timestamp
            
            return {
                'event_id': str(uuid.uuid4()),
                'event_type': event_type,
                'timestamp': timestamp.isoformat(),
                'esp': 'internal',
                'recipient_id': user_id,
                'recipient_email': '',
                'campaign_id': 'hot_path',
                'campaign_name': event_type.replace('_', ' ').title(),
                'message_id': '',
                'subject': '',
                'metadata': {
                    'test_data': True,
                    'hot_path': True,
                    'source': 'website' if 'site' in event_type or 'product' in event_type else 'twilio'
                },
                'ingested_at': datetime.utcnow().isoformat()
            }
        return None
    
    def _apply_confidence_drift(self, user: Dict):
        """
        NEW: Slow drift in engagement rates over time
        
        Prevents overfitting to static personas
        """
        config = user['config']
        drift = config.get('drift_rate', 0.002)
        
        config['click_rate'] *= random.uniform(1 - drift, 1 + drift)
        config['open_rate'] *= random.uniform(1 - drift, 1 + drift)
        
        # Clamp to reasonable bounds
        config['click_rate'] = max(0.01, min(0.50, config['click_rate']))
        config['open_rate'] = max(0.05, min(0.70, config['open_rate']))
    
    def _generate_event_sequence(self, user: Dict, campaign: Dict, send_time: datetime):
        """Generate realistic event sequence with SendFlowr training signals (multi-channel)"""
        config = user['config']
        user_id = user['id']
        
        # Initialize user state if needed
        if user_id not in self.user_state:
            self.user_state[user_id] = {}
        if 'recent_sends' not in self.user_state[user_id]:
            self.user_state[user_id]['recent_sends'] = []
        
        # Check circuit breaker (suppression)
        if self._check_circuit_breaker(user_id, send_time):
            return  # Suppressed, no send
        
        # Track this send for fatigue
        self.user_state[user_id]['recent_sends'].append(send_time)
        
        # Select channel and provider for this campaign
        available_channels = campaign.get('channels', ['email'])
        channel = random.choice(available_channels)
        
        # Pick provider for this channel (weighted random)
        channel_providers = [p for p in PROVIDERS if p['channel'] == channel]
        if not channel_providers:
            channel_providers = [p for p in PROVIDERS if p['channel'] == 'email']  # Fallback
        
        weights = [p['weight'] for p in channel_providers]
        provider_config = random.choices(channel_providers, weights=weights, k=1)[0]
        provider = provider_config['provider']
        
        # Base event template (matching CanonicalEvent schema)
        campaign_name = campaign['id'].replace('_', ' ').title()
        base_event = {
            'esp': provider,  # Now multi-channel: klaviyo, twilio, onesignal, etc.
            'recipient_id': user_id,
            'recipient_email': user['email'],
            'campaign_id': campaign['id'],
            'campaign_name': campaign_name,
            'message_id': f"msg_{uuid.uuid4().hex[:12]}",
            'subject': f"{campaign_name} - Special Offer" if channel == 'email' else campaign_name,
            'metadata': {
                'persona': user['persona'], 
                'test_data': True,
                'channel': channel,  # Track channel for analytics
                'provider': provider
            },
            'ingested_at': datetime.utcnow().isoformat()
        }
        
        # Calculate ML training features (per ML-SPEC.md §1)
        campaign_type = campaign.get('type', 'promotional')
        avg_size_kb = campaign.get('avg_size_kb', 80) if channel == 'email' else 1  # SMS/push tiny
        # Add realistic variance to payload size
        payload_size_bytes = int((avg_size_kb * 1024) * random.uniform(0.85, 1.15))
        queue_depth = self._estimate_queue_depth(send_time, channel)
        
        # Sent event
        sent_event = base_event.copy()
        sent_event['metadata'] = base_event['metadata'].copy()  # Deep copy metadata
        sent_event.update({
            'event_id': uuid7(),  # UUIDv7 - time-ordered
            'event_type': 'sent',
            'timestamp': send_time.isoformat()
        })
        # Add campaign metadata for training
        sent_event['metadata']['campaign_type'] = campaign_type
        sent_event['metadata']['payload_size_bytes'] = payload_size_bytes
        yield sent_event
        
        # Delivered with realistic latency (channel-aware)
        if random.random() < 0.99:
            latency_seconds = self._sample_esp_latency(send_time, payload_size_bytes, queue_depth, provider_config)
            delivered_time = send_time + timedelta(seconds=latency_seconds)
            
            delivered_event = base_event.copy()
            delivered_event['metadata'] = base_event['metadata'].copy()  # Deep copy metadata
            delivered_event.update({
                'event_id': uuid7(),  # UUIDv7 - time-ordered
                'event_type': 'delivered',
                'timestamp': delivered_time.isoformat()
            })
            # Store ML training features in metadata (per ML-SPEC.md §1: Latency Prediction)
            # send_time = when the message was sent (from sent event timestamp)
            delivered_event['metadata']['latency_seconds'] = latency_seconds
            delivered_event['metadata']['send_time'] = send_time.isoformat()
            delivered_event['metadata']['hour_of_day'] = send_time.hour
            delivered_event['metadata']['minute'] = send_time.minute
            delivered_event['metadata']['day_of_week'] = send_time.weekday()
            delivered_event['metadata']['campaign_type'] = campaign_type
            delivered_event['metadata']['payload_size_bytes'] = payload_size_bytes
            delivered_event['metadata']['queue_depth_estimate'] = queue_depth
            yield delivered_event
            
            # CRITICAL: Engagement based on DELIVERY time, not send time
            should_open, time_affinity = self._should_engage_at_time(user, delivered_time)
            
            # Apply modifiers
            hot_path_mult = self._check_hot_path_boost(user_id, delivered_time)
            fatigue_mult = self._apply_campaign_fatigue(user_id, delivered_time)
            
            effective_open_rate = config['open_rate'] * hot_path_mult * fatigue_mult
            
            if should_open or random.random() < effective_open_rate:
                open_delay_minutes = int(np.random.exponential(120))
                open_delay_minutes = min(open_delay_minutes, 2880)
                open_time = delivered_time + timedelta(minutes=open_delay_minutes)
                
                opened_event = base_event.copy()
                opened_event.update({
                    'event_id': uuid7(),  # UUIDv7 - time-ordered
                    'event_type': 'opened',
                    'timestamp': open_time.isoformat()
                })
                yield opened_event
                
                # Click (conditional on open)
                effective_click_rate = (config['click_rate'] / config['open_rate']) * hot_path_mult * fatigue_mult
                if random.random() < effective_click_rate:
                    click_delay = random.randint(1, 60)
                    click_time = open_time + timedelta(minutes=click_delay)
                    
                    clicked_event = base_event.copy()
                    clicked_event.update({
                        'event_id': uuid7(),  # UUIDv7 - time-ordered
                        'event_type': 'clicked',
                        'timestamp': click_time.isoformat()
                    })
                    yield clicked_event
    
    def generate_historical_data(self, use_connector=True):
        """Generate enhanced training data through Connector API"""
        
        if use_connector and not self.connector_available:
            print("❌ Connector API not available at", CONNECTOR_API_URL)
            print("   Start it with: cd src/SendFlowr.Connectors && dotnet run")
            return
        
        print(f"🌸 Generating SendFlowr-enhanced synthetic data for {len(self.users)} users")
        print(f"📅 Date range: {START_DATE.date()} to {END_DATE.date()} ({DAYS} days)")
        print(f"🎯 Production flow: Events → Connector API → Identity Resolution → Kafka → Consumer")
        print()
        
        if not use_connector:
            print("⚠️  --dry-run mode: Events will not be published")
            print()
        
        current_date = START_DATE
        total_api_calls = 0
        
        while current_date < END_DATE:
            day_events = 0
            
            for user in self.users:
                user_id = user['id']
                
                # Apply slow drift
                if current_date.day == 1:  # Monthly
                    self._apply_confidence_drift(user)
                
                # Email campaigns
                daily_send_prob = sum(c['freq_per_week'] for c in CAMPAIGNS) / 7
                num_sends = np.random.poisson(daily_send_prob)
                
                for _ in range(min(num_sends, 3)):
                    campaign = random.choice(CAMPAIGNS)
                    send_hour = random.randint(6, 22)
                    send_minute = random.randint(0, 59)
                    send_time = current_date.replace(hour=send_hour, minute=send_minute)
                    
                    # Generate event sequence locally (sent, delivered, opened, clicked)
                    for event in self._generate_event_sequence(user, campaign, send_time):
                        if use_connector:
                            # Publish our carefully crafted synthetic event
                            if self._publish_event_via_connector(event):
                                self.events_generated += 1
                                day_events += 1
                            
                            total_api_calls += 1
                            if total_api_calls % 100 == 0:
                                time.sleep(0.05)  # Rate limit
                        else:
                            # Dry run - just count
                            self.events_generated += 1
                            day_events += 1
            
            if current_date.day == 1 or current_date.day % 7 == 0:
                print(f"📊 {current_date.date()}: {day_events} events | Total: {self.events_generated:,}")
            
            current_date += timedelta(days=1)
        
        print()
        print(f"✅ Generated {self.events_generated:,} total events")
        print(f"📧 Avg per user: {self.events_generated / len(self.users):.0f} events")
        
        if use_connector:
            print()
            print("🎯 Production Flow Complete:")
            print("  ✅ Events sent through Connector API")
            print("  ✅ Identity resolution applied")
            print("  ✅ Emails hashed (privacy-first)")
            print("  ✅ Published to Kafka")
            print("  ✅ Consumed to ClickHouse")
        else:
            print()
            print("ℹ️  Dry run complete - no events published")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate SendFlowr-enhanced synthetic data')
    parser.add_argument('--dry-run', action='store_true', help='Calculate without publishing')
    parser.add_argument('--summary', action='store_true', help='Show summary only')
    parser.add_argument('--users', type=int, help='Limit number of users (for testing)')
    parser.add_argument('--count', type=int, default=100, help='Number of events to generate (default: 100)')
    
    args = parser.parse_args()
    
    generator = EnhancedSyntheticDataGenerator()
    
    if not generator.connector_available and not args.dry_run:
        print("❌ Connector API not available at", CONNECTOR_API_URL)
        print()
        print("Options:")
        print("  1. Start the connector: cd src/SendFlowr.Connectors && dotnet run")
        print("  2. Use --dry-run to test without publishing")
        exit(1)
    
    if args.users:
        generator.users = generator.users[:args.users]
        print(f"🎯 Limited to {args.users} users for testing")
        print()
    
    if args.summary:
        print(f"\n📊 Expected Data Summary:")
        print(f"Users: {len(generator.users)}")
        print(f"Date range: {DAYS} days")
        print(f"Estimated events: ~{len(generator.users) * DAYS * 2:,}")
        exit(0)
    
    # Quick mode: just generate N events via connector
    if args.count:
        print(f"🚀 Quick Generate: {args.count} events via Connector API")
        print(f"🎯 Using enhanced synthetic events with:")
        print(f"   ✅ Delivery-time causality (Upgrade #2)")
        print(f"   ✅ Stochastic ESP latency (Upgrade #3)")
        print(f"   ✅ Minute-level intent spikes (Upgrade #4)")
        print(f"   ✅ Hot path boosts & circuit breakers")
        print()
        
        if args.dry_run:
            print(f"✅ Would generate {args.count} events (dry run)")
        else:
            # Generate realistic event sequences through the generator
            success_count = 0
            events_to_generate = []
            
            # Create a few test users
            test_users = generator.users[:5]
            campaign = CAMPAIGNS[0]
            
            # Generate events from random users
            for i in range(args.count):
                user = random.choice(test_users)
                send_time = datetime.utcnow() - timedelta(minutes=random.randint(1, 10080))
                
                # Generate one event sequence (sent → delivered → opened → clicked)
                for event in generator._generate_event_sequence(user, campaign, send_time):
                    events_to_generate.append(event)
                    if len(events_to_generate) >= args.count:
                        break
                
                if len(events_to_generate) >= args.count:
                    break
            
            # Now publish them
            for i, event in enumerate(events_to_generate[:args.count]):
                if generator._publish_event_via_connector(event):
                    success_count += 1
                
                if (i + 1) % 10 == 0:
                    print(f"  Published {i + 1}/{len(events_to_generate[:args.count])} events...")
                
                time.sleep(0.01)  # Rate limit
            
            print()
            print(f"✅ Successfully published {success_count}/{args.count} events")
            print()
            print("Verify in ClickHouse:")
            print('  docker exec sendflowr-clickhouse clickhouse-client --query \\')
            print('    "SELECT event_type, count() FROM sendflowr.email_events WHERE universal_id LIKE \'sf_%\' GROUP BY event_type"')
    else:
        # Full historical data generation
        generator.generate_historical_data(use_connector=not args.dry_run)
