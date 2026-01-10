-- ClickHouse email_events table
CREATE TABLE IF NOT EXISTS sendflowr.email_events
(
    event_id String,
    event_type LowCardinality(String),
    timestamp DateTime64(3, 'UTC'),
    esp LowCardinality(String),
    universal_id String,
    recipient_email_hash String,
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
ORDER BY (esp, universal_id, timestamp, event_type)
PRIMARY KEY (esp, universal_id, timestamp)
SETTINGS index_granularity = 8192;
