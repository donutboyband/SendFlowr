"""
Event Repository - ClickHouse data access for email events
"""
from clickhouse_driver import Client
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Optional
import os


class EventRepository:
    """Repository for email_events table"""
    
    def __init__(self, host: str = None, port: int = None):
        self.client = Client(
            host=host or os.getenv('CLICKHOUSE_HOST', 'localhost'),
            port=int(port or os.getenv('CLICKHOUSE_PORT', '9000')),
            user=os.getenv('CLICKHOUSE_USER', 'sendflowr'),
            password=os.getenv('CLICKHOUSE_PASSWORD', 'sendflowr_dev'),
            database=os.getenv('CLICKHOUSE_DATABASE', 'sendflowr')
        )
    
    def get_click_events(self, universal_id: str, days_back: int = 90) -> List[datetime]:
        """
        Get all click timestamps for a user (by Universal ID).
        
         All queries use Universal SendFlowr ID.
        """
        query = """
            SELECT timestamp
            FROM sendflowr.email_events
            WHERE universal_id = %(universal_id)s
              AND event_type = 'clicked'
              AND timestamp >= now() - INTERVAL %(days)d DAY
            ORDER BY timestamp
        """
        
        result = self.client.execute(query, {
            'universal_id': universal_id,
            'days': days_back
        })
        
        return [row[0] for row in result]
    
    def get_event_counts(self, universal_id: str) -> Dict[str, int]:
        """Get event counts by type for recency/frequency features (by Universal ID)"""
        query = """
            SELECT 
                event_type,
                max(timestamp) as last_event,
                countIf(timestamp >= now() - INTERVAL 30 DAY) as count_30d,
                countIf(timestamp >= now() - INTERVAL 7 DAY) as count_7d,
                countIf(timestamp >= now() - INTERVAL 1 DAY) as count_1d
            FROM sendflowr.email_events
            WHERE universal_id = %(universal_id)s
              AND timestamp >= now() - INTERVAL 90 DAY
              AND event_type IN ('clicked', 'opened', 'delivered')
            GROUP BY event_type
        """
        
        result = self.client.execute(query, {'universal_id': universal_id})
        return result
    
    def get_context_signals(self, universal_id: str, 
                           circuit_breaker_events: Tuple[str, ...],
                           hot_path_events: Tuple[str, ...]) -> Tuple[List, List]:
        """
        Get contextual signals for hot paths and circuit breakers
        
        Args:
            universal_id: Universal SendFlowr ID 
        
        Returns: (suppression_rows, hot_path_rows)
        """
        # Circuit breaker events
        suppression_query = """
            SELECT event_type, max(timestamp) AS last_ts
            FROM sendflowr.email_events
            WHERE universal_id = %(universal_id)s
              AND event_type IN %(cb_events)s
            GROUP BY event_type
            ORDER BY last_ts DESC
        """
        
        suppression_rows = self.client.execute(suppression_query, {
            'universal_id': universal_id,
            'cb_events': circuit_breaker_events
        })
        
        # Hot path events (recent only)
        hot_path_query = """
            SELECT event_type, max(timestamp) AS last_ts
            FROM sendflowr.email_events
            WHERE universal_id = %(universal_id)s
              AND event_type IN %(hot_events)s
              AND timestamp >= now() - INTERVAL 30 MINUTE
            GROUP BY event_type
            ORDER BY last_ts DESC
            LIMIT 1
        """
        
        hot_path_rows = self.client.execute(hot_path_query, {
            'universal_id': universal_id,
            'hot_events': hot_path_events
        })
        
        return suppression_rows, hot_path_rows
    
    def get_all_active_users(self, min_events: int = 3) -> List[Tuple[str, int]]:
        """Get list of all active users with sufficient data (by Universal ID)"""
        query = """
            SELECT DISTINCT universal_id, count() as event_count
            FROM sendflowr.email_events
            WHERE timestamp >= now() - INTERVAL 90 DAY
              AND universal_id != ''  -- Exclude events without resolved ID
            GROUP BY universal_id
            HAVING event_count >= %(min_events)d
            ORDER BY event_count DESC
        """
        
        return self.client.execute(query, {'min_events': min_events})
