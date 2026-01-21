-- Migration: Add ML Training Feature Columns
-- Per ML-SPEC.md §1: Latency Prediction Model
-- Date: 2026-01-11

-- Add latency training features to email_events table
ALTER TABLE sendflowr.email_events 
ADD COLUMN IF NOT EXISTS latency_seconds Nullable(Int32) COMMENT 'Delivery latency in seconds (send → delivered)',
ADD COLUMN IF NOT EXISTS send_time Nullable(DateTime64(3, 'UTC')) COMMENT 'Original send timestamp for latency calculation',
ADD COLUMN IF NOT EXISTS hour_of_day Nullable(Int8) COMMENT 'Hour of send time (0-23) for ML features',
ADD COLUMN IF NOT EXISTS minute Nullable(Int8) COMMENT 'Minute of send time (0-59) for ML features',
ADD COLUMN IF NOT EXISTS day_of_week Nullable(Int8) COMMENT 'Day of week (0=Mon, 6=Sun) for ML features',
ADD COLUMN IF NOT EXISTS campaign_type LowCardinality(Nullable(String)) COMMENT 'Campaign type: transactional, promotional',
ADD COLUMN IF NOT EXISTS payload_size_bytes Nullable(Int32) COMMENT 'Email payload size in bytes',
ADD COLUMN IF NOT EXISTS queue_depth_estimate Nullable(Int32) COMMENT 'Estimated ESP queue depth at send time';

-- Create materialized view for latency training data
-- Use coalesce to avoid nulls in ORDER BY
CREATE MATERIALIZED VIEW IF NOT EXISTS sendflowr.latency_training_mv
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (esp, timestamp)
POPULATE
AS SELECT 
    timestamp,
    esp,
    campaign_id,
    campaign_type,
    hour_of_day,
    minute,
    day_of_week,
    payload_size_bytes,
    queue_depth_estimate,
    latency_seconds,
    send_time,
    universal_id
FROM sendflowr.email_events
WHERE event_type = 'delivered' 
  AND latency_seconds IS NOT NULL
  AND latency_seconds > 0;

-- Index for fast ML feature queries
CREATE INDEX IF NOT EXISTS idx_campaign_type ON sendflowr.email_events (campaign_type) TYPE bloom_filter GRANULARITY 1;
