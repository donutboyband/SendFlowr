# Connector Integration Guide

## Overview

This guide explains how to add new connectors (ESPs, ecommerce platforms, support systems) to SendFlowr's identity resolution and hot path systems.

Every new connector requires **two integration points**:

1. **Identity Resolution** - How to stitch this platform's user IDs to Universal SendFlowr ID
2. **Hot Path Signals** - Whether events from this platform should accelerate or suppress sends

---

## Part 1: Identity Resolution Integration

### Decision Framework: Deterministic vs Probabilistic

**Ask yourself:** *"Does this identifier uniquely belong to exactly ONE person, forever?"*

#### ✅ Deterministic (weight = 1.0, confidence = 1.0)

Use when the identifier is **cryptographically unique** or **guaranteed 1:1 with a person**.

**Criteria:**
- Cannot be shared between people
- Cannot be reassigned to a different person
- Persists for the lifetime of the relationship

**Examples:**
- ✅ Email address (one email = one inbox)
- ✅ Phone number (one number = one device, mostly)
- ✅ OAuth `sub` claim from Google/Apple/Facebook
- ✅ Government ID hash (SSN, passport)

#### ⚠️ Probabilistic (weight < 1.0, confidence < 1.0)

Use when the identifier **might be shared** or **might change ownership**.

**Confidence Levels:**

| Source Type | Weight | Use When | Examples |
|-------------|--------|----------|----------|
| **ESP User ID** | 0.95 | Stable platform ID, rarely changes | Klaviyo k_id, Iterable user_id |
| **Ecommerce Customer** | 0.90 | Platform customer ID | Shopify customer_id, BigCommerce customer_id |
| **Payment Platform** | 0.85 | Payment customer ID | Stripe customer_id, PayPal payer_id |
| **Support System** | 0.80 | Ticket/user ID | Zendesk user_id, Intercom user_id |
| **Device ID** | 0.70 | Mobile app device ID | iOS identifierForVendor, Android ad_id |
| **Cookie/Session** | 0.50 | Browser cookie | Session cookie, analytics cookie |
| **IP Address** | 0.30 | Network identifier | IPv4/IPv6 address |
| **Browser Fingerprint** | 0.40 | Device signature | Canvas fingerprint, WebGL signature |

---

## Adding a New Connector: Step-by-Step

### Example: Adding Postscript (SMS Platform)

**Analysis:**
- Platform: SMS marketing (like Klaviyo but for SMS)
- Identifier: `subscriber_id` (e.g., `ps_sub_abc123`)
- Deterministic? **NO** - subscriber IDs can be reassigned if phone changes
- Weight: **0.90** (high confidence, similar to Klaviyo)
- Link via: `phone_number` (when available from webhook)

---

### Step 1: Add to `IdentifierType` Enum

**File:** `src/SendFlowr.Inference/core/identity_model.py`

```python
class IdentifierType(str, Enum):
    """Identity key types per spec §7.2"""
    # Primary (Deterministic)
    EMAIL_HASH = "email_hash"
    PHONE_NUMBER = "phone_number"
    
    # Secondary (Probabilistic)
    ESP_USER_ID = "esp_user_id"
    KLAVIYO_ID = "klaviyo_id"
    SHOPIFY_CUSTOMER_ID = "shopify_customer_id"
    POSTSCRIPT_SUBSCRIBER_ID = "postscript_subscriber_id"  # ← ADD THIS
    IP_DEVICE_SIGNATURE = "ip_device_signature"
    
    # Internal
    UNIVERSAL_ID = "universal_id"
```

---

### Step 2: Update Request Model

**File:** `src/SendFlowr.Inference/models/requests.py`

```python
class TimingRequest(BaseModel):
    # ... existing fields ...
    
    postscript_subscriber_id: Optional[str] = Field(
        None,
        description="Postscript SMS subscriber ID (probabilistic key)",
        example="ps_sub_abc123"
    )
```

---

### Step 3: Update Identity Normalization

**File:** `src/SendFlowr.Inference/services/identity_service.py`

```python
def _normalize_identifiers(self, raw_identifiers: Dict[str, str]):
    normalized = {}
    
    # ... existing code ...
    
    # Add Postscript subscriber ID
    if 'postscript_subscriber_id' in raw_identifiers and raw_identifiers['postscript_subscriber_id']:
        normalized[IdentifierType.POSTSCRIPT_SUBSCRIBER_ID] = raw_identifiers['postscript_subscriber_id']
    
    return normalized
```

---

### Step 4: Configure Resolution Priority

**File:** `src/SendFlowr.Inference/services/identity_service.py`

Update the `_probabilistic_lookup()` method to include the new identifier in priority order:

```python
def _probabilistic_lookup(self, identifiers):
    steps = []
    
    # Try ESP/platform IDs in order of reliability
    probabilistic_order = [
        IdentifierType.KLAVIYO_ID,              # 0.95
        IdentifierType.POSTSCRIPT_SUBSCRIBER_ID, # 0.90 ← ADD HERE (high priority)
        IdentifierType.SHOPIFY_CUSTOMER_ID,     # 0.90
        IdentifierType.ESP_USER_ID,             # 0.85
        IdentifierType.IP_DEVICE_SIGNATURE      # 0.50
    ]
    
    # ... rest of method ...
```

**Priority Guidelines:**
- Higher weight = earlier in list
- Deterministic keys (email, phone) are tried first automatically
- Order within same weight doesn't matter much

---

### Step 5: Create Webhook Handler

**File:** `src/SendFlowr.Connectors/PostscriptWebhookHandler.cs` (or equivalent)

When receiving webhooks from Postscript, link the subscriber ID to phone number:

```python
# Example Python webhook handler
@app.post("/webhooks/postscript")
async def postscript_webhook(event: dict):
    """
    Example Postscript webhook payload:
    {
      "type": "subscriber.created",
      "data": {
        "id": "ps_sub_abc123",
        "phone": "+14155551234",
        "email": "user@example.com",
        "opted_in_at": "2026-01-10T00:00:00Z"
      }
    }
    """
    subscriber = event.get('data', {})
    postscript_id = subscriber.get('id')
    phone = subscriber.get('phone')
    email = subscriber.get('email')
    
    if not postscript_id:
        return {"error": "No subscriber ID"}
    
    # Link phone → postscript_id (deterministic edge)
    if phone:
        normalized_phone = IdentityHelper.normalize_phone(phone)
        
        requests.post("http://localhost:8001/link-identifiers", params={
            "identifier_a": normalized_phone,
            "type_a": "phone_number",
            "identifier_b": postscript_id,
            "type_b": "postscript_subscriber_id",
            "weight": 1.0,  # Deterministic (phone is deterministic)
            "source": "postscript_webhook"
        })
    
    # Link email → postscript_id (deterministic edge)
    if email:
        email_hash = IdentityHelper.hash_email(email)
        
        requests.post("http://localhost:8001/link-identifiers", params={
            "identifier_a": email_hash,
            "type_a": "email_hash",
            "identifier_b": postscript_id,
            "type_b": "postscript_subscriber_id",
            "weight": 1.0,  # Deterministic (email is deterministic)
            "source": "postscript_webhook"
        })
    
    return {"status": "linked"}
```

**Key Points:**
- Always link to **deterministic keys** (email, phone) when available
- Edge weight is 1.0 because the connection itself is deterministic
- The `postscript_subscriber_id` becomes probabilistic when resolved WITHOUT phone/email

---

### Step 6: Test Identity Resolution

```bash
# Test 1: Resolve with phone (should work immediately)
curl -X POST "http://localhost:8001/resolve-identity?phone=+14155551234&postscript_subscriber_id=ps_sub_abc123"

# Test 2: Link the IDs via webhook simulation
curl -X POST "http://localhost:8001/link-identifiers" \
  "?identifier_a=+14155551234&type_a=phone_number" \
  "&identifier_b=ps_sub_abc123&type_b=postscript_subscriber_id" \
  "&weight=1.0&source=postscript_webhook"

# Test 3: Resolve with ONLY postscript ID (probabilistic)
curl -X POST "http://localhost:8001/resolve-identity?postscript_subscriber_id=ps_sub_abc123"

# Expected: Same Universal ID via graph traversal
```

---

## Part 2: Hot Path & Circuit Breaker Integration

### Decision Framework: Accelerate vs Suppress

**Ask yourself:** *"When this event happens, should we send SOONER or send LATER (or not at all)?"*

#### 🚀 Hot Path (Acceleration)

**Use when:** The event indicates **immediate interest** or **high engagement intent**

**Characteristics:**
- Event happened recently (last 5-30 minutes)
- User is actively engaged right now
- Sending now has higher chance of conversion

**Examples:**
- ✅ Site visit (browsing your website)
- ✅ Product view (looking at specific item)
- ✅ Cart abandonment (just added to cart)
- ✅ SMS link click (engaged via SMS)
- ✅ App opened (mobile engagement)
- ✅ Search performed (looking for something)

**Effect:** Multiply probability by weight for next 60 minutes with exponential decay

**Formula:**
```python
boost_weight = 2.0 * exp(-minutes_ago / 15.0)
adjusted_prob[slot] *= (1 + boost_weight)
```

#### 🛑 Circuit Breaker (Suppression)

**Use when:** The event indicates **frustration**, **fatigue**, or **opt-out intent**

**Characteristics:**
- User is annoyed, frustrated, or disengaged
- Sending now will damage relationship
- Need cooling-off period

**Examples:**
- ✅ Support ticket created (customer is frustrated)
- ✅ Complaint submitted (explicit negative feedback)
- ✅ Unsubscribe request (wants out)
- ✅ Spam report (very bad signal)
- ✅ Multiple bounces (deliverability issue)
- ✅ Survey negative response (dissatisfied)

**Effect:** Suppress sends for N hours (48h - 7 days depending on severity)

**Suppression Windows:**
- Support ticket: 48 hours
- Complaint: 48 hours
- Unsubscribe request: 7 days (168 hours)
- Spam report: Permanent (never send)

---

### Adding Hot Path: Example - Product View Event

**Scenario:** Shopify sends webhook when customer views a product

**File:** `src/SendFlowr.Inference/services/feature_service.py`

```python
def get_context_signals(self, recipient_id: str) -> Dict:
    # Hot path signals (last 30 minutes)
    hot_path_signals = [
        'site_visit',
        'sms_click',
        'product_view',      # ← ADD THIS
        'cart_add',          # ← ADD THIS
        'search_performed'   # ← ADD THIS
    ]
    
    hot_path = self.event_repo.get_context_signals(
        recipient_id,
        event_types=hot_path_signals,
        hours_back=0.5  # 30 minutes
    )
    
    # ... rest of method ...
```

**Webhook Handler:**

```python
@app.post("/webhooks/shopify/product_view")
async def shopify_product_view(event: dict):
    """
    Shopify product view event
    """
    customer_email = event.get('customer', {}).get('email')
    product_id = event.get('product', {}).get('id')
    viewed_at = event.get('created_at')
    
    if customer_email:
        # Store event in ClickHouse
        clickhouse.execute("""
            INSERT INTO sendflowr.email_events (
                recipient_id, event_type, event_timestamp_utc,
                metadata
            ) VALUES
        """, [{
            'recipient_id': customer_email,
            'event_type': 'product_view',
            'event_timestamp_utc': viewed_at,
            'metadata': json.dumps({'product_id': product_id})
        }])
    
    return {"status": "recorded"}
```

---

### Adding Circuit Breaker: Example - Zendesk Support Ticket

**Scenario:** Zendesk sends webhook when customer creates support ticket

**File:** `src/SendFlowr.Inference/services/feature_service.py`

```python
def get_context_signals(self, recipient_id: str) -> Dict:
    # Circuit breaker signals (48h - 7 days)
    circuit_breaker_signals = [
        'support_ticket',
        'complaint',
        'unsubscribe_request',
        'zendesk_ticket_created'  # ← ADD THIS
    ]
    
    circuit_breakers = self.event_repo.get_context_signals(
        recipient_id,
        event_types=circuit_breaker_signals,
        hours_back=48  # 48 hours
    )
    
    # ... rest of method ...
```

**Suppression Logic:**

```python
# In get_context_signals() method
if circuit_breakers:
    latest = circuit_breakers[0]
    event_type = latest['event_type']
    
    # Determine suppression window by event type
    suppression_hours = {
        'support_ticket': 48,
        'zendesk_ticket_created': 48,  # ← ADD THIS
        'complaint': 48,
        'unsubscribe_request': 168,  # 7 days
        'spam_report': 999999  # Permanent
    }.get(event_type, 48)
    
    suppression_until = latest['event_timestamp_utc'] + timedelta(hours=suppression_hours)
    
    return {
        'suppressed': {
            'active': True,
            'reason': event_type,
            'until': suppression_until
        }
    }
```

**Webhook Handler:**

```python
@app.post("/webhooks/zendesk/ticket_created")
async def zendesk_ticket_created(event: dict):
    """
    Zendesk ticket creation event
    """
    ticket = event.get('ticket', {})
    requester_email = ticket.get('requester', {}).get('email')
    ticket_id = ticket.get('id')
    created_at = ticket.get('created_at')
    
    if requester_email:
        # Store event in ClickHouse
        clickhouse.execute("""
            INSERT INTO sendflowr.email_events (
                recipient_id, event_type, event_timestamp_utc,
                metadata
            ) VALUES
        """, [{
            'recipient_id': requester_email,
            'event_type': 'zendesk_ticket_created',
            'event_timestamp_utc': created_at,
            'metadata': json.dumps({'ticket_id': ticket_id})
        }])
        
        # Also link Zendesk user ID to email
        zendesk_user_id = ticket.get('requester', {}).get('id')
        if zendesk_user_id:
            email_hash = IdentityHelper.hash_email(requester_email)
            
            requests.post("http://localhost:8001/link-identifiers", params={
                "identifier_a": email_hash,
                "type_a": "email_hash",
                "identifier_b": f"zendesk_{zendesk_user_id}",
                "type_b": "zendesk_user_id",
                "weight": 1.0,
                "source": "zendesk_webhook"
            })
    
    return {"status": "recorded"}
```

---

## Testing Your Integration

### Test Identity Resolution

```bash
# 1. Link identifiers via webhook
curl -X POST "http://localhost:8001/webhooks/postscript" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "subscriber.created",
    "data": {
      "id": "ps_sub_test123",
      "phone": "+14155551234",
      "email": "test@example.com"
    }
  }'

# 2. Verify resolution works
curl -X POST "http://localhost:8001/resolve-identity?postscript_subscriber_id=ps_sub_test123"

# Expected: Should return Universal ID linked to that phone/email
```

### Test Hot Path

```bash
# 1. Insert hot path event
docker exec -i sendflowr-clickhouse clickhouse-client --query "
INSERT INTO sendflowr.email_events (
    recipient_id, event_type, event_timestamp_utc
) VALUES (
    'test@example.com',
    'product_view',
    now() - INTERVAL 5 MINUTE
)"

# 2. Request timing decision
curl -X POST "http://localhost:8001/timing-decision" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "send_after": "2026-01-10T00:00:00Z",
    "send_before": "2026-01-17T00:00:00Z"
  }'

# Expected: applied_weights should show product_view with weight > 0
```

### Test Circuit Breaker

```bash
# 1. Insert suppression event
docker exec -i sendflowr-clickhouse clickhouse-client --query "
INSERT INTO sendflowr.email_events (
    recipient_id, event_type, event_timestamp_utc
) VALUES (
    'test@example.com',
    'zendesk_ticket_created',
    now() - INTERVAL 1 HOUR
)"

# 2. Request timing decision
curl -X POST "http://localhost:8001/timing-decision" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "send_after": "2026-01-10T00:00:00Z",
    "send_before": "2026-01-17T00:00:00Z"
  }'

# Expected: suppressed=true, trigger_timestamp delayed by 48 hours
```

---

## Checklist for New Connector

### Identity Resolution
- [ ] Add `IdentifierType` enum value
- [ ] Decide deterministic vs probabilistic (and weight)
- [ ] Update `TimingRequest` model with new field
- [ ] Update `_normalize_identifiers()` in `IdentityResolver`
- [ ] Update `_probabilistic_lookup()` priority order
- [ ] Create webhook handler to link identifiers
- [ ] Test resolution with new identifier type

### Hot Path / Circuit Breaker (if applicable)
- [ ] Decide: acceleration or suppression?
- [ ] Add event type to appropriate signal list
- [ ] Configure suppression window (if circuit breaker)
- [ ] Create webhook handler to insert events
- [ ] Test hot path boost or suppression logic
- [ ] Verify in `applied_weights` or `suppressed` field

### Documentation
- [ ] Update connector README with webhook endpoints
- [ ] Document identifier weight rationale
- [ ] Add example payloads for webhooks
- [ ] Update API docs with new request fields

---

## Real-World Examples

### Example 1: Stripe Integration

**Identity:**
- Type: Probabilistic (0.85)
- Reason: Payment customer IDs can be shared (business accounts, family cards)
- Link via: email from `customer.email`

**Hot Paths:**
- `payment_succeeded` → Hot path (customer just purchased, send upsell within 30 min)
- `payment_failed` → Circuit breaker (suppress for 24h, don't annoy frustrated customer)

### Example 2: Attentive (SMS Platform)

**Identity:**
- Type: Probabilistic (0.90)
- Reason: Similar to Klaviyo, subscriber IDs are stable but not cryptographic
- Link via: phone from `subscriber.phone`

**Hot Paths:**
- `sms_clicked` → Hot path (user engaged via SMS, send email within 15 min)
- `sms_unsubscribed` → Circuit breaker (suppress for 7 days)

### Example 3: Gorgias (Support System)

**Identity:**
- Type: Probabilistic (0.80)
- Reason: Support user IDs can change, customers might share tickets
- Link via: email from `customer.email`

**Hot Paths:**
- `ticket_created` → Circuit breaker (suppress for 48h)
- `ticket_closed_satisfied` → Hot path (customer happy, send NPS survey within 2h)
- `ticket_closed_unsatisfied` → Circuit breaker (suppress for 7 days)

---

## Advanced: Multi-Platform Identity Graph

When a user is active across multiple platforms, the identity graph looks like:

```
email_hash (deterministic)
    ├── klaviyo_id (0.95)
    ├── shopify_customer_id (0.90)
    ├── stripe_customer_id (0.85)
    ├── zendesk_user_id (0.80)
    └── postscript_subscriber_id (0.90)

phone_number (deterministic)
    ├── postscript_subscriber_id (0.90)
    └── attentive_subscriber_id (0.90)

Universal ID: sf_abc123 (resolves all of the above)
```

**Resolution behavior:**
- Input: `{klaviyo_id: k_123}` → Finds Universal ID via email_hash (confidence=0.95)
- Input: `{stripe_customer_id: cus_xyz}` → Finds Universal ID via email_hash (confidence=0.85)
- Input: `{klaviyo_id: k_123, stripe_customer_id: cus_xyz}` → Merges both → Same Universal ID (confidence=1.0)

---

## Questions to Ask When Adding a Connector

1. **What identifiers does this platform provide?**
   - User IDs, customer IDs, subscriber IDs?

2. **Are these identifiers unique to one person?**
   - Can they be shared? (→ probabilistic)
   - Can they be reassigned? (→ probabilistic)

3. **What deterministic keys can we link to?**
   - Email? Phone? Both?

4. **What events does this platform emit?**
   - Engagement events? (→ hot path)
   - Negative events? (→ circuit breaker)

5. **How fresh do these events need to be?**
   - 5 minutes? 30 minutes? 48 hours?

6. **What's the suppression window for negative events?**
   - 24h? 48h? 7 days? Permanent?

---

## Support

For questions about connector integration:
- See **docs/IDENTITY-RESOLUTION.md** for identity system details
- See **LLM-Ref/LLM-spec.md §7** for specification
- See **src/SendFlowr.Inference/services/** for implementation examples
