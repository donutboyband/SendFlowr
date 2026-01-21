"""
Identity Resolution Service

Identity Resolution
- All decisions MUST reference a Universal SendFlowr ID
- Deterministic matching on email_hash, phone_number
- Probabilistic matching on ESP IDs, customer IDs, device signatures
- Idempotent merges with audit trail
"""

from typing import Dict, Optional, List, Set
from datetime import datetime
from uuid import uuid4

from core.identity_model import (
    IdentifierType, IdentityEdge, IdentityResolution, IdentityHelper
)
from repositories.identity_repository import IdentityRepository


class IdentityResolver:
    """
    Resolves multiple identifiers to a single Universal SendFlowr ID.
    
    Resolution algorithm:
    1. Check cache for existing Universal ID (fast path)
    2. If not cached, traverse identity graph using BFS
    3. Apply deterministic rules first (email_hash, phone)
    4. Apply probabilistic rules second (ESP IDs, customer IDs)
    5. Create new Universal ID if no matches found
    6. Cache result and log audit trail
    """
    
    def __init__(self, identity_repo: IdentityRepository):
        self.repo = identity_repo
    
    def resolve(self, identifiers: Dict[str, str]) -> IdentityResolution:
        """
        Resolve multiple identifiers to Universal ID.
        
        Args:
            identifiers: {
                'email': 'user@example.com',
                'phone': '+14155551234',
                'klaviyo_id': 'k_abc123',
                'shopify_customer_id': '12345'
            }
        
        Returns:
            IdentityResolution with universal_id and audit trail
        """
        resolution_id = f"res_{uuid4().hex[:12]}"
        resolution_steps = []
        
        # Normalize and hash identifiers
        normalized = self._normalize_identifiers(identifiers)
        if not normalized:
            # No valid identifiers provided - create new Universal ID
            universal_id = IdentityHelper.generate_universal_id()
            return IdentityResolution(
                universal_id=universal_id,
                input_identifiers=identifiers,
                resolved_identifiers={},
                resolution_steps=['created_new_id:no_identifiers_provided'],
                confidence_score=0.0
            )
        
        # Step 1: Try deterministic cache lookup (email_hash or phone)
        universal_id, confidence, steps = self._deterministic_lookup(normalized)
        resolution_steps.extend(steps)
        
        if universal_id:
            # Found via deterministic key - done!
            all_identifiers = self.repo.get_all_identifiers_for_universal_id(universal_id)
            
            # Cache any new identifiers
            self._cache_new_identifiers(normalized, universal_id, confidence)
            
            # Log audit trail
            for key, value in normalized.items():
                self.repo.log_resolution_step(
                    resolution_id, universal_id, value, key,
                    f"deterministic_match:{key.value}",
                    confidence
                )
            
            return IdentityResolution(
                universal_id=universal_id,
                input_identifiers=identifiers,
                resolved_identifiers=all_identifiers,
                resolution_steps=resolution_steps,
                confidence_score=confidence
            )
        
        # Step 2: Try probabilistic graph traversal (ESP IDs, customer IDs)
        universal_id, confidence, steps = self._probabilistic_lookup(normalized)
        resolution_steps.extend(steps)
        
        if universal_id:
            # Found via probabilistic match
            all_identifiers = self.repo.get_all_identifiers_for_universal_id(universal_id)
            
            # Cache all identifiers
            self._cache_new_identifiers(normalized, universal_id, confidence)
            
            # Log audit trail
            for key, value in normalized.items():
                self.repo.log_resolution_step(
                    resolution_id, universal_id, value, key,
                    f"probabilistic_match:{key.value}",
                    confidence
                )
            
            return IdentityResolution(
                universal_id=universal_id,
                input_identifiers=identifiers,
                resolved_identifiers=all_identifiers,
                resolution_steps=resolution_steps,
                confidence_score=confidence
            )
        
        # Step 3: No match found - create new Universal ID
        universal_id = IdentityHelper.generate_universal_id()
        resolution_steps.append(f"created_new_id:{universal_id}")
        
        # Cache all identifiers
        for identifier_type, identifier_value in normalized.items():
            self.repo.cache_resolution(identifier_value, identifier_type, universal_id, 1.0)
            
            self.repo.log_resolution_step(
                resolution_id, universal_id, identifier_value, identifier_type,
                f"new_id_created:{identifier_type.value}",
                1.0
            )
        
        return IdentityResolution(
            universal_id=universal_id,
            input_identifiers=identifiers,
            resolved_identifiers={k.value: v for k, v in normalized.items()},
            resolution_steps=resolution_steps,
            confidence_score=1.0
        )
    
    def link_identifiers(
        self,
        identifier_a: str,
        type_a: IdentifierType,
        identifier_b: str,
        type_b: IdentifierType,
        weight: float,
        source: str
    ) -> None:
        """
        Create bidirectional link between two identifiers.
        Per spec §7.3: Idempotent merges.
        
        Args:
            weight: 1.0 = deterministic, < 1.0 = probabilistic
            source: e.g., 'klaviyo_webhook', 'shopify_order'
        """
        edge = IdentityEdge(
            identifier_a=identifier_a,
            identifier_type_a=type_a,
            identifier_b=identifier_b,
            identifier_type_b=type_b,
            weight=weight,
            source=source
        )
        
        self.repo.add_edge(edge)
    
    def _normalize_identifiers(self, raw_identifiers: Dict[str, str]) -> Dict[IdentifierType, str]:
        """
        Normalize and hash raw identifiers.
        
        Returns: {IdentifierType.EMAIL_HASH: 'abc123...', ...}
        """
        normalized = {}
        
        # Email -> email_hash
        if 'email' in raw_identifiers and raw_identifiers['email']:
            normalized[IdentifierType.EMAIL_HASH] = IdentityHelper.hash_email(
                raw_identifiers['email']
            )
        
        # Phone -> normalized phone
        if 'phone' in raw_identifiers and raw_identifiers['phone']:
            normalized[IdentifierType.PHONE_NUMBER] = IdentityHelper.normalize_phone(
                raw_identifiers['phone']
            )
        
        # ESP user IDs (pass through)
        if 'esp_user_id' in raw_identifiers and raw_identifiers['esp_user_id']:
            normalized[IdentifierType.ESP_USER_ID] = raw_identifiers['esp_user_id']
        
        if 'klaviyo_id' in raw_identifiers and raw_identifiers['klaviyo_id']:
            normalized[IdentifierType.KLAVIYO_ID] = raw_identifiers['klaviyo_id']
        
        if 'shopify_customer_id' in raw_identifiers and raw_identifiers['shopify_customer_id']:
            normalized[IdentifierType.SHOPIFY_CUSTOMER_ID] = raw_identifiers['shopify_customer_id']
        
        if 'ip_device_signature' in raw_identifiers and raw_identifiers['ip_device_signature']:
            normalized[IdentifierType.IP_DEVICE_SIGNATURE] = raw_identifiers['ip_device_signature']
        
        return normalized
    
    def _deterministic_lookup(self, identifiers: Dict[IdentifierType, str]) -> tuple[Optional[str], float, List[str]]:
        """
        Try to find Universal ID using deterministic keys (email_hash, phone).
        Returns: (universal_id, confidence, steps)
        """
        steps = []
        
        # Try email_hash first (highest priority)
        if IdentifierType.EMAIL_HASH in identifiers:
            email_hash = identifiers[IdentifierType.EMAIL_HASH]
            universal_id = self.repo.get_universal_id(email_hash, IdentifierType.EMAIL_HASH)
            if universal_id:
                steps.append(f"found_via_email_hash:{email_hash[:8]}")
                return universal_id, 1.0, steps
            steps.append(f"email_hash_miss:{email_hash[:8]}")
        
        # Try phone number
        if IdentifierType.PHONE_NUMBER in identifiers:
            phone = identifiers[IdentifierType.PHONE_NUMBER]
            universal_id = self.repo.get_universal_id(phone, IdentifierType.PHONE_NUMBER)
            if universal_id:
                steps.append(f"found_via_phone:{phone}")
                return universal_id, 1.0, steps
            steps.append(f"phone_miss:{phone}")
        
        return None, 0.0, steps
    
    def _probabilistic_lookup(self, identifiers: Dict[IdentifierType, str]) -> tuple[Optional[str], float, List[str]]:
        """
        Try to find Universal ID using probabilistic keys (ESP IDs, customer IDs).
        Uses graph traversal to find connected identifiers.
        Returns: (universal_id, confidence, steps)
        """
        steps = []
        
        # Try ESP/platform IDs in order of reliability
        probabilistic_order = [
            IdentifierType.KLAVIYO_ID,
            IdentifierType.SHOPIFY_CUSTOMER_ID,
            IdentifierType.ESP_USER_ID,
            IdentifierType.IP_DEVICE_SIGNATURE
        ]
        
        for id_type in probabilistic_order:
            if id_type not in identifiers:
                continue
            
            identifier = identifiers[id_type]
            
            # Check cache first
            universal_id = self.repo.get_universal_id(identifier, id_type)
            if universal_id:
                steps.append(f"found_via_{id_type.value}:{identifier[:12]}")
                return universal_id, 0.85, steps  # Probabilistic confidence
            
            # Traverse graph to find connected identifiers
            connected = self.repo.get_connected_identifiers(identifier, id_type)
            for conn in connected:
                # If connected to a deterministic key, use that Universal ID
                conn_type = IdentifierType(conn['type'])
                if conn_type in [IdentifierType.EMAIL_HASH, IdentifierType.PHONE_NUMBER]:
                    universal_id = self.repo.get_universal_id(conn['identifier'], conn_type)
                    if universal_id:
                        confidence = conn['weight'] * 0.85  # Apply edge weight
                        steps.append(f"graph_traversal:{id_type.value}->{conn_type.value}")
                        return universal_id, confidence, steps
            
            steps.append(f"{id_type.value}_miss:{identifier[:12]}")
        
        return None, 0.0, steps
    
    def _cache_new_identifiers(
        self,
        identifiers: Dict[IdentifierType, str],
        universal_id: str,
        confidence: float
    ) -> None:
        """Cache any identifiers that aren't already cached"""
        for id_type, id_value in identifiers.items():
            cached_id = self.repo.get_universal_id(id_value, id_type)
            if not cached_id:
                self.repo.cache_resolution(id_value, id_type, universal_id, confidence)
