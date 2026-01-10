-- ClickHouse Identity Resolution Tables
-- Per LLM-spec.md §7: Identity Resolution

-- Database setup
CREATE DATABASE IF NOT EXISTS sendflowr;

-- 1. Identity Graph: Stores relationships between identifiers
--    Used for probabilistic resolution via graph traversal
CREATE TABLE IF NOT EXISTS sendflowr.identity_graph
(
    identifier_a String,
    identifier_type_a LowCardinality(String),  -- 'email_hash', 'phone_number', 'klaviyo_id', etc.
    identifier_b String,
    identifier_type_b LowCardinality(String),
    weight Float32,                            -- 1.0 = deterministic, < 1.0 = probabilistic
    source LowCardinality(String),             -- 'klaviyo_webhook', 'shopify_order', 'manual', etc.
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (identifier_a, identifier_b)
SETTINGS index_granularity = 8192;

-- Index for reverse lookups (identifier_b -> identifier_a)
CREATE INDEX IF NOT EXISTS idx_identifier_b 
ON sendflowr.identity_graph (identifier_b) 
TYPE bloom_filter GRANULARITY 1;

-- 2. Identity Audit Log: Tracks all resolution decisions
--    Per LLM-spec §7.3: "Resolution steps MUST be auditable"
CREATE TABLE IF NOT EXISTS sendflowr.identity_audit_log
(
    resolution_id String,                      -- UUID for this resolution attempt
    universal_id String,                       -- Resolved Universal SendFlowr ID
    input_identifier String,                   -- What was provided (email, phone, etc.)
    input_type LowCardinality(String),        -- Type of input identifier
    resolution_step String,                    -- e.g., 'found_via_email_hash', 'graph_traversal:klaviyo_id->email_hash'
    confidence_score Float32,                  -- 1.0 = deterministic, < 1.0 = probabilistic
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
ORDER BY (universal_id, created_at)
SETTINGS index_granularity = 8192;

-- Index for resolution ID lookups
CREATE INDEX IF NOT EXISTS idx_resolution_id 
ON sendflowr.identity_audit_log (resolution_id) 
TYPE bloom_filter GRANULARITY 1;

-- 3. Resolved Identities: Cache of identifier -> Universal ID mappings
--    Fast path for already-resolved identities
CREATE TABLE IF NOT EXISTS sendflowr.resolved_identities
(
    identifier String,                         -- Email hash, phone number, klaviyo_id, etc.
    identifier_type LowCardinality(String),   -- Type of identifier
    universal_id String,                       -- Universal SendFlowr ID (sf_xxxxxxxx)
    confidence_score Float32,                  -- Confidence of this resolution
    last_seen DateTime DEFAULT now(),          -- Last time this identifier was resolved
    created_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(last_seen)
ORDER BY (identifier, identifier_type)
SETTINGS index_granularity = 8192;

-- Index for Universal ID lookups (reverse direction)
CREATE INDEX IF NOT EXISTS idx_universal_id 
ON sendflowr.resolved_identities (universal_id) 
TYPE bloom_filter GRANULARITY 1;

-- Comments on design choices:
-- 
-- identity_graph:
--   - ReplacingMergeTree ensures idempotent edge insertion (no duplicates)
--   - Bidirectional edges stored as single row (query both directions)
--   - Weight field allows deterministic (1.0) vs probabilistic (< 1.0) classification
--
-- identity_audit_log:
--   - Append-only MergeTree for compliance (cannot modify history)
--   - Stores complete resolution path for debugging and compliance
--   - No TTL by default (add TTL for GDPR compliance if needed)
--
-- resolved_identities:
--   - ReplacingMergeTree with last_seen for cache freshness
--   - Speeds up repeated resolutions (no graph traversal needed)
--   - Updated on every resolution to refresh last_seen
