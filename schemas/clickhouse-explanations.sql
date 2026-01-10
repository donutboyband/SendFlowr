-- ClickHouse table for timing decision explanations
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
SETTINGS index_granularity = 8192;
