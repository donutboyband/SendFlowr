"""
Explanation Repository - ClickHouse storage for timing explanations
"""
from clickhouse_driver import Client
from datetime import datetime, timezone
from typing import Dict, List
import json
import os


class ExplanationRepository:
    """Repository for timing_explanations table"""
    
    def __init__(self, host: str = None, port: int = None):
        self.client = Client(
            host=host or os.getenv('CLICKHOUSE_HOST', 'localhost'),
            port=int(port or os.getenv('CLICKHOUSE_PORT', '9000')),
            user=os.getenv('CLICKHOUSE_USER', 'sendflowr'),
            password=os.getenv('CLICKHOUSE_PASSWORD', 'sendflowr_dev'),
            database=os.getenv('CLICKHOUSE_DATABASE', 'sendflowr')
        )
        self._table_ready = False
    
    def ensure_table_exists(self):
        """Create timing_explanations table if it doesn't exist"""
        if self._table_ready:
            return
        
        self.client.execute("""
            CREATE TABLE IF NOT EXISTS sendflowr.timing_explanations
            (
                decision_id String,
                explanation_ref String,
                universal_id String,
                target_minute UInt16,
                trigger_timestamp_utc DateTime64(3, 'UTC'),
                latency_estimate_seconds Float64,
                confidence_score Float32,
                model_version String,
                base_curve_peak_minute UInt16,
                applied_weights String,
                suppressed UInt8,
                suppression_reason LowCardinality(String),
                suppression_until DateTime64(3, 'UTC'),
                hot_path_signal LowCardinality(String),
                hot_path_weight Float32,
                created_at_utc DateTime64(3, 'UTC') DEFAULT now()
            )
            ENGINE = MergeTree()
            ORDER BY (universal_id, created_at_utc)
            SETTINGS index_granularity = 8192
        """)
        
        self._table_ready = True
    
    def store_explanation(self, 
                         decision_id: str,
                         explanation_ref: str,
                         universal_id: str,
                         target_minute: int,
                         trigger_timestamp: datetime,
                         latency_estimate_seconds: float,
                         confidence_score: float,
                         model_version: str,
                         base_curve_peak_minute: int,
                         applied_weights: List[Dict],
                         suppressed: bool,
                         suppression_reason: str,
                         suppression_until: datetime,
                         hot_path_signal: str,
                         hot_path_weight: float):
        """Store timing decision explanation"""
        
        self.ensure_table_exists()
        
        # Convert to naive UTC
        trigger_ts = self._to_naive_utc(trigger_timestamp)
        suppression_until_ts = self._to_naive_utc(suppression_until) if suppression_until else datetime(2099, 12, 31, 23, 59, 59)
        created_at = datetime.utcnow()
        
        self.client.execute(
            """
            INSERT INTO sendflowr.timing_explanations (
                decision_id,
                explanation_ref,
                universal_id,
                target_minute,
                trigger_timestamp_utc,
                latency_estimate_seconds,
                confidence_score,
                model_version,
                base_curve_peak_minute,
                applied_weights,
                suppressed,
                suppression_reason,
                suppression_until,
                hot_path_signal,
                hot_path_weight,
                created_at_utc
            ) VALUES
            """,
            [(
                decision_id,
                explanation_ref,
                universal_id,
                target_minute,
                trigger_ts,
                latency_estimate_seconds,
                confidence_score,
                model_version,
                base_curve_peak_minute,
                json.dumps(applied_weights),
                1 if suppressed else 0,
                suppression_reason or '',
                suppression_until_ts,
                hot_path_signal or '',
                float(hot_path_weight or 0.0),
                created_at
            )]
        )
    
    @staticmethod
    def _to_naive_utc(dt: datetime) -> datetime:
        """Convert datetime to naive UTC"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
