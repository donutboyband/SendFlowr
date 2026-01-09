-- ClickHouse schema for email events

CREATE DATABASE IF NOT EXISTS sendflowr;

USE sendflowr;

CREATE TABLE IF NOT EXISTS email_events
(
    event_id String,
    event_type LowCardinality(String),
    timestamp DateTime64(3, 'UTC'),
    esp LowCardinality(String),
    recipient_id String,
    recipient_email String,
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
ORDER BY (esp, recipient_id, timestamp, event_type)
PRIMARY KEY (esp, recipient_id, timestamp)
SETTINGS index_granularity = 8192;

-- Dedupe view
CREATE MATERIALIZED VIEW IF NOT EXISTS email_events_deduped
ENGINE = ReplacingMergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (esp, event_id, campaign_id)
AS SELECT *
FROM email_events;

-- Index for fast lookups by recipient
CREATE INDEX IF NOT EXISTS idx_recipient ON email_events (recipient_id) TYPE bloom_filter GRANULARITY 1;

-- Index for campaign lookups
CREATE INDEX IF NOT EXISTS idx_campaign ON email_events (campaign_id) TYPE bloom_filter GRANULARITY 1;
