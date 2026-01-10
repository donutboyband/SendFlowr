# SendFlowr ML Support Systems Spec

## Purpose
Detail the machine learning systems that augment (but never replace) the Timing Layer “physics,” ensuring SendFlowr stays explainable, portable, and deterministic while still learning from data.

## Guiding Principle
ML should supply calibrated inputs—latency estimates, signal weights, confidence reliability, priors, and suppression likelihood—into the core minute-level decision engine (`LLM-Ref/spec.json`). The decision logic (continuous curves, rule-based guards) remains code-first; ML sits above it as sensor/forecasting services.

## ML Capabilities and Implementation Plan

### 1. Latency Prediction
*Problem*: A static latency offset ignores ESP/queue variation.  
*ML Role*: Train a regression (GBDT or temporal fusion) that predicts delivery latency from `(ESP, hour_of_day, day_of_week, payload_size, campaign_type, queue_depth)` using historical telemetry.  
*Integration*: The prediction feeds `latency_estimate_seconds` in `/timing-decision`; accuracy can be measured by comparing predicted vs actual delivery timestamps logged via `timing_explanations`.  
*Plan*:  
  - Collect telemetry tables from ClickHouse consumer logs (include delivery timestamp).  
  - Train daily, export weights as a service or incremental model.  
  - Provide API that returns latency per request context.  

### 2. Signal Weight Learning
*Problem*: Hard-coded hot-path decay assumes universality.  
*ML Role*: Learn ω values per signal_type/brand/segment using supervised models trained on historical lift (open/click probability increase).  
*Input features*: signal_type, minutes_since_signal, brand_id, user_segment, recency counts, channel.  
*Output*: predicted uplift weight that multiplies the base curve (`1 + ω`).  
*Plan*:  
  - Label training examples: when hot path fired vs baseline outcome.  
  - Train simple regression (e.g., tree-based) per signal_type or aggregated.  
  - Use inference API to call weight predictor before `ContinuousCurve` adjustments.  

### 3. Confidence Calibration
*Problem*: Entropy-derived score is symbolic; we need reliability.  
*ML Role*: Learn mapping `confidence_score → realized lift` so that SendFlowr’s confidence matches empirical performance.  
*Plan*:  
  - Collect decision outcomes (did send outperform average?).  
  - Train isotonic regression or calibration model.  
  - Adjust served `confidence_score` and surface in `/explanations`.

### 4. Cold-Start Prior Estimation
*Problem*: Uniform priors are suboptimal for new users.  
*ML Role*: Predict minute-level prior curve from cohort features (industry, timezone, geography, device mix).  
*Plan*:  
  - Cluster historical users into chronotypes.  
  - Train a model that outputs a coarse histogram or parametric curve per cohort.  
  - Use when `ContinuousCurve` has no data (before any events).

### 5. Suppression Likelihood
*Problem*: Rule-based circuit breakers are brittle.  
*ML Role*: Predict probability that a user is “annoyed” or suppressed, based on support tickets, complaint rate, recency, sentiment.  
*Plan*:  
  - Build classifier using labeled suppression outcomes.  
  - Use probability to override decisions when risk exceeds threshold (monitored via CA metrics).

### 6. Segment Pattern Discovery
*Problem*: Fixed personas miss seasonal drift.  
*ML Role*: Discover behavioral clusters (chronotypes) and feed them as priors/overrides.  
*Plan*:  
  - Use clustering on click/open timing, update segmentation weekly.  
  - Feed segment assignments into `signal weight` and `cold-start` models.

## Data Contracts & Explainability
- Every ML output is logged in `timing_explanations` under `applied_weights`, `confidence`, and `suppression` fields with `explanation_ref`.  
- Latency predictions, weight contributions, and suppression scores should be auditable.

## Operational Notes
- Retrain latency and weight models nightly; deploy versioned inference APIs.  
- Cache ML predictions near the inference service (Redis) for low latency, invalidating when models rotate.  
- Monitor drift via holdout cohorts and track `confidence` accuracy metrics.
