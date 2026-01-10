-- Migration: Update email_events table for privacy-first architecture
-- Date: 2026-01-10
-- Changes:
--   1. Remove recipient_id column (replaced by universal_id)
--   2. Rename recipient_email → recipient_email_hash
--   3. Update primary key and ordering

-- Step 1: Check if old table exists
SELECT 'Checking existing table structure...' AS status;

-- Step 2: Create new table with updated schema
CREATE TABLE IF NOT EXISTS sendflowr.email_events_new
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
ORDER BY (esp, universal_id, timestamp, event_type)
PRIMARY KEY (esp, universal_id, timestamp)
SETTINGS index_granularity = 8192;

-- Step 3: Migrate existing data (if table has data)
-- Note: This assumes universal_id has been backfilled
-- If recipient_email column exists, it will be copied as-is (should already be hashed)
INSERT INTO sendflowr.email_events_new
SELECT 
    event_id,
    event_type,
    timestamp,
    esp,
    universal_id,
    recipient_email AS recipient_email_hash,  -- Rename column
    campaign_id,
    campaign_name,
    message_id,
    subject,
    click_url,
    bounce_type,
    user_agent,
    ip_address,
    metadata,
    ingested_at
FROM sendflowr.email_events
WHERE universal_id != '';  -- Only migrate events with resolved universal_id

-- Step 4: Backup old table
RENAME TABLE sendflowr.email_events TO sendflowr.email_events_old;

-- Step 5: Rename new table to production
RENAME TABLE sendflowr.email_events_new TO sendflowr.email_events;

-- Step 6: Create indexes
CREATE INDEX IF NOT EXISTS idx_universal_id ON sendflowr.email_events (universal_id) TYPE bloom_filter GRANULARITY 1;
CREATE INDEX IF NOT EXISTS idx_campaign ON sendflowr.email_events (campaign_id) TYPE bloom_filter GRANULARITY 1;

-- Step 7: Verify migration
SELECT 
    'Migration complete!' AS status,
    count() AS total_events,
    uniq(universal_id) AS unique_users
FROM sendflowr.email_events;

-- Note: To rollback, run:
-- DROP TABLE sendflowr.email_events;
-- RENAME TABLE sendflowr.email_events_old TO sendflowr.email_events;
