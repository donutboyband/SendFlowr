# SendFlowr

**Timing Intelligence Layer for Email Campaigns**

Minute-level precision timing decisions with identity resolution and latency awareness.

## 🎯 Core Features

✅ **Universal Identity Resolution** - Stitch email, phone, ESP IDs, and customer IDs into a single Universal SendFlowr ID  
✅ **Minute-Level Precision** - 10,080 minute slots per week (canonical time grid)  
✅ **Click-Based Modeling** - MPP-resilient engagement signals  
✅ **Latency-Aware Triggers** - Compensate for ESP delivery delays  
✅ **Hot Path Detection** - Real-time event boosts (site visits, SMS clicks, product views)  
✅ **Circuit Breakers** - Automatic suppression for complaints, support tickets, unsubscribes  
✅ **Explainable Decisions** - Full audit trail and decision explanations  

## Quick Start

```bash
# Start infrastructure
docker-compose up -d

# Run inference API
cd src/SendFlowr.Inference
source venv/bin/activate
python main.py

# API available at:
# - Swagger UI:  http://localhost:8001/docs
# - Scalar Docs: http://localhost:8001/scalar
# - ReDoc:       http://localhost:8001/redoc
```

## Architecture

### Layered Design (Clean Architecture)
- **Controllers** → HTTP request/response handling
- **Services** → Business logic (timing decisions, identity resolution)
- **Repositories** → Data access (ClickHouse, Redis)

### Components
- **Timing Service**: Minute-level timing decisions with latency compensation
- **Identity Resolution**: Universal ID stitching (deterministic + probabilistic)
- **Feature Service**: Click-based engagement curve computation
- **Event Store**: ClickHouse for email events, identity graph, explanations
- **Feature Store**: Redis for cached features and decisions
- **Connectors** (C#): OAuth + backfill + webhooks for ESPs (future)

## Identity Resolution

Per **LLM-spec.md §7**, all timing decisions reference a **Universal SendFlowr ID**.

### Deterministic Keys (highest priority)
- Email (hashed with SHA-256)
- Phone number (normalized to E.164)

### Probabilistic Keys (graph traversal)
- Klaviyo ID, Shopify customer ID, ESP user IDs, IP/device signatures

### Example: Timing Decision with Identity Resolution

```bash
curl -X POST http://localhost:8001/timing-decision \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "klaviyo_id": "k_abc123",
    "send_after": "2026-01-10T00:00:00Z",
    "send_before": "2026-01-17T00:00:00Z",
    "latency_estimate_seconds": 300
  }'
```

**Response:**
```json
{
  "universal_id": "sf_b8783dbfc0024695",
  "trigger_timestamp_utc": "2026-01-16T23:55:00Z",
  "confidence_score": 0.72
}
```

See **[docs/IDENTITY-RESOLUTION.md](docs/IDENTITY-RESOLUTION.md)** for full documentation.

## Current Status

### ✅ Phase 1-5: Core Timing Layer (COMPLETE)
- [x] Minute-level resolution (10,080 slots)
- [x] Click-based engagement curves
- [x] Latency-aware trigger computation
- [x] Confidence scoring (entropy-based)
- [x] Spec compliance 

### ✅ Phase 6: Identity Resolution (COMPLETE)
- [x] Universal SendFlowr ID generation
- [x] Deterministic matching (email hash, phone)
- [x] Probabilistic matching (ESP IDs, customer IDs)
- [x] Identity graph with audit trail
- [x] Idempotent merges

### ⚠️ Phase 6-8: Advanced Features (PARTIAL)
- [x] Hot path logic implemented
- [x] Circuit breaker logic implemented
- [ ] Real-time webhook integration (Shopify, Zendesk, etc.)
- [ ] Dynamic latency tracking per ESP
- [ ] Explainability UI/dashboard

## Documentation

- **[LLM-Ref/LLM-spec.md](LLM-Ref/LLM-spec.md)** - Canonical specification
- **[LLM-Ref/SendFlowr-Overview.md](LLM-Ref/SendFlowr-Overview.md)** - Architecture overview
- **[docs/IDENTITY-RESOLUTION.md](docs/IDENTITY-RESOLUTION.md)** - Identity resolution guide
- **[docs/TESTING.md](docs/TESTING.md)** - Testing guide
- **[REFACTORING-SUMMARY.md](REFACTORING-SUMMARY.md)** - Recent changes

## Spec Compliance

✅ **100% LLM-Ref compliant**  
✅ **§2**: 10,080 minute slots, continuous curves  
✅ **§3**: TimingDecision contract with latency compensation  
✅ **§6**: Probabilistic P(t) distributions from clicks  
✅ **§7**: Universal Identity Resolution with audit trail  
✅ **§8**: SendFlowr owns timing logic and identity (headless architecture)
