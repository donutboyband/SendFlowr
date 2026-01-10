"""
SendFlowr ML Support Systems

These helpers implement lightweight, explainable ML-style predictors that
augment the timing physics without owning the decision logic. They should be
easy to replace with true trained models later; current implementations are
deterministic heuristics that mirror the ML-SPEC.md contracts.
"""

from __future__ import annotations

from typing import Dict, Optional
from datetime import datetime, timezone
import math
import numpy as np

from timing_model import MINUTES_PER_WEEK


class MLModels:
    """Container for pluggable ML predictors used by the inference service."""

    def predict_latency(
        self,
        *,
        esp: Optional[str],
        event_time: datetime,
        payload_bytes: Optional[int] = None,
        default_latency_seconds: float = 300.0,
    ) -> float:
        """
        Predict ESP latency (seconds).

        Heuristic implementation:
        - Base on default_latency_seconds
        - Penalize top-of-hour congestion
        - Penalize morning/evening batch windows
        - Cap to 15 minutes
        """
        latency = default_latency_seconds
        hour = event_time.hour
        minute = event_time.minute

        # Top-of-hour congestion
        if minute in (0, 1, 2):
            latency *= 1.8

        # Morning/evening batch pressure
        if hour in (8, 9, 18, 19):
            latency *= 1.5

        # Tiny adjustment for payload size, if known
        if payload_bytes:
            latency *= 1.0 + min(payload_bytes / (1024 * 1024 * 2), 0.2)  # up to +20% for large payloads

        return float(min(latency, 900.0))

    def predict_signal_weight(
        self,
        *,
        signal_type: str,
        minutes_ago: float,
        brand: Optional[str] = None,
        segment: Optional[str] = None,
        default_weight: float = 0.0,
    ) -> float:
        """
        Predict contextual weight (ω) for a signal.

        Heuristic implementation:
        - Use exponential decay based on minutes_ago
        - Adjust weight by signal_type defaults
        """
        base = default_weight
        if signal_type in ("site_visit", "product_view"):
            base = 1.2
        elif signal_type in ("sms_click", "push_click"):
            base = 1.5
        elif signal_type:
            base = 1.0

        decay = math.exp(-minutes_ago / 15.0) if minutes_ago is not None else 1.0
        return float(base * decay)

    def calibrate_confidence(self, raw_confidence: float, sample_size: int = 0) -> float:
        """
        Calibrate entropy-derived confidence into a reliability-aware score.

        Heuristic: shrink extreme values toward mean when sample size is small.
        """
        if sample_size <= 0:
            return float(max(0.0, min(1.0, raw_confidence * 0.85)))

        shrink = 1.0 / (1.0 + math.exp(-sample_size / 50.0))
        calibrated = (raw_confidence * shrink) + (0.5 * (1 - shrink))
        return float(max(0.0, min(1.0, calibrated)))

    def generate_cold_start_curve(self, cohort_features: Dict) -> np.ndarray:
        """
        Produce a non-uniform cold-start prior based on cohort hints.

        Heuristic: blend a morning and evening bump; adjust for timezone or industry hints if provided.
        """
        curve = np.ones(MINUTES_PER_WEEK, dtype=float)

        # Morning bump (8-10am)
        for day in range(7):
            start = day * 1440 + 8 * 60
            curve[start : start + 120] *= 1.4

        # Evening bump (6-9pm)
        for day in range(7):
            start = day * 1440 + 18 * 60
            curve[start : start + 180] *= 1.6

        # Weekend adjustment
        for day in (5, 6):  # Sat, Sun
            start = day * 1440
            curve[start : start + 1440] *= 1.1

        return curve

    def suppression_probability(self, context: Dict) -> float:
        """
        Estimate suppression likelihood.

        Heuristic: if an active circuit breaker exists, return high probability; otherwise low.
        """
        suppressed = context.get("suppressed", {})
        if suppressed.get("active"):
            return 0.95
        return 0.05
