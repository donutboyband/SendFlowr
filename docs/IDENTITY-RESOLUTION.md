# Identity Resolution System

## Overview

SendFlowr implements a **Universal Identity Resolution**. All timing decisions reference a single **Universal SendFlowr ID** that stitches together identity signals from multiple sources.

## Architecture

### Identity Resolution Contract

**All signals must resolve to a Universal SendFlowr ID.**

#### Primary Deterministic Keys
- **Email** (hashed with SHA-256)
- **Phone number** (normalized to E.164 format)

#### Secondary Probabilistic Keys
- **ESP user IDs** (Klaviyo, Iterable, etc.)
- **Shopify customer_id**
- **IP/device signatures**

#### Resolution Rules
✅ **Merges are idempotent** - Same inputs always return same Universal ID  
✅ **No destructive overwrites** - Identity graph only adds, never removes  
✅ **Resolution steps are auditable** - All decisions logged to `identity_audit_log`

---

## Database Schema

### 1. `identity_graph` Table
Stores relationships between identifiers (bidirectional graph).

```sql
CREATE TABLE identity_graph (
    identifier_a String,
    identifier_type_a LowCardinality(String),
    identifier_b String,
    identifier_type_b LowCardinality(String),
    weight Float32,              -- 1.0 = deterministic, < 1.0 = probabilistic
    source LowCardinality(String), -- e.g., 'klaviyo_webhook', 'shopify_order'
    created_at DateTime,
    updated_at DateTime
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (identifier_a, identifier_b)
```

### 2. `identity_audit_log` Table
Tracks resolution decisions (audit trail per spec §7.3).

```sql
CREATE TABLE identity_audit_log (
    resolution_id String,
    universal_id String,
    input_identifier String,
    input_type LowCardinality(String),
    resolution_step String,
    confidence_score Float32,
    created_at DateTime
)
ENGINE = MergeTree()
ORDER BY (universal_id, created_at)
```

### 3. `resolved_identities` Table
Cache of identifier → Universal ID mappings (fast path).

```sql
CREATE TABLE resolved_identities (
    identifier String,
    identifier_type LowCardinality(String),
    universal_id String,
    confidence_score Float32,
    last_seen DateTime,
    created_at DateTime
)
ENGINE = ReplacingMergeTree(last_seen)
ORDER BY (identifier, identifier_type)
```

---

## Resolution Algorithm

### Step 1: Deterministic Lookup (Fast Path)
1. Hash email → SHA-256
2. Normalize phone → E.164 format
3. Check `resolved_identities` cache
4. If found → return Universal ID (confidence = 1.0)

### Step 2: Probabilistic Graph Traversal
1. Check ESP IDs (klaviyo_id, shopify_customer_id, etc.) in cache
2. If not cached, traverse `identity_graph` using BFS
3. If connected to deterministic key → use that Universal ID
4. Apply edge weight to confidence (e.g., 0.85 for probabilistic match)

### Step 3: Create New Universal ID
1. If no match found → generate new `sf_xxxxxxxxx` ID
2. Cache all provided identifiers
3. Log resolution to audit trail

---

## API Usage

### Timing Decision with Identity Resolution

**Old way (pre-resolved):**
```bash
curl -X POST http://localhost:8001/timing-decision \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_id": "user_12345",
    "send_after": "2026-01-10T00:00:00Z",
    "send_before": "2026-01-17T00:00:00Z"
  }'
```

**New way (automatic resolution):**
```bash
curl -X POST http://localhost:8001/timing-decision \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "klaviyo_id": "k_abc123",
    "send_after": "2026-01-10T00:00:00Z",
    "send_before": "2026-01-17T00:00:00Z"
  }'
```

**Response:**
```json
{
  "decision_id": "abc-123",
  "universal_id": "sf_b8783dbfc0024695",  // ← Resolved automatically
  "target_minute_utc": 7200,
  "trigger_timestamp_utc": "2026-01-16T23:55:00Z",
  "confidence_score": 0.72
}
```

### Explicit Identity Resolution

```bash
curl -X POST "http://localhost:8001/resolve-identity?email=user@example.com&phone=+14155551234"
```

**Response:**
```json
{
  "universal_id": "sf_b8783dbfc0024695",
  "input_identifiers": {
    "email": "user@example.com",
    "phone": "+14155551234"
  },
  "resolved_identifiers": {
    "email_hash": "973dfe463ec85785...",
    "phone_number": "+14155551234",
    "klaviyo_id": "k_abc123"
  },
  "resolution_steps": [
    "found_via_email_hash:973dfe46"
  ],
  "confidence_score": 1.0
}
```

### Link Identifiers (e.g., from webhook)

When you receive a Klaviyo webhook with both email and klaviyo_id:

```bash
curl -X POST "http://localhost:8001/link-identifiers" \
  "?identifier_a=973dfe463ec85785...&type_a=email_hash" \
  "&identifier_b=k_abc123&type_b=klaviyo_id" \
  "&weight=1.0&source=klaviyo_webhook"
```

**Response:**
```json
{
  "status": "linked",
  "identifier_a": "973dfe463ec85785...",
  "identifier_b": "k_abc123",
  "weight": 1.0
}
```

---

## Testing Examples

### Test 1: Create New Identity
```bash
curl -X POST "http://localhost:8001/resolve-identity?email=test@example.com&phone=4155551234"
```

**Expected:** New Universal ID created (e.g., `sf_b8783dbfc0024695`)

### Test 2: Idempotent Resolution
```bash
curl -X POST "http://localhost:8001/resolve-identity?email=test@example.com"
```

**Expected:** Same Universal ID returned (`sf_b8783dbfc0024695`)

### Test 3: Link Klaviyo ID
```bash
curl -X POST "http://localhost:8001/link-identifiers" \
  "?identifier_a=973dfe463ec85785...&type_a=email_hash" \
  "&identifier_b=k_abc123&type_b=klaviyo_id&weight=1.0&source=test"
```

### Test 4: Probabilistic Resolution
```bash
curl -X POST "http://localhost:8001/resolve-identity?klaviyo_id=k_abc123"
```

**Expected:** Same Universal ID via graph traversal (`sf_b8783dbfc0024695`)

### Test 5: Timing Decision with Multiple IDs
```bash
curl -X POST http://localhost:8001/timing-decision \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "klaviyo_id": "k_abc123",
    "send_after": "2026-01-10T00:00:00Z",
    "send_before": "2026-01-17T00:00:00Z"
  }'
```

**Expected:** Single Universal ID used for timing decision

---

## Verification Queries

### Check Audit Log
```sql
SELECT 
    resolution_id,
    universal_id,
    input_type,
    resolution_step,
    confidence_score,
    created_at
FROM sendflowr.identity_audit_log
ORDER BY created_at DESC
LIMIT 20
```

### Check Identity Graph
```sql
SELECT 
    identifier_a,
    identifier_type_a,
    identifier_b,
    identifier_type_b,
    weight,
    source
FROM sendflowr.identity_graph
ORDER BY created_at DESC
```

### Check Resolved Identities Cache
```sql
SELECT 
    identifier,
    identifier_type,
    universal_id,
    confidence_score
FROM sendflowr.resolved_identities
ORDER BY last_seen DESC
```

---

## Confidence Scoring

| Match Type | Method | Confidence |
|------------|--------|------------|
| Email hash exact match | Deterministic cache lookup | 1.0 |
| Phone number exact match | Deterministic cache lookup | 1.0 |
| Klaviyo ID cached | Deterministic cache lookup | 1.0 (if previously linked) |
| Klaviyo ID graph traversal | Probabilistic via identity_graph | 0.85 |
| Shopify customer ID graph | Probabilistic via identity_graph | 0.85 |
| IP/device signature | Probabilistic via identity_graph | 0.50 |

---

## Production Recommendations

### 1. Webhook Integration
When receiving webhooks from Klaviyo, Shopify, etc., call `/link-identifiers` to build the identity graph:

```python
# Example: Klaviyo webhook handler
@app.post("/webhooks/klaviyo")
async def klaviyo_webhook(event: dict):
    email = event.get('data', {}).get('attributes', {}).get('email')
    klaviyo_id = event.get('data', {}).get('id')
    
    if email and klaviyo_id:
        # Hash email
        email_hash = hashlib.sha256(email.lower().encode()).hexdigest()
        
        # Link to identity graph
        requests.post("http://localhost:8001/link-identifiers", params={
            "identifier_a": email_hash,
            "type_a": "email_hash",
            "identifier_b": klaviyo_id,
            "type_b": "klaviyo_id",
            "weight": 1.0,
            "source": "klaviyo_webhook"
        })
```

### 2. Batch Resolution
For existing users, run a batch job to pre-populate the identity graph:

```python
for user in users:
    requests.post("http://localhost:8001/resolve-identity", params={
        "email": user.email,
        "phone": user.phone,
        "klaviyo_id": user.klaviyo_id,
        "shopify_customer_id": user.shopify_id
    })
```

### 3. Monitor Audit Log
Set up alerts for low-confidence resolutions (< 0.5):

```sql
SELECT COUNT(*) FROM sendflowr.identity_audit_log
WHERE confidence_score < 0.5
AND created_at > now() - INTERVAL 1 HOUR
```

---

## Spec Compliance

✅ **LLM-spec.md §7.1**: All decisions reference Universal SendFlowr ID  
✅ **LLM-spec.md §7.2**: Deterministic (email, phone) + Probabilistic (ESP IDs) keys  
✅ **LLM-spec.md §7.3**: Idempotent merges, no destructive overwrites, auditable steps  
✅ **LLM-spec.md §8.1**: SendFlowr owns identity resolution (not delegated to ESP)
