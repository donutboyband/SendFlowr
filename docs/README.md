# SendFlowr Documentation Index

## Getting Started

- **[README.md](../README.md)** - Project overview and quick start
- **[SendFlowr-Overview.md](../LLM-Ref/SendFlowr-Overview.md)** - Architecture and roadmap
- **[LLM-spec.md](../LLM-Ref/LLM-spec.md)** - Canonical specification

## Core Concepts

### Identity Resolution
- **[IDENTITY-RESOLUTION.md](IDENTITY-RESOLUTION.md)** - Universal ID system, deterministic vs probabilistic matching
- **[CONNECTOR-INTEGRATION-GUIDE.md](CONNECTOR-INTEGRATION-GUIDE.md)** - How to add new ESPs, platforms, and hot paths

### Timing Intelligence
- **[INFERENCE.md](INFERENCE.md)** - Minute-level timing decisions, latency compensation
- **[LLM-spec.md §2-6](../LLM-Ref/LLM-spec.md)** - Time model, probabilistic scoring, hot paths

## Development

- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Local setup, architecture patterns
- **[TESTING.md](TESTING.md)** - Testing guide, E2E scenarios
- **[MIGRATION.md](MIGRATION.md)** - v1 → v2 migration notes
- **[REFACTORING-SUMMARY.md](../REFACTORING-SUMMARY.md)** - Recent architectural changes

## Data & Testing

- **[SYNTHETIC-DATA.md](SYNTHETIC-DATA.md)** - Generating test data
- **[MOCK-DATA.md](MOCK-DATA.md)** - Mock data structures

## API Reference

- **Swagger UI**: http://localhost:8001/docs
- **Scalar Docs**: http://localhost:8001/scalar
- **ReDoc**: http://localhost:8001/redoc

## Specifications

- **[LLM-spec.md](../LLM-Ref/LLM-spec.md)** - Canonical requirements (MUST follow)
- **[LLM-negative-spec.md](../LLM-Ref/LLM-negative-spec.md)** - Anti-patterns (MUST avoid)
- **[spec.json](../LLM-Ref/spec.json)** - JSON schema for TimingDecision

## Integration Guides

### Adding New Connectors

1. **Read**: [CONNECTOR-INTEGRATION-GUIDE.md](CONNECTOR-INTEGRATION-GUIDE.md)
2. **Decide**: Deterministic vs Probabilistic identity
3. **Decide**: Hot path (accelerate) vs Circuit breaker (suppress)
4. **Implement**: Follow 6-step integration process
5. **Test**: Use provided test scripts

### Quick Reference

| If you're adding... | Start here... |
|---------------------|---------------|
| New ESP (Klaviyo, Iterable, etc.) | [CONNECTOR-INTEGRATION-GUIDE.md](CONNECTOR-INTEGRATION-GUIDE.md) → Identity Resolution |
| New ecommerce platform (Shopify, WooCommerce) | [CONNECTOR-INTEGRATION-GUIDE.md](CONNECTOR-INTEGRATION-GUIDE.md) → Identity + Hot Paths |
| New support system (Zendesk, Intercom) | [CONNECTOR-INTEGRATION-GUIDE.md](CONNECTOR-INTEGRATION-GUIDE.md) → Circuit Breakers |
| New event type (product view, cart add) | [CONNECTOR-INTEGRATION-GUIDE.md](CONNECTOR-INTEGRATION-GUIDE.md) → Hot Path Integration |

## Architecture Layers

```
┌─────────────────────────────────────────┐
│  Controllers (HTTP handlers)           │
├─────────────────────────────────────────┤
│  Services (Business logic)              │
│  - TimingService                        │
│  - IdentityResolver                     │
│  - FeatureService                       │
├─────────────────────────────────────────┤
│  Repositories (Data access)             │
│  - EventRepository (ClickHouse)         │
│  - IdentityRepository (ClickHouse)      │
│  - FeatureRepository (Redis)            │
├─────────────────────────────────────────┤
│  Models (Domain objects)                │
│  - TimingDecision                       │
│  - IdentityResolution                   │
│  - ContinuousCurve                      │
└─────────────────────────────────────────┘
```

## Database Schema

### ClickHouse Tables
- `email_events` - Event store (clicks, opens, sends, etc.)
- `identity_graph` - Identity edges (deterministic + probabilistic)
- `identity_audit_log` - Resolution audit trail
- `resolved_identities` - Universal ID cache
- `timing_explanations` - Decision explanations

### Redis Keys
- `features:v2:{universal_id}` - Cached minute-level features
- `decision:{universal_id}:{decision_id}` - Cached timing decisions

## Testing Scripts

- `scripts/test-identity-resolution.sh` - Comprehensive identity tests
- `scripts/run-e2e-timing-test.sh` - End-to-end timing decision test
- `scripts/restart-inference.sh` - Restart API server
- `scripts/quick-predict.sh` - Quick prediction test

## Key Files

### Core Implementation
- `src/SendFlowr.Inference/main.py` - FastAPI app entry point
- `src/SendFlowr.Inference/services/timing_service.py` - Timing decision logic
- `src/SendFlowr.Inference/services/identity_service.py` - Identity resolution
- `src/SendFlowr.Inference/core/timing_model.py` - Continuous curve model
- `src/SendFlowr.Inference/core/identity_model.py` - Identity domain models

### Configuration
- `docker-compose.yml` - Infrastructure (ClickHouse, Redis)
- `src/SendFlowr.Inference/requirements.txt` - Python dependencies

## Compliance Checklist

When implementing features, ensure:

- ✅ **§2**: Minute-level resolution (10,080 slots)
- ✅ **§3**: Latency-aware trigger computation
- ✅ **§6**: Click-based probabilistic scoring
- ✅ **§7**: Universal ID resolution before decisions
- ✅ **§8**: SendFlowr owns timing and identity logic

See **[LLM-spec.md](../LLM-Ref/LLM-spec.md)** for full requirements.

## Common Tasks

### Start Development Environment
```bash
docker-compose up -d
cd src/SendFlowr.Inference
source venv/bin/activate
python main.py
```

### Test Identity Resolution
```bash
./scripts/test-identity-resolution.sh
```

### Add New Connector
1. Read [CONNECTOR-INTEGRATION-GUIDE.md](CONNECTOR-INTEGRATION-GUIDE.md)
2. Add `IdentifierType` enum
3. Update request models
4. Create webhook handler
5. Test resolution

### View Audit Logs
```bash
docker exec -i sendflowr-clickhouse clickhouse-client --query "
SELECT * FROM sendflowr.identity_audit_log
ORDER BY created_at DESC LIMIT 20"
```

## Support & Questions

For detailed guides:
- **Identity questions** → [IDENTITY-RESOLUTION.md](IDENTITY-RESOLUTION.md)
- **Connector questions** → [CONNECTOR-INTEGRATION-GUIDE.md](CONNECTOR-INTEGRATION-GUIDE.md)
- **Timing questions** → [INFERENCE.md](INFERENCE.md)
- **Spec questions** → [LLM-spec.md](../LLM-Ref/LLM-spec.md)
