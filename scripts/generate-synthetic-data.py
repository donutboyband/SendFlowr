"""
SendFlowr Synthetic Data Generator

Generates realistic email engagement data for ML training:
- Multiple user personas (morning, evening, weekend, commuter, etc.)
- Temporal patterns (time of day, day of week)
- Realistic event sequences (sent → delivered → opened → clicked)
- Campaign variations
- Seasonal/weekly patterns
"""

import random
import json
from datetime import datetime, timedelta
from typing import List, Dict
import uuid
import numpy as np

try:
    from confluent.kafka import Producer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    print("⚠️  confluent-kafka not installed. Use --dry-run mode or install with: pip install confluent-kafka")

# Configuration
KAFKA_BOOTSTRAP = 'localhost:9092'
TOPIC = 'email-events'
START_DATE = datetime(2025, 10, 1)  # 3 months of history
END_DATE = datetime(2026, 1, 10)
DAYS = (END_DATE - START_DATE).days

# User personas with different behavior patterns
USER_PERSONAS = {
    'morning_person': {
        'count': 50,
        'peak_hours': [7, 8, 9],
        'secondary_hours': [10, 11],
        'active_days': [0, 1, 2, 3, 4],  # Weekdays
        'click_rate': 0.15,
        'open_rate': 0.35
    },
    'evening_person': {
        'count': 50,
        'peak_hours': [18, 19, 20, 21],
        'secondary_hours': [17, 22],
        'active_days': [0, 1, 2, 3, 4, 5, 6],
        'click_rate': 0.18,
        'open_rate': 0.40
    },
    'night_owl': {
        'count': 30,
        'peak_hours': [22, 23, 0, 1],
        'secondary_hours': [21, 2],
        'active_days': [4, 5, 6],  # Weekend heavy
        'click_rate': 0.12,
        'open_rate': 0.28
    },
    'lunch_browser': {
        'count': 40,
        'peak_hours': [12, 13],
        'secondary_hours': [11, 14],
        'active_days': [0, 1, 2, 3, 4],
        'click_rate': 0.20,
        'open_rate': 0.45
    },
    'weekend_warrior': {
        'count': 35,
        'peak_hours': [10, 11, 14, 15],
        'secondary_hours': [9, 12, 13, 16],
        'active_days': [5, 6],  # Weekends only
        'click_rate': 0.25,
        'open_rate': 0.50
    },
    'commuter': {
        'count': 45,
        'peak_hours': [8, 9, 17, 18],  # Morning/evening commute
        'secondary_hours': [7, 10, 16, 19],
        'active_days': [0, 1, 2, 3, 4],
        'click_rate': 0.16,
        'open_rate': 0.38
    },
    'sporadic': {
        'count': 50,
        'peak_hours': list(range(24)),  # No pattern
        'secondary_hours': [],
        'active_days': [0, 1, 2, 3, 4, 5, 6],
        'click_rate': 0.08,
        'open_rate': 0.20
    },
    'highly_engaged': {
        'count': 20,
        'peak_hours': [9, 10, 14, 15, 19, 20],
        'secondary_hours': [8, 11, 13, 16, 18, 21],
        'active_days': [0, 1, 2, 3, 4, 5, 6],
        'click_rate': 0.35,
        'open_rate': 0.65
    },
    'low_engaged': {
        'count': 30,
        'peak_hours': [],
        'secondary_hours': list(range(24)),
        'active_days': [0, 1, 2, 3, 4, 5, 6],
        'click_rate': 0.03,
        'open_rate': 0.10
    }
}

# Campaign types
CAMPAIGNS = [
    {'id': 'welcome_series', 'freq_per_week': 0.5, 'subject_prefix': 'Welcome to'},
    {'id': 'newsletter', 'freq_per_week': 1.0, 'subject_prefix': 'Weekly Newsletter'},
    {'id': 'promotion', 'freq_per_week': 2.0, 'subject_prefix': 'Special Offer'},
    {'id': 'abandoned_cart', 'freq_per_week': 0.3, 'subject_prefix': 'You left something'},
    {'id': 'product_reco', 'freq_per_week': 1.5, 'subject_prefix': 'You might like'},
    {'id': 'reengagement', 'freq_per_week': 0.2, 'subject_prefix': 'We miss you'},
]


class SyntheticDataGenerator:
    def __init__(self):
        if KAFKA_AVAILABLE:
            self.producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP})
        else:
            self.producer = None
        self.users = self._generate_users()
        self.events_generated = 0
    
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
                    'config': config
                })
                user_id += 1
        
        return users
    
    def _should_engage_at_time(self, user: Dict, dt: datetime) -> tuple[bool, float]:
        """Determine if user would engage at this time"""
        config = user['config']
        hour = dt.hour
        day_of_week = dt.weekday()
        
        # Check if active on this day
        if day_of_week not in config['active_days']:
            return False, 0.0
        
        # Calculate engagement probability based on time
        if hour in config['peak_hours']:
            prob = 1.0
        elif hour in config['secondary_hours']:
            prob = 0.5
        else:
            prob = 0.1
        
        # Add some noise
        prob *= random.uniform(0.8, 1.2)
        
        return random.random() < prob * 0.3, prob
    
    def _generate_event_sequence(self, user: Dict, campaign: Dict, send_time: datetime):
        """Generate realistic event sequence: sent → delivered → opened → clicked"""
        config = user['config']
        
        # Sent event (always happens)
        yield {
            'event_id': str(uuid.uuid4()),
            'event_type': 'sent',
            'timestamp': send_time.isoformat(),
            'esp': 'klaviyo',
            'recipient_id': user['id'],
            'recipient_email': user['email'],
            'campaign_id': campaign['id'],
            'campaign_name': f"{campaign['subject_prefix']} Campaign",
            'message_id': f"msg_{uuid.uuid4().hex[:12]}",
            'subject': f"{campaign['subject_prefix']} - {send_time.strftime('%B %Y')}",
            'metadata': {
                'persona': user['persona'],
                'test_data': True
            },
            'ingested_at': datetime.utcnow().isoformat()
        }
        
        # Delivered (99% of time, 1-30 seconds later)
        if random.random() < 0.99:
            delivered_time = send_time + timedelta(seconds=random.randint(1, 30))
            yield {
                **_, 
                'event_id': str(uuid.uuid4()),
                'event_type': 'delivered',
                'timestamp': delivered_time.isoformat()
            }
            
            # Opened (based on open_rate and time affinity)
            should_open, time_affinity = self._should_engage_at_time(user, send_time)
            if should_open or random.random() < config['open_rate']:
                # Open delay: 1 min to 48 hours, skewed toward faster
                open_delay_minutes = int(np.random.exponential(120))  # avg 2 hours
                open_delay_minutes = min(open_delay_minutes, 2880)  # max 48 hours
                open_time = delivered_time + timedelta(minutes=open_delay_minutes)
                
                yield {
                    **_, 
                    'event_id': str(uuid.uuid4()),
                    'event_type': 'opened',
                    'timestamp': open_time.isoformat(),
                    'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
                    'ip_address': f"192.168.{random.randint(1,254)}.{random.randint(1,254)}"
                }
                
                # Clicked (based on click_rate, conditional on open)
                if random.random() < (config['click_rate'] / config['open_rate']):
                    # Click happens 1-60 min after open
                    click_delay = random.randint(1, 60)
                    click_time = open_time + timedelta(minutes=click_delay)
                    
                    yield {
                        **_, 
                        'event_id': str(uuid.uuid4()),
                        'event_type': 'clicked',
                        'timestamp': click_time.isoformat(),
                        'click_url': f"https://example.com/{campaign['id']}/product-{random.randint(1,100)}"
                    }
    
    def generate_historical_data(self, publish_to_kafka=True):
        """Generate 3 months of historical data"""
        print(f"🌸 Generating synthetic data for {len(self.users)} users")
        print(f"📅 Date range: {START_DATE.date()} to {END_DATE.date()} ({DAYS} days)")
        print()
        
        current_date = START_DATE
        
        while current_date < END_DATE:
            day_events = 0
            
            # Each user may receive 0-3 campaigns per day
            for user in self.users:
                # Determine number of sends for this user today
                daily_send_prob = sum(c['freq_per_week'] for c in CAMPAIGNS) / 7
                num_sends = np.random.poisson(daily_send_prob)
                
                for _ in range(min(num_sends, 3)):  # Cap at 3 per day
                    # Pick random campaign
                    campaign = random.choice(CAMPAIGNS)
                    
                    # Random send time during the day
                    send_hour = random.randint(6, 22)
                    send_minute = random.randint(0, 59)
                    send_time = current_date.replace(hour=send_hour, minute=send_minute)
                    
                    # Generate event sequence
                    for event in self._generate_event_sequence(user, campaign, send_time):
                        if publish_to_kafka and self.producer:
                            self.producer.produce(
                                TOPIC,
                                key=event['recipient_id'].encode('utf-8'),
                                value=json.dumps(event).encode('utf-8')
                            )
                        
                        self.events_generated += 1
                        day_events += 1
            
            # Flush every day
            if publish_to_kafka and self.producer:
                self.producer.flush()
            
            # Progress update
            if current_date.day == 1 or current_date.day % 7 == 0:
                print(f"📊 {current_date.date()}: {day_events} events | Total: {self.events_generated:,}")
            
            current_date += timedelta(days=1)
        
        print()
        print(f"✅ Generated {self.events_generated:,} total events")
        print(f"📧 Avg per user: {self.events_generated / len(self.users):.0f} events")
        print()
        
        # Summary by persona
        print("👥 Users by persona:")
        for persona, config in USER_PERSONAS.items():
            print(f"  {persona:20s}: {config['count']} users")
    
    def generate_summary_stats(self):
        """Print expected statistics"""
        total_users = sum(p['count'] for p in USER_PERSONAS.values())
        
        print(f"\n📊 Expected Data Summary:")
        print(f"  Total Users: {total_users}")
        print(f"  Time Period: {DAYS} days")
        print(f"  Expected Events: ~{total_users * DAYS * 2:,} (rough estimate)")
        print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate synthetic email engagement data')
    parser.add_argument('--dry-run', action='store_true', help='Calculate stats without publishing')
    parser.add_argument('--summary', action='store_true', help='Show summary only')
    
    args = parser.parse_args()
    
    generator = SyntheticDataGenerator()
    
    if args.summary:
        generator.generate_summary_stats()
    else:
        print("⚠️  This will generate ~500K-1M events!")
        print("⚠️  Make sure ClickHouse and Kafka are running")
        print("⚠️  Consumer should be running to process events")
        print()
        
        if not args.dry_run:
            response = input("Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Cancelled.")
                exit(0)
        
        generator.generate_historical_data(publish_to_kafka=not args.dry_run)
        
        if args.dry_run:
            print("\n✅ Dry run complete (no data published)")
