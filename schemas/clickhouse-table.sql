-- ClickHouse email_events table
CREATE TABLE IF NOT EXISTS sendflowr.email_events
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
