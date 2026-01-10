"""
Timing Service - Core business logic for timing decisions
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import numpy as np
import uuid

from services.feature_service import FeatureService
from services.identity_service import IdentityResolver
from repositories.feature_repository import FeatureRepository
from repositories.explanation_repository import ExplanationRepository
from core.timing_model import ContinuousCurve, MinuteSlotGrid, TimingDecision, MINUTES_PER_WEEK
from core.ml_models import MLModels
from models.requests import TimingRequest


class TimingService:
    """
    Service for generating timing decisions.
    
    Per LLM-spec.md §7: All decisions MUST reference a Universal SendFlowr ID.
    This service resolves identities before making timing decisions.
    """
    
    def __init__(self, 
                 feature_service: FeatureService,
                 identity_resolver: IdentityResolver,
                 feature_repo: FeatureRepository,
                 explanation_repo: ExplanationRepository):
        self.feature_service = feature_service
        self.identity_resolver = identity_resolver
        self.feature_repo = feature_repo
        self.explanation_repo = explanation_repo
        self.ml_models = MLModels()
    
    def generate_timing_decision(self, request: TimingRequest) -> TimingDecision:
        """
        Generate timing decision per spec.json
        
        Per LLM-spec.md §7: Resolves identity to Universal ID before decision.
        Returns TimingDecision with latency-compensated trigger time
        """
        # Step 1: Resolve identity to Universal SendFlowr ID
        universal_id = self._resolve_identity(request)
        
        # Step 2: Get features using Universal ID
        features = self.feature_service.get_or_compute_features(universal_id)
        
        # Reconstruct continuous curve
        curve_probs = np.array(features['click_curve_minutes'], dtype=float)
        adjusted_probs = np.copy(curve_probs)
        applied_weights: List[Dict] = []
        
        # Get context signals (using Universal ID)
        context = self.feature_service.get_context_signals(universal_id)
        
        # Time boundaries
        now = datetime.now(timezone.utc)
        send_after = self._ensure_utc(request.send_after) or now
        send_before = self._ensure_utc(request.send_before) or (now + timedelta(days=7))
        
        current_slot = MinuteSlotGrid.datetime_to_minute_slot(now)
        
        # Apply hot path boost (acceleration)
        hot_path_ctx = context.get('hot_path', {})
        if hot_path_ctx.get('active'):
            weight = self.ml_models.predict_signal_weight(
                signal_type=hot_path_ctx.get('signal', 'hot_path'),
                minutes_ago=0.0,
                default_weight=hot_path_ctx.get('weight', 0.0)
            )
            applied_weights.append({
                "signal": hot_path_ctx.get('signal', 'hot_path'),
                "weight": round(weight, 4)
            })
            # Apply exponential decay boost to next 60 minutes
            for minute_offset in range(0, 60):
                slot_idx = (current_slot + minute_offset) % MINUTES_PER_WEEK
                decay = np.exp(-minute_offset / 15.0)
                adjusted_probs[slot_idx] *= (1 + weight * decay)
        
        curve = ContinuousCurve(adjusted_probs)
        
        # Find optimal minute slot within constraints
        send_after_slot = MinuteSlotGrid.datetime_to_minute_slot(send_after)
        send_before_slot = MinuteSlotGrid.datetime_to_minute_slot(send_before)
        
        if send_before_slot > send_after_slot:
            valid_slots = range(send_after_slot, send_before_slot)
        else:
            # Wraps around week boundary
            valid_slots = list(range(send_after_slot, MINUTES_PER_WEEK)) + list(range(0, send_before_slot))
        
        if not valid_slots:
            raise ValueError("No valid minute slots within the provided window")
        
        # Check for circuit breaker suppression
        suppressed_ctx = context.get('suppressed', {})
        suppressed = suppressed_ctx.get('active', False)
        debug_suppressed = False
        
        if suppressed:
            suppression_until = suppressed_ctx.get('until') or (now + timedelta(hours=1))
            suppression_until = max(suppression_until, send_after)
            if suppression_until > send_before:
                raise ValueError("Recipient is under circuit breaker suppression for the requested window")
            
            best_slot = MinuteSlotGrid.datetime_to_minute_slot(suppression_until)
            target_datetime = suppression_until
            confidence_score = 0.0
            applied_weights.append({
                "signal": suppressed_ctx.get('reason', 'circuit_breaker'),
                "weight": -1.0
            })
            debug_suppressed = True
        else:
            # ML-based suppression probability (soft guardrail)
            sup_prob = self.ml_models.suppression_probability(context)
            if sup_prob > 0.8:
                suppressed = True
                suppressed_ctx = {'reason': 'ml_suppression_risk', 'until': now + timedelta(hours=1), 'active': True}
                applied_weights.append({"signal": "ml_suppression_risk", "weight": -1.0})
            
            if suppressed:
                suppression_until = suppressed_ctx.get('until') or (now + timedelta(hours=1))
                suppression_until = max(suppression_until, send_after)
                if suppression_until > send_before:
                    raise ValueError("Recipient is under circuit breaker suppression for the requested window")
                
                best_slot = MinuteSlotGrid.datetime_to_minute_slot(suppression_until)
                target_datetime = suppression_until
                confidence_score = 0.0
                debug_suppressed = True
            else:
                # Find best slot by probability
                best_slot = max(valid_slots, key=lambda s: curve.get_probability(s))
            
                # Upgrade #6: Decision-Level Confidence
                # Combine curve sharpness with peak probability
                curve_confidence = curve.get_confidence_score()
                peak_probability = curve.get_probability(best_slot)
                
                # Decision confidence = curve confidence × peak probability
                # This prevents overconfident flat curves
                raw_confidence = curve_confidence * peak_probability
                confidence_score = self.ml_models.calibrate_confidence(
                    raw_confidence,
                    sample_size=features.get('click_count_30d', 0)
                )
            
            # Convert slot to datetime
            reference_time = max(now, send_after)
            reference_slot = MinuteSlotGrid.datetime_to_minute_slot(reference_time)
            slots_ahead = (best_slot - reference_slot) % MINUTES_PER_WEEK
            target_datetime = reference_time + timedelta(minutes=slots_ahead)
        
        # Latency prediction (override default if possible)
        predicted_latency = self.ml_models.predict_latency(
            esp=None,
            event_time=now,
            default_latency_seconds=request.latency_estimate_seconds
        )
        
        # Calculate trigger time accounting for latency
        trigger_datetime = target_datetime - timedelta(seconds=predicted_latency)
        
        # Ensure trigger is in the future
        while trigger_datetime < now:
            target_datetime += timedelta(days=7)
            trigger_datetime = target_datetime - timedelta(seconds=predicted_latency)
        
        # Generate decision
        decision = TimingDecision(
            decision_id=str(uuid.uuid4()),
            universal_id=universal_id,  # ← Use resolved Universal ID
            target_minute_utc=best_slot,
            trigger_timestamp_utc=trigger_datetime,
            latency_estimate_seconds=predicted_latency,
            confidence_score=confidence_score,
            model_version="minute_level_click_based",
            explanation_ref=f"explain:{universal_id}:{best_slot}",
            base_curve_peak_minute=int(np.argmax(curve.probabilities)),
            applied_weights=applied_weights,
            suppressed=debug_suppressed
        )
        
        # Cache decision
        self.feature_repo.cache_decision(universal_id, decision.decision_id, decision.to_dict())
        
        # Store explanation
        try:
            self._store_explanation(decision, context)
            print(f"✅ Stored explanation for decision {decision.decision_id}")
        except Exception as e:
            import traceback
            print(f"⚠️ Failed to store explanation for {decision.decision_id}: {e}")
            print(traceback.format_exc())
        
        return decision
    
    def _store_explanation(self, decision: TimingDecision, context: Dict):
        """Persist explanation to ClickHouse"""
        suppressed_ctx = context.get('suppressed', {})
        hot_path_ctx = context.get('hot_path', {})
        
        self.explanation_repo.store_explanation(
            decision_id=decision.decision_id,
            explanation_ref=decision.explanation_ref,
            universal_id=decision.universal_id,
            target_minute=decision.target_minute_utc,
            trigger_timestamp=decision.trigger_timestamp_utc,
            latency_estimate_seconds=decision.latency_estimate_seconds,
            confidence_score=decision.confidence_score,
            model_version=decision.model_version,
            base_curve_peak_minute=decision.debug.get('base_curve_peak_minute') or 0,
            applied_weights=decision.debug.get('applied_weights', []),
            suppressed=decision.debug.get('suppressed', False),
            suppression_reason=suppressed_ctx.get('reason'),
            suppression_until=suppressed_ctx.get('until'),
            hot_path_signal=hot_path_ctx.get('signal'),
            hot_path_weight=float(hot_path_ctx.get('weight') or 0.0)
        )
    
    def _resolve_identity(self, request: TimingRequest) -> str:
        """
        Resolve identity to Universal SendFlowr ID.
        
        Per LLM-spec.md §7: All decisions MUST reference a Universal SendFlowr ID.
        
        Priority:
        1. If universal_id provided → use it directly (already resolved)
        2. If email/phone/ESP IDs provided → resolve via IdentityResolver
        3. Otherwise → error
        """
        # Fast path: universal_id already provided
        if request.universal_id:
            print(f"✅ Using pre-resolved universal_id: {request.universal_id}")
            return request.universal_id
        
        # Build identity map from request
        identifiers = {}
        
        if request.email:
            identifiers['email'] = request.email
        if request.phone:
            identifiers['phone'] = request.phone
        if request.klaviyo_id:
            identifiers['klaviyo_id'] = request.klaviyo_id
        if request.shopify_customer_id:
            identifiers['shopify_customer_id'] = request.shopify_customer_id
        if request.esp_user_id:
            identifiers['esp_user_id'] = request.esp_user_id
        
        # If identity keys provided, resolve them
        if identifiers:
            resolution = self.identity_resolver.resolve(identifiers)
            print(f"🔗 Resolved identity: {resolution.universal_id} (confidence: {resolution.confidence_score:.2f})")
            print(f"   Steps: {' → '.join(resolution.resolution_steps)}")
            return resolution.universal_id
        
        raise ValueError("Must provide either 'universal_id' or identity keys (email, phone, klaviyo_id, etc.)")
    
    @staticmethod
    def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime is UTC timezone-aware"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
