-- Postgres schema for connector metadata and configuration

CREATE TABLE IF NOT EXISTS esp_accounts (
    id SERIAL PRIMARY KEY,
    esp VARCHAR(50) NOT NULL,
    account_id VARCHAR(255) NOT NULL,
    account_name VARCHAR(255),
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(esp, account_id)
);

CREATE TABLE IF NOT EXISTS backfill_progress (
    id SERIAL PRIMARY KEY,
    esp_account_id INTEGER REFERENCES esp_accounts(id) ON DELETE CASCADE,
    backfill_start TIMESTAMP WITH TIME ZONE NOT NULL,
    backfill_end TIMESTAMP WITH TIME ZONE,
    cursor TEXT,
    events_processed INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'in_progress',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS webhook_events (
    id SERIAL PRIMARY KEY,
    esp VARCHAR(50) NOT NULL,
    event_id VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    received_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    UNIQUE(esp, event_id)
);

CREATE INDEX idx_webhook_status ON webhook_events(status, received_at);
CREATE INDEX idx_backfill_account ON backfill_progress(esp_account_id, status);
