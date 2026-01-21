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
*Detailed Plan*:  
1. **Telemetry instrumentation** – record each send and its matching delivery with fields: `esp`, `campaign_type`, `payload_size_bytes`, `queue_depth_estimate`, `send_timestamp`, `delivery_timestamp`, and derived `latency_seconds`. Write this into a materialized view like `sendflowr.latency_training_mv` so the training script can query a single source.  
2. **Model training script** – run `scripts/train_latency_model.py` (or similar) that pulls the MV, filters outliers, engineers the same features used by inference (ESP one-hot, time-of-day flags, payload/queue buckets), and fits a tree-based regressor. Persist the artifact plus feature order to `models/latency_model.pkl`.  
3. **Inference integration** – update `core/ml_models.MLModels` to load the pickled model, build the feature vector with `_feature_vector`, and return the predicted latency; fallback to the existing heuristic when the artifact is missing.  
4. **Canary loop** – periodically send diagnostic messages through each ESP to capture controlled latency samples; write those back into the same telemetry table for ongoing calibration.  
5. **Monitoring** – store predicted vs actual latency in `timing_explanations` so you can monitor MAE/RMSE and trigger retraining when drift exceeds thresholds.  
6. **Retraining cadence** – schedule the training script nightly or on-demand when new telemetry is available, and deploy the new `models/latency_model.pkl` via your restart/reload process.

### 2. Signal Weight Learning
*Problem*: Hard-coded hot-path decay assumes universality.  
*ML Role*: Learn ω values per signal_type/brand/segment using supervised models trained on historical lift (open/click probability increase).  
*Input features*: signal_type, minutes_since_signal, brand_id, user_segment, recency counts, channel.  
*Output*: predicted uplift weight that multiplies the base curve (`1 + ω`).  
*Plan*:  
  - Label training examples: when hot path fired vs baseline outcome.  
  - Train simple regression (e.g., tree-based) per signal_type or aggregated.  
  - Use inference API to call weight predictor before `ContinuousCurve` adjustments.  
*Detailed Plan*:  
1. **Data capture** – surface each hot-path signal in a dedicated ClickHouse table (e.g., `sendflowr.signal_events`). Keep `email_events` focused on canonical send/delivery data while `signal_events` stores `signal_type`, `universal_id`, `timestamp`, `provider`, `brand`, `base_probability`, `minutes_since_signal`, and a boolean indicating a downstream high-fidelity outcome (click/open) within a follow-up window (15/30 minutes).  
2. **Label construction** – join those rows with downstream `email_events` to compute the realized uplift (e.g., `max(click_in_window, open_in_window)` minus baseline probability). Store that as the regression target `ω_target`.  
3. **Training script** – build `scripts/train_signal_weight_model.py` that engineers features (signal_type, recency buckets, brand_id, segment, channel, suppression context) and fits a LightGBM/XGBoost regressor. Persist the model plus the feature order to `models/signal_weight_model.pkl`.  
4. **Inference integration** – extend `core/ml_models.MLModels.predict_signal_weight` to load the serialized model and reuse the same feature pipeline so `TimingService` consumes the ML-generated `weight` instead of the decay heuristic when the artifact exists.  
5. **Monitoring** – log both predicted `ω` and observed lift inside `timing_explanations.applied_weights` (and optionally a metrics table) so you can prove the ML weight improves outcomes.  
6. **Retraining cadence** – refresh the artifact weekly or when concept drift is detected (the same pipeline can be scheduled whenever new signal/outcome data flows into ClickHouse).

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

> See `docs/thoughts.md` for the full operational roadmap (canary loop, shadow segments, KPIs) that contextualizes these ML feedback loops and keeps the architecture aligned.
