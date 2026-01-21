"""
Identity Repository - ClickHouse data access for identity resolution

Resolution Rules
- Merges are idempotent
- No destructive overwrites
- Resolution steps must be auditable
"""

from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
from clickhouse_driver import Client
from core.identity_model import IdentifierType, IdentityEdge, IdentityHelper


class IdentityRepository:
    """
    Manages identity graph storage in ClickHouse.
    
    Tables:
    - identity_graph: edges between identifiers (idempotent)
    - identity_audit_log: resolution step tracking
    - resolved_identities: Universal ID mapping cache
    """
    
    def __init__(self, clickhouse_client: Client):
        self.client = clickhouse_client
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create identity tables if they don't exist"""
        
        # identity_graph: stores relationships between identifiers
        self.client.execute("""
            CREATE TABLE IF NOT EXISTS identity_graph (
                identifier_a String,
                identifier_type_a LowCardinality(String),
                identifier_b String,
                identifier_type_b LowCardinality(String),
                weight Float32,
                source LowCardinality(String),
                created_at DateTime DEFAULT now(),
                updated_at DateTime DEFAULT now()
            )
            ENGINE = ReplacingMergeTree(updated_at)
            ORDER BY (identifier_a, identifier_b)
            SETTINGS index_granularity = 8192
        """)
        
        # identity_audit_log: tracks resolution decisions
        self.client.execute("""
            CREATE TABLE IF NOT EXISTS identity_audit_log (
                resolution_id String,
                universal_id String,
                input_identifier String,
                input_type LowCardinality(String),
                resolution_step String,
                confidence_score Float32,
                created_at DateTime DEFAULT now()
            )
            ENGINE = MergeTree()
            ORDER BY (universal_id, created_at)
            SETTINGS index_granularity = 8192
        """)
        
        # resolved_identities: cache of identifier -> Universal ID mappings
        self.client.execute("""
            CREATE TABLE IF NOT EXISTS resolved_identities (
                identifier String,
                identifier_type LowCardinality(String),
                universal_id String,
                confidence_score Float32,
                last_seen DateTime DEFAULT now(),
                created_at DateTime DEFAULT now()
            )
            ENGINE = ReplacingMergeTree(last_seen)
            ORDER BY (identifier, identifier_type)
            SETTINGS index_granularity = 8192
        """)
    
    def add_edge(self, edge: IdentityEdge) -> None:
        """
        Add edge to identity graph (idempotent).
        Per spec §7.3: No destructive overwrites.
        """
        query = """
            INSERT INTO identity_graph (
                identifier_a, identifier_type_a,
                identifier_b, identifier_type_b,
                weight, source, created_at, updated_at
            ) VALUES
        """
        
        self.client.execute(
            query,
            [{
                'identifier_a': edge.identifier_a,
                'identifier_type_a': edge.identifier_type_a.value,
                'identifier_b': edge.identifier_b,
                'identifier_type_b': edge.identifier_type_b.value,
                'weight': edge.weight,
                'source': edge.source,
                'created_at': edge.created_at,
                'updated_at': datetime.utcnow()
            }]
        )
    
    def get_connected_identifiers(self, identifier: str, identifier_type: IdentifierType) -> List[Dict]:
        """
        Find all identifiers connected to this one via graph traversal.
        Returns: [{'identifier': '...', 'type': '...', 'weight': 0.95}, ...]
        """
        query = """
            SELECT DISTINCT
                identifier_b as identifier,
                identifier_type_b as type,
                weight
            FROM identity_graph
            WHERE identifier_a = %(identifier)s
              AND identifier_type_a = %(identifier_type)s
            
            UNION ALL
            
            SELECT DISTINCT
                identifier_a as identifier,
                identifier_type_a as type,
                weight
            FROM identity_graph
            WHERE identifier_b = %(identifier)s
              AND identifier_type_b = %(identifier_type)s
        """
        
        result = self.client.execute(query, {
            'identifier': identifier,
            'identifier_type': identifier_type.value
        })
        
        return [
            {'identifier': row[0], 'type': row[1], 'weight': row[2]}
            for row in result
        ]
    
    def get_universal_id(self, identifier: str, identifier_type: IdentifierType) -> Optional[str]:
        """
        Lookup cached Universal ID for this identifier.
        Fast path for already-resolved identities.
        """
        query = """
            SELECT universal_id, confidence_score
            FROM resolved_identities
            WHERE identifier = %(identifier)s
              AND identifier_type = %(identifier_type)s
            ORDER BY last_seen DESC
            LIMIT 1
        """
        
        result = self.client.execute(query, {
            'identifier': identifier,
            'identifier_type': identifier_type.value
        })
        
        if result:
            return result[0][0]  # universal_id
        return None
    
    def cache_resolution(
        self,
        identifier: str,
        identifier_type: IdentifierType,
        universal_id: str,
        confidence_score: float
    ) -> None:
        """
        Cache resolved Universal ID for fast lookups.
        Per spec §7.3: Idempotent operations.
        """
        query = """
            INSERT INTO resolved_identities (
                identifier, identifier_type, universal_id,
                confidence_score, last_seen, created_at
            ) VALUES
        """
        
        now = datetime.utcnow()
        self.client.execute(
            query,
            [{
                'identifier': identifier,
                'identifier_type': identifier_type.value,
                'universal_id': universal_id,
                'confidence_score': confidence_score,
                'last_seen': now,
                'created_at': now
            }]
        )
    
    def log_resolution_step(
        self,
        resolution_id: str,
        universal_id: str,
        input_identifier: str,
        input_type: IdentifierType,
        step_description: str,
        confidence_score: float
    ) -> None:
        """
        Log resolution step for audit trail.
        Per spec §7.3: Resolution steps MUST be auditable.
        """
        query = """
            INSERT INTO identity_audit_log (
                resolution_id, universal_id, input_identifier,
                input_type, resolution_step, confidence_score, created_at
            ) VALUES
        """
        
        self.client.execute(
            query,
            [{
                'resolution_id': resolution_id,
                'universal_id': universal_id,
                'input_identifier': input_identifier,
                'input_type': input_type.value,
                'resolution_step': step_description,
                'confidence_score': confidence_score,
                'created_at': datetime.utcnow()
            }]
        )
    
    def get_all_identifiers_for_universal_id(self, universal_id: str) -> Dict[str, str]:
        """
        Get all known identifiers for a Universal ID.
        Returns: {'email_hash': '...', 'phone_number': '...', 'klaviyo_id': '...'}
        """
        query = """
            SELECT identifier_type, identifier
            FROM resolved_identities
            WHERE universal_id = %(universal_id)s
            ORDER BY last_seen DESC
        """
        
        result = self.client.execute(query, {'universal_id': universal_id})
        
        return {row[0]: row[1] for row in result}
