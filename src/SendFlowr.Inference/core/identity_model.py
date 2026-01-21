"""
Identity Resolution Domain Models

Identity Resolution
- Universal SendFlowr ID for all decisions
- Deterministic keys: hashed email, phone
- Probabilistic keys: ESP IDs, customer IDs, device signatures
- Idempotent merges with audit trail
"""

from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum
import hashlib


class IdentifierType(str, Enum):
    """Identity key types per spec §7.2"""
    # Primary (Deterministic)
    EMAIL_HASH = "email_hash"
    PHONE_NUMBER = "phone_number"
    
    # Secondary (Probabilistic)
    ESP_USER_ID = "esp_user_id"
    KLAVIYO_ID = "klaviyo_id"
    SHOPIFY_CUSTOMER_ID = "shopify_customer_id"
    IP_DEVICE_SIGNATURE = "ip_device_signature"
    
    # Internal
    UNIVERSAL_ID = "universal_id"


class IdentityEdge:
    """
    Represents a link between two identifiers.
    Edge weight determines confidence: 1.0 = deterministic, < 1.0 = probabilistic
    """
    def __init__(
        self,
        identifier_a: str,
        identifier_type_a: IdentifierType,
        identifier_b: str,
        identifier_type_b: IdentifierType,
        weight: float,
        source: str,
        created_at: datetime = None
    ):
        self.identifier_a = identifier_a
        self.identifier_type_a = identifier_type_a
        self.identifier_b = identifier_b
        self.identifier_type_b = identifier_type_b
        self.weight = weight  # 1.0 = deterministic, < 1.0 = probabilistic
        self.source = source  # e.g., "klaviyo_webhook", "shopify_order"
        self.created_at = created_at or datetime.utcnow()


class IdentityResolution:
    """
    Result of identity resolution process.
    Contains Universal ID and audit trail of resolution steps.
    """
    def __init__(
        self,
        universal_id: str,
        input_identifiers: Dict[str, str],
        resolved_identifiers: Dict[str, str],
        resolution_steps: List[str],
        confidence_score: float
    ):
        self.universal_id = universal_id
        self.input_identifiers = input_identifiers  # What was provided
        self.resolved_identifiers = resolved_identifiers  # All known identifiers
        self.resolution_steps = resolution_steps  # Audit trail
        self.confidence_score = confidence_score  # 1.0 = deterministic, < 1.0 = probabilistic
        self.resolved_at = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        return {
            'universal_id': self.universal_id,
            'input_identifiers': self.input_identifiers,
            'resolved_identifiers': self.resolved_identifiers,
            'resolution_steps': self.resolution_steps,
            'confidence_score': self.confidence_score,
            'resolved_at': self.resolved_at.isoformat()
        }


class IdentityHelper:
    """Utility functions for identity normalization"""
    
    @staticmethod
    def hash_email(email: str) -> str:
        """Hash email for deterministic matching"""
        normalized = email.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize phone to E.164 format (basic)"""
        # Remove all non-digits
        digits = ''.join(c for c in phone if c.isdigit())
        
        # Add +1 if US number without country code
        if len(digits) == 10:
            return f"+1{digits}"
        elif len(digits) == 11 and digits[0] == '1':
            return f"+{digits}"
        else:
            return f"+{digits}"
    
    @staticmethod
    def generate_universal_id() -> str:
        """Generate new Universal SendFlowr ID"""
        from uuid import uuid4
        return f"sf_{uuid4().hex[:16]}"
