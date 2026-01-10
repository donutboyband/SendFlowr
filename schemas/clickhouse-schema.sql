CREATE DATABASE IF NOT EXISTS sendflowr;

CREATE TABLE IF NOT EXISTS sendflowr.email_events
(
    event_id String,
    event_type LowCardinality(String),
    timestamp DateTime64(3, 'UTC'),
    esp LowCardinality(String),
    universal_id String,                  -- Resolved Universal SendFlowr ID (PRIMARY)
    recipient_email_hash String,          -- SHA-256 hash of email (privacy-first)
    campaign_id String,
    campaign_name String,
    message_id String,
    subject String,
    click_url String,
    bounce_type LowCardinality(String),
    user_agent String,
    ip_address String,
    metadata String,
    ingested_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (esp, universal_id, timestamp, event_type)  -- Ordered by universal_id
PRIMARY KEY (esp, universal_id, timestamp)
SETTINGS index_granularity = 8192;

-- Dedupe view
CREATE MATERIALIZED VIEW IF NOT EXISTS sendflowr.email_events_deduped
ENGINE = ReplacingMergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (esp, event_id, campaign_id)
AS SELECT *
FROM sendflowr.email_events;

-- Index for fast lookups by universal_id
CREATE INDEX IF NOT EXISTS idx_universal_id ON sendflowr.email_events (universal_id) TYPE bloom_filter GRANULARITY 1;

-- Index for campaign lookups
CREATE INDEX IF NOT EXISTS idx_campaign ON sendflowr.email_events (campaign_id) TYPE bloom_filter GRANULARITY 1;

-- Index for campaign lookups
CREATE INDEX IF NOT EXISTS idx_campaign ON sendflowr.email_events (campaign_id) TYPE bloom_filter GRANULARITY 1;
