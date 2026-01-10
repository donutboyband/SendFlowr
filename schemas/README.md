# SendFlowr Database Schemas

This directory contains canonical database schemas for SendFlowr.

## Schema Files

### ClickHouse Schemas

**Main Tables:**
- **`clickhouse-schema.sql`** - Email events table
  - `email_events` - Primary event store (sent, delivered, opened, clicked, bounced)
  - `email_events_deduped` - Materialized view for deduplication

- **`clickhouse-explanations.sql`** - Timing decision explanations
  - `timing_explanations` - Stores timing decision metadata and audit trail

- **`clickhouse-identity.sql`** - Identity resolution tables (NEW)
  - `identity_graph` - Bidirectional edges between identifiers
  - `identity_audit_log` - Resolution step tracking (compliance)
  - `resolved_identities` - Universal ID mapping cache

### Other Schemas

- **`canonical-event.json`** - JSON schema for event payloads
- **`postgres-schema.sql`** - PostgreSQL schema (future use)

---

## Table Relationships

```
┌─────────────────────────────────────────────────────────────┐
│  Identity Resolution Layer                                  │
├─────────────────────────────────────────────────────────────┤
│  identity_graph                                             │
│    ├─ email_hash ←→ klaviyo_id                             │
│    ├─ phone_number ←→ shopify_customer_id                  │
│    └─ email_hash ←→ phone_number                           │
│                                                             │
│  resolved_identities (cache)                                │
│    ├─ email_hash → sf_abc123                               │
│    ├─ klaviyo_id → sf_abc123                               │
│    └─ phone_number → sf_abc123                             │
│                                                             │
│  identity_audit_log (compliance)                            │
│    └─ Tracks every resolution step                         │
└─────────────────────────────────────────────────────────────┘
                         ↓ 
                  Resolve at Ingestion
                         ↓
┌─────────────────────────────────────────────────────────────┐
│  Event Storage Layer (RESOLVED DATA)                        │
├─────────────────────────────────────────────────────────────┤
│  email_events                                               │
│    ├─ recipient_id (original: email, phone, etc.)         │
│    └─ universal_id (RESOLVED: sf_abc123) ← PRIMARY   │
│                                                             │
│  timing_explanations                                        │
│    └─ universal_id (from email_events)                │
└─────────────────────────────────────────────────────────────┘

NOTE: Identity resolution happens BEFORE storage.
      All queries use universal_id for unified view.
```

---

## Initialization

### Quick Start

```bash
# Initialize all tables
./scripts/init-clickhouse-schema.sh
```

### Manual Initialization

```bash
# Create database
docker exec -i sendflowr-clickhouse clickhouse-client --query "
CREATE DATABASE IF NOT EXISTS sendflowr
"

# Create email events
docker exec -i sendflowr-clickhouse clickhouse-client < schemas/clickhouse-schema.sql

# Create timing explanations
docker exec -i sendflowr-clickhouse clickhouse-client < schemas/clickhouse-explanations.sql

# Create identity resolution tables
docker exec -i sendflowr-clickhouse clickhouse-client < schemas/clickhouse-identity.sql
```

### Verify Tables

```bash
docker exec -i sendflowr-clickhouse clickhouse-client --query "
SHOW TABLES FROM sendflowr
"

# Expected output:
# email_events
# email_events_deduped
# identity_audit_log
# identity_graph
# resolved_identities
# timing_explanations
```

---

## Schema Details

### `email_events`

**Purpose:** Primary event store for all email-related events

**Key Fields:**
- `event_id` - Unique event identifier
- `recipient_id` - Original identifier (email, phone, etc.) **for audit trail**
- `universal_user_id` - **Resolved Universal SendFlowr ID (PRIMARY)** ← Query this!
- `event_type` - sent, delivered, opened, clicked, bounced, complained, unsubscribed
- `timestamp` - When event occurred (UTC)
- `esp` - Email service provider (klaviyo, sendgrid, etc.)

**Critical Design Decision:**
- Identity is resolved **BEFORE** storage (at webhook ingestion time)
- `recipient_id` preserved for audit trail (what was originally provided)
- `universal_user_id` used for all queries (unified cross-platform view)
- Same person using multiple identifiers = single `universal_user_id`

**Example:**
```sql
-- Alice used 3 different identifiers:
recipient_id           universal_user_id   events
alice@example.com  →   sf_abc123           45
alice@gmail.com    →   sf_abc123           23
+14155551234       →   sf_abc123           12

-- Query by Universal ID to get ALL events for Alice:
SELECT * FROM email_events 
WHERE universal_user_id = 'sf_abc123'  -- Returns all 80 events!
```

**Partitioning:** By month (`PARTITION BY toYYYYMM(timestamp)`)

**Ordering:** `(esp, universal_user_id, timestamp, event_type)` ← Indexed by Universal ID

**Use Cases:**
- Click-based engagement modeling (unified across all user's identifiers)
- Feature computation for timing decisions
- Hot path detection (recent site visits, SMS clicks)
- Circuit breaker detection (complaints, support tickets)
- Cross-platform analytics (email + SMS + Shopify unified)

---

### `timing_explanations`

**Purpose:** Audit trail for timing decisions

**Key Fields:**
- `decision_id` - UUID for this decision
- `universal_user_id` - Resolved Universal SendFlowr ID
- `target_minute` - Minute slot (0-10079)
- `trigger_timestamp_utc` - When to trigger send
- `confidence_score` - Model confidence (0-1)
- `applied_weights` - JSON array of hot path/circuit breaker weights
- `suppressed` - Whether send was suppressed

**Ordering:** `(universal_user_id, created_at_utc)`

**Use Cases:**
- Decision explainability
- Debugging timing issues
- A/B testing analysis
- Compliance auditing

---

### `identity_graph`

**Purpose:** Stores relationships between identifiers for cross-platform stitching

**Key Fields:**
- `identifier_a`, `identifier_type_a` - First identifier (e.g., email_hash)
- `identifier_b`, `identifier_type_b` - Second identifier (e.g., klaviyo_id)
- `weight` - 1.0 = deterministic, < 1.0 = probabilistic
- `source` - Where this link came from (e.g., 'klaviyo_webhook')

**Engine:** `ReplacingMergeTree(updated_at)` - Idempotent edge insertion

**Ordering:** `(identifier_a, identifier_b)`

**Use Cases:**
- Probabilistic identity resolution
- Graph traversal (klaviyo_id → email_hash → universal_id)
- Cross-platform user stitching

**Per LLM-spec.md §7:**
- Deterministic keys: email_hash, phone_number (weight = 1.0)
- Probabilistic keys: klaviyo_id, shopify_customer_id, etc. (weight < 1.0)

---

### `identity_audit_log`

**Purpose:** Compliance-grade audit trail for identity resolution

**Key Fields:**
- `resolution_id` - UUID for this resolution attempt
- `universal_id` - Resolved Universal SendFlowr ID
- `input_identifier` - What was provided
- `resolution_step` - How resolution happened (e.g., 'graph_traversal:klaviyo_id->email_hash')
- `confidence_score` - Resolution confidence

**Engine:** `MergeTree()` - Append-only for compliance

**Ordering:** `(universal_id, created_at)`

**Use Cases:**
- GDPR compliance (right to explanation)
- Debugging identity resolution issues
- Security auditing

**Per LLM-spec.md §7.3:**
- "Resolution steps MUST be auditable" ✅

---

### `resolved_identities`

**Purpose:** Cache of identifier → Universal ID mappings for fast lookups

**Key Fields:**
- `identifier` - Email hash, phone, klaviyo_id, etc.
- `identifier_type` - Type of identifier
- `universal_id` - Universal SendFlowr ID
- `confidence_score` - Resolution confidence
- `last_seen` - Last time this identifier was resolved

**Engine:** `ReplacingMergeTree(last_seen)` - Updates on re-resolution

**Ordering:** `(identifier, identifier_type)`

**Use Cases:**
- Fast path for repeated resolutions (< 2ms)
- Avoid graph traversal on every request
- Cache invalidation via `last_seen`

---

## Identifier Types

Per `src/SendFlowr.Inference/core/identity_model.py`:

### Deterministic (weight = 1.0)
- `email_hash` - SHA-256 of normalized email
- `phone_number` - E.164 normalized phone

### Probabilistic (weight < 1.0)
- `klaviyo_id` - Klaviyo user ID (0.95)
- `shopify_customer_id` - Shopify customer ID (0.90)
- `esp_user_id` - Generic ESP user ID (0.85)
- `ip_device_signature` - IP + user agent (0.50)

---

## Data Retention

### Current Policy (Default)

**email_events:**
- Retention: Unlimited (for model training)
- Partitioning: Monthly (for efficient TTL later)
- Recommendation: Add 90-day TTL for GDPR compliance

**timing_explanations:**
- Retention: Unlimited
- Recommendation: Add 30-day TTL for GDPR compliance

**identity_graph:**
- Retention: Unlimited (graph edges persist)
- Recommendation: User-initiated deletion only

**identity_audit_log:**
- Retention: Unlimited (compliance audit trail)
- Recommendation: Add 90-day TTL (balance compliance vs. privacy)

**resolved_identities:**
- Retention: Auto-refresh on re-resolution
- `last_seen` updated on every resolution
- Stale entries cleaned up automatically

### GDPR-Compliant Policy (Optional)

```sql
-- Add TTL to audit log
ALTER TABLE sendflowr.identity_audit_log
MODIFY TTL created_at + INTERVAL 30 DAY;

-- Add TTL to email events
ALTER TABLE sendflowr.email_events
MODIFY TTL timestamp + INTERVAL 90 DAY;

-- Add TTL to timing explanations
ALTER TABLE sendflowr.timing_explanations
MODIFY TTL created_at_utc + INTERVAL 30 DAY;
```

---

## Migration from Legacy

### Migrating to Universal ID Storage

**CRITICAL:** Existing `email_events` data only has `recipient_id`, not `universal_user_id`.

**Step 1:** Add column (already done via schema update)
```sql
ALTER TABLE sendflowr.email_events
ADD COLUMN universal_user_id String DEFAULT '';
```

**Step 2:** Backfill existing data
```bash
# Resolve all recipient_ids to universal_user_ids
./scripts/backfill-universal-ids.sh
```

**Step 3:** Verify backfill
```sql
SELECT 
    countIf(universal_user_id != '') as resolved,
    countIf(universal_user_id = '') as unresolved,
    count() as total
FROM sendflowr.email_events;

-- Expected after backfill:
-- resolved: 67538, unresolved: 0
```

**Step 4:** Update webhook handlers
```python
# OLD (wrong):
event = {
    'recipient_id': email,
    ...
}

# NEW (correct):
resolution = identity_resolver.resolve({'email': email})
event = {
    'recipient_id': email,           # Keep for audit
    'universal_user_id': resolution.universal_id,  # Use for queries
    ...
}
```

See `UNIVERSAL-ID-STORAGE.md` for complete migration guide.

### Database Prefix Migration

If you have existing tables without `sendflowr.` prefix:

```sql
-- Rename tables to include database prefix
RENAME TABLE email_events TO sendflowr.email_events;
RENAME TABLE timing_explanations TO sendflowr.timing_explanations;
```

---

## Backup & Recovery

### Export Schema

```bash
# Export all schemas
for table in email_events timing_explanations identity_graph identity_audit_log resolved_identities; do
  docker exec -i sendflowr-clickhouse clickhouse-client --query "
    SHOW CREATE TABLE sendflowr.$table
  " > schemas/backup/${table}_$(date +%Y%m%d).sql
done
```

### Export Data

```bash
# Export identity graph (small, safe to export)
docker exec -i sendflowr-clickhouse clickhouse-client --query "
  SELECT * FROM sendflowr.identity_graph
  FORMAT CSVWithNames
" > backups/identity_graph_$(date +%Y%m%d).csv

# Export resolved identities cache
docker exec -i sendflowr-clickhouse clickhouse-client --query "
  SELECT * FROM sendflowr.resolved_identities
  FORMAT CSVWithNames
" > backups/resolved_identities_$(date +%Y%m%d).csv
```

### Disaster Recovery

If you need to rebuild `universal_user_id` mappings:

```bash
# 1. Truncate resolved_identities cache
docker exec -i sendflowr-clickhouse clickhouse-client --query "
  TRUNCATE TABLE sendflowr.resolved_identities
"

# 2. Re-run backfill
./scripts/backfill-universal-ids.sh

# 3. Verify
docker exec -i sendflowr-clickhouse clickhouse-client --query "
  SELECT COUNT(*) FROM sendflowr.email_events WHERE universal_user_id != ''
"
```

---

## Spec Compliance

✅ **LLM-spec.md §7.1**: All decisions reference Universal SendFlowr ID  
✅ **LLM-spec.md §7.2**: Deterministic + Probabilistic resolution keys  
✅ **LLM-spec.md §7.3**: Idempotent merges, auditable steps  
✅ **LLM-spec.md §8.1**: SendFlowr owns identity resolution  

---

## Important Notes

### Universal ID Storage Architecture

⚠️ **CRITICAL DESIGN DECISION:** `email_events` stores **RESOLVED** universal_user_id, not raw recipient_id.

**Why this matters:**
- ✅ Same person with multiple identifiers = single `universal_user_id`
- ✅ Cross-platform analytics (email + SMS + Shopify unified)
- ✅ Higher confidence scores (more training data per user)
- ✅ Spec-compliant (LLM-spec.md §7)

**Example:**
```
Alice uses:
  - alice@example.com (45 events)
  - alice@gmail.com (23 events)  
  - +14155551234 (12 events)

Old (wrong): 3 separate users, 3 separate timing decisions
New (correct): 1 user (sf_abc123), 1 timing decision, 80 events
```

See `UNIVERSAL-ID-STORAGE.md` for full architectural explanation.

---

## Support

For questions about schemas:
- **Identity resolution**: See `docs/IDENTITY-RESOLUTION.md`
- **Universal ID storage**: See `UNIVERSAL-ID-STORAGE.md`
- **Connector integration**: See `docs/CONNECTOR-INTEGRATION-GUIDE.md`
- **Specification**: See `LLM-Ref/LLM-spec.md §7`
- **Migration**: See `ARCHITECTURAL-FIX-SUMMARY.md`
