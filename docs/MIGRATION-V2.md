# SendFlowr v2.0 - Timing Layer Migration Guide

## What Changed

SendFlowr has been refactored from traditional **Send Time Optimization (STO)** to a **Timing Intelligence Layer** with minute-level precision.

### Before (v1.0 - STO)
- Hour-level resolution (24 buckets)
- Discrete histograms
- Open-rate focused
- ESP-coupled execution
- "Best hour" recommendations

### After (v2.0 - Timing Layer)
- **Minute-level resolution** (10,080 slots/week)
- **Continuous probability curves**
- **Click/conversion focused** (MPP resilient)
- **Latency-aware triggers**
- **Precise timestamp outputs**

## Core Changes

### 1. Time Model: Minute-Level Grid

**Old (Hourly)**:
```python
hour_histogram = {
    9: 0.15,   # 9 AM
    10: 0.12,  # 10 AM
    18: 0.20   # 6 PM
}
```

**New (Minute-Level)**:
```python
# 10,080 minute slots (Mon 00:00 = slot 0, Sun 23:59 = slot 10079)
curve = ContinuousCurve(minute_probabilities)  # numpy array of 10,080 floats

# Get probability at exact minute
prob = curve.get_probability(540)  # Monday 9:00 AM

# Interpolate at sub-minute precision
prob = curve.interpolate(540.5)  # Monday 9:00:30 AM
```

### 2. Signal Priority: Clicks Over Opens

**Old**: Optimized for email opens
```python
compute_hourly_histogram(recipient_id, event_type='opened')
```

**New**: Optimizes for clicks (MPP resilient)
```python
compute_minute_level_curve(recipient_id, event_type='clicked')
```

Per spec: *"Opens are weak signals. Clicks, conversions, replies dominate all inference."*

### 3. Output: TimingDecision (not Prediction)

**Old Response**:
```json
{
  "recipient_id": "user_003",
  "optimal_windows": [
    {"start": "2026-01-10T15:00:00", "end": "2026-01-10T17:00:00"}
  ],
  "peak_hours": [16, 11, 18]
}
```

**New Response (spec.json compliant)**:
```json
{
  "decision_id": "uuid-here",
  "universal_user_id": "user_003",
  "target_minute_utc": 8618,
  "trigger_timestamp_utc": "2026-01-10T23:33:17Z",
  "latency_estimate_seconds": 300,
  "confidence_score": 0.84,
  "model_version": "minute_level_v2.0_click_based",
  "explanation_ref": "explain:user_003:8618"
}
```

### 4. Latency Awareness

**Old**: Assumed immediate delivery
```python
send_time = target_hour
```

**New**: Compensates for ESP latency
```python
trigger_time = target_minute - latency_estimate
```

Example:
- Target delivery: Friday 3:00 PM (minute slot 6660)
- ESP latency: 5 minutes (300 seconds)
- **Trigger time**: Friday 2:55 PM

## API Migration

### New Primary Endpoint: `/timing-decision`

```bash
curl -X POST http://localhost:8001/timing-decision \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_id": "user_003",
    "latency_estimate_seconds": 300,
    "send_after": "2026-01-10T00:00:00Z",
    "send_before": "2026-01-17T00:00:00Z"
  }'
```

Response includes:
- `target_minute_utc`: Canonical minute slot (0-10079)
- `trigger_timestamp_utc`: When to fire the send (latency-adjusted)
- `confidence_score`: 0-1 based on curve sharpness
- `debug.base_curve_peak_minute`: Where curve peaks
- `explanation_ref`: Link to explainability data

### Legacy Endpoint: `/predict` (STO Fallback)

Still supported for backwards compatibility:

```bash
curl -X POST http://localhost:8001/predict \
  -H "Content-Type: application/json" \
  -d '{"recipient_id": "user_003", "hours_ahead": 24}'
```

Returns hourly recommendation (degraded precision).

## Feature Store Changes

### v1.0 Features
```json
{
  "hour_histogram_24": {0: 0.02, 1: 0.01, ..., 23: 0.05},
  "weekday_histogram_7": {0: 0.15, ..., 6: 0.10},
  "open_count_30d": 45
}
```

### v2.0 Features
```json
{
  "version": "2.0_minute_level",
  "click_curve_minutes": [0.0001, 0.0001, ..., 0.0003],  // 10,080 floats
  "curve_confidence": 0.84,
  "peak_windows": [
    {"minute_slot": 8618, "readable": "Fri 23:38", "probability": 0.0012}
  ],
  "click_count_30d": 29,
  "click_count_7d": 12,
  "click_count_1d": 3,
  "hour_histogram_24": {...}  // Still included for fallback
}
```

## Minute Slot Reference

```
Minute Slot 0     = Monday 00:00 UTC
Minute Slot 60    = Monday 01:00 UTC
Minute Slot 1440  = Tuesday 00:00 UTC
Minute Slot 10079 = Sunday 23:59 UTC
```

Formula:
```python
slot = (day_of_week * 1440) + (hour * 60) + minute
```

Helper:
```python
from timing_model import MinuteSlotGrid

slot = MinuteSlotGrid.datetime_to_minute_slot(datetime.now())
readable = MinuteSlotGrid.slot_to_readable(slot)  # "Mon 14:35"
```

## Running v2.0

### Start the API
```bash
cd src/SendFlowr.Inference
source venv/bin/activate
pip install scipy  # New dependency
python -m uvicorn main_v2:app --reload --port 8001
```

### Compute Minute-Level Features
```bash
curl -X POST http://localhost:8001/compute-features
```

### Get Timing Decision
```bash
curl -X POST http://localhost:8001/timing-decision \
  -H "Content-Type: application/json" \
  -d '{"recipient_id": "user_003", "latency_estimate_seconds": 300}'
```

## Backwards Compatibility

✅ **Hour-level STO preserved**
- `/predict` endpoint still works
- `hour_histogram_24` still computed
- Can run v1 and v2 in parallel

✅ **Gradual migration**
- Clients can use v1 while testing v2
- No breaking changes to existing integrations
- Feature flags to toggle minute-level precision

## What's Still Needed

Per the Timing Layer spec, these modules are planned but not yet implemented:

- [ ] **Latency Tracker**: Real-time ESP latency measurement
- [ ] **Contextual Signals**: Hot paths & circuit breakers
- [ ] **Universal ID**: Cross-channel identity resolution
- [ ] **Shadow Segmentation**: Burst traffic prevention
- [ ] **Explainability UI**: Decision audit logs

## Key Principles (from spec)

1. **Minute-level is canonical** - Hour buckets are projections only
2. **Clicks over opens** - MPP killed open rate optimization
3. **Latency always exists** - Never assume instant delivery
4. **ESPs are replaceable** - No ESP-specific logic in core
5. **Explainable decisions** - Every output must be reconstructable

## Testing

```bash
# Test v2 API
cd /Users/donut/Dev/SendFlowr
./scripts/run-inference-pipeline.sh  # Update needed for v2

# Compare v1 vs v2
curl http://localhost:8000/predict ...  # v1.0 hourly
curl http://localhost:8001/timing-decision ...  # v2.0 minute-level
```

## Migration Checklist

- [x] Minute-level time grid (10,080 slots)
- [x] Continuous probability curves
- [x] Click-based feature computation
- [x] TimingDecision schema compliance
- [x] Latency-aware trigger calculation
- [x] Backwards compatible API
- [ ] Update scheduler to consume TimingDecision
- [ ] Latency tracker module
- [ ] Contextual signal processing
- [ ] Universal ID resolution
- [ ] Migration from v1 to v2 in production

## Questions?

See:
- `LLM-Ref/LLM-spec.md` - Core specification
- `LLM-Ref/LLM-negative-spec.md` - Anti-patterns
- `LLM-Ref/spec.json` - TimingDecision schema
