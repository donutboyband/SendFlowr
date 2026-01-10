"""
SendFlowr Timing Model - Minute-Level Resolution

This module implements the canonical 10,080 minute-slot time grid
and continuous probability curve primitives per the Timing Layer spec.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta, timezone
from scipy.interpolate import interp1d
from scipy.ndimage import gaussian_filter1d

# Constants from spec
MINUTES_PER_WEEK = 10_080
MINUTES_PER_HOUR = 60
MINUTES_PER_DAY = 1_440


class MinuteSlotGrid:
    """Canonical 10,080 minute-slot time grid"""
    
    @staticmethod
    def datetime_to_minute_slot(dt: datetime) -> int:
        """
        Convert datetime to canonical minute slot (0-10079)
        Slot 0 = Monday 00:00 UTC
        """
        # Get day of week (0=Monday, 6=Sunday)
        day_of_week = dt.weekday()
        # Get minutes since start of day
        minutes_in_day = dt.hour * 60 + dt.minute
        # Calculate slot
        slot = day_of_week * MINUTES_PER_DAY + minutes_in_day
        return slot % MINUTES_PER_WEEK
    
    @staticmethod
    def minute_slot_to_datetime(slot: int, reference_week_start: datetime) -> datetime:
        """
        Convert minute slot back to datetime using a reference week
        """
        if not 0 <= slot < MINUTES_PER_WEEK:
            raise ValueError(f"Slot must be 0-10079, got {slot}")
        
        return reference_week_start + timedelta(minutes=slot)
    
    @staticmethod
    def slot_to_readable(slot: int) -> str:
        """Convert slot to human-readable format: Day HH:MM"""
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        day_idx = slot // MINUTES_PER_DAY
        minutes_in_day = slot % MINUTES_PER_DAY
        hour = minutes_in_day // 60
        minute = minutes_in_day % 60
        return f"{day_names[day_idx]} {hour:02d}:{minute:02d}"


class ContinuousCurve:
    """
    Continuous probability curve over 10,080 minute slots
    
    Per spec: "Timing intent is represented as a continuous probability function.
    Discrete histograms MAY be used only as priors or cold-start fallbacks."
    """
    
    def __init__(self, minute_probabilities: np.ndarray):
        """
        Initialize curve with minute-level probabilities
        
        Args:
            minute_probabilities: Array of length 10,080 with probabilities
        """
        if len(minute_probabilities) != MINUTES_PER_WEEK:
            raise ValueError(f"Expected {MINUTES_PER_WEEK} probabilities, got {len(minute_probabilities)}")
        
        # Normalize to sum to 1.0
        total = np.sum(minute_probabilities)
        if total > 0:
            self.probabilities = minute_probabilities / total
        else:
            # Uniform fallback
            self.probabilities = np.ones(MINUTES_PER_WEEK) / MINUTES_PER_WEEK
        
        # Create interpolation function for arbitrary minute queries
        self._interpolator = interp1d(
            np.arange(MINUTES_PER_WEEK),
            self.probabilities,
            kind='cubic',
            fill_value='extrapolate'
        )
    
    def get_probability(self, minute_slot: int) -> float:
        """Get probability for exact minute slot"""
        return float(self.probabilities[minute_slot % MINUTES_PER_WEEK])
    
    def interpolate(self, minute_offset: float) -> float:
        """
        Interpolate probability at arbitrary minute offset
        
        Supports fractional minutes for sub-minute precision
        """
        return float(self._interpolator(minute_offset % MINUTES_PER_WEEK))
    
    def find_peak_window(self, window_minutes: int = 120, top_k: int = 3) -> List[Tuple[int, float]]:
        """
        Find optimal send windows
        
        Returns list of (start_slot, avg_probability) tuples
        """
        windows = []
        
        for start_slot in range(MINUTES_PER_WEEK):
            end_slot = (start_slot + window_minutes) % MINUTES_PER_WEEK
            
            if end_slot > start_slot:
                window_probs = self.probabilities[start_slot:end_slot]
            else:
                # Handle wrap around week boundary
                window_probs = np.concatenate([
                    self.probabilities[start_slot:],
                    self.probabilities[:end_slot]
                ])
            
            avg_prob = np.mean(window_probs)
            windows.append((start_slot, avg_prob))
        
        # Sort by probability and return top K
        windows.sort(key=lambda x: x[1], reverse=True)
        return windows[:top_k]
    
    def get_confidence_score(self) -> float:
        """
        Calculate confidence score based on curve sharpness
        
        Higher entropy = lower confidence (flat curve)
        Lower entropy = higher confidence (peaked curve)
        """
        # Calculate normalized entropy
        probs = self.probabilities[self.probabilities > 0]
        entropy = -np.sum(probs * np.log(probs))
        max_entropy = np.log(MINUTES_PER_WEEK)
        
        # Invert: sharp curves have high confidence
        confidence = 1.0 - (entropy / max_entropy)
        return float(confidence)
    
    @classmethod
    def from_hourly_histogram(cls, hour_hist: Dict[int, float]) -> 'ContinuousCurve':
        """
        Create continuous curve from legacy hourly histogram (fallback)
        
        Per spec: "Hourly buckets are treated as derived projections only."
        """
        # Initialize minute array
        minute_probs = np.zeros(MINUTES_PER_WEEK)
        
        # Expand hourly buckets to minutes (each hour = 60 minutes)
        for hour in range(24):
            prob = hour_hist.get(hour, 0.0)
            # Repeat for each day of week
            for day in range(7):
                start_slot = day * MINUTES_PER_DAY + hour * 60
                minute_probs[start_slot:start_slot + 60] = prob / 60.0
        
        # Apply smoothing to create continuous curve
        smoothed = gaussian_filter1d(minute_probs, sigma=30, mode='wrap')
        
        return cls(smoothed)
    
    @classmethod
    def from_click_events(cls, click_timestamps: List[datetime], 
                         sigma_minutes: int = 60,
                         recency_half_life_hours: float = 72.0) -> 'ContinuousCurve':
        """
        Build continuous curve from click events with recency weighting
        
        Per spec: "Clicks, conversions, replies, and real-time activity 
        dominate all inference."
        
        Upgrade #1: Recency-weighted curves
        - Recent clicks weighted higher (exponential decay)
        - Default half-life: 3 days (72 hours)
        - Prevents old behavior from polluting current intent
        """
        if not click_timestamps:
            # No clicks - return uniform distribution
            return cls(np.ones(MINUTES_PER_WEEK) / MINUTES_PER_WEEK)
        
        # Get current time for recency calculation
        now = datetime.now(timezone.utc)
        
        # Convert timestamps to minute slots with recency weights
        minute_counts = np.zeros(MINUTES_PER_WEEK)
        
        for ts in click_timestamps:
            # Ensure timezone aware
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)
            
            # Calculate age in hours
            age_hours = (now - ts).total_seconds() / 3600
            
            # Exponential decay weight (half-life)
            # weight = exp(-age_hours * ln(2) / half_life)
            weight = np.exp(-age_hours * np.log(2) / recency_half_life_hours)
            
            # Add weighted click to slot
            slot = MinuteSlotGrid.datetime_to_minute_slot(ts)
            minute_counts[slot] += weight
        
        # Apply Gaussian smoothing for continuity
        smoothed = gaussian_filter1d(minute_counts, sigma=sigma_minutes, mode='wrap')
        
        # Add small uniform prior (Laplace smoothing)
        smoothed += 0.001
        
        return cls(smoothed)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class TimingDecision:
    """
    Canonical timing decision output per spec.json
    
    This is the primary output of the Timing Layer.
    """
    
    def __init__(
        self,
        decision_id: str,
        universal_id: str,
        target_minute_utc: int,
        trigger_timestamp_utc: datetime,
        latency_estimate_seconds: float,
        confidence_score: float,
        model_version: str,
        explanation_ref: str,
        base_curve_peak_minute: Optional[int] = None,
        applied_weights: Optional[List[Dict]] = None,
        suppressed: bool = False
    ):
        self.decision_id = decision_id
        self.universal_id = universal_id
        self.target_minute_utc = target_minute_utc
        self.trigger_timestamp_utc = _ensure_utc(trigger_timestamp_utc)
        self.latency_estimate_seconds = latency_estimate_seconds
        self.confidence_score = confidence_score
        self.model_version = model_version
        self.explanation_ref = explanation_ref
        self.created_at_utc = datetime.now(timezone.utc)
        
        # Debug payload
        self.debug = {
            'base_curve_peak_minute': base_curve_peak_minute,
            'applied_weights': applied_weights or [],
            'suppressed': suppressed
        }
    
    def to_dict(self) -> dict:
        """Export as canonical JSON per spec.json"""
        return {
            'decision_id': self.decision_id,
            'universal_id': self.universal_id,
            'target_minute_utc': self.target_minute_utc,
            'trigger_timestamp_utc': self.trigger_timestamp_utc.isoformat().replace('+00:00', 'Z'),
            'latency_estimate_seconds': self.latency_estimate_seconds,
            'confidence_score': self.confidence_score,
            'model_version': self.model_version,
            'explanation_ref': self.explanation_ref,
            'created_at_utc': self.created_at_utc.isoformat().replace('+00:00', 'Z'),
            'debug': self.debug
        }


if __name__ == "__main__":
    # Example: Create minute-level curve from legacy hour data
    hour_hist = {9: 0.15, 10: 0.12, 14: 0.10, 18: 0.20, 19: 0.15}
    
    curve = ContinuousCurve.from_hourly_histogram(hour_hist)
    
    # Find optimal windows
    windows = curve.find_peak_window(window_minutes=120, top_k=3)
    
    print("Top 3 Send Windows (Minute-Level):")
    for slot, prob in windows:
        readable = MinuteSlotGrid.slot_to_readable(slot)
        print(f"  {readable} - Probability: {prob:.4f}")
    
    print(f"\nConfidence Score: {curve.get_confidence_score():.3f}")
    
    # Test interpolation
    print(f"\nInterpolation test:")
    print(f"  Minute 540 (Mon 09:00): {curve.get_probability(540):.6f}")
    print(f"  Minute 540.5 (interpolated): {curve.interpolate(540.5):.6f}")
