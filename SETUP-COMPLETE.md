# SendFlowr - Initial Setup Complete ✅

## What's Been Built

### 1. Project Structure
```
SendFlowr/
├── src/
│   └── SendFlowr.Connectors/     # C# connector service
├── schemas/                       # Database schemas
├── scripts/                       # Initialization scripts  
├── tests/fixtures/                # Mock Klaviyo event data
├── docs/                         # Documentation
└── docker-compose.yml            # Local dev environment
```

### 2. Klaviyo Connector (C#)
- ✅ **OAuth Flow**: Initiate authorization and token exchange
- ✅ **Backfill**: Pull historical events from Klaviyo API
- ✅ **Webhook Handler**: Real-time event ingestion with signature validation
- ✅ **Event Publisher**: Kafka integration for event streaming
- ✅ **Canonical Event Model**: Normalized schema across all ESPs
- ✅ **Mock Data Generator**: Generate realistic test data without Klaviyo account

### 3. Infrastructure (Docker Compose)
- ✅ ClickHouse for event storage
- ✅ Redis for feature caching
- ✅ Kafka for event streaming
- ✅ Postgres for metadata

### 4. Database Schemas
- ✅ ClickHouse: Partitioned event store with deduplication
- ✅ Postgres: ESP account management, backfill tracking, webhook events

### 5. API Endpoints

#### OAuth (for real Klaviyo integration)
- `GET /api/connector/oauth/authorize` - Start OAuth flow
- `GET /api/connector/oauth/callback` - OAuth callback handler

#### Backfill (for real Klaviyo integration)
- `POST /api/connector/backfill?days=90` - Backfill historical events

#### Webhooks (for real Klaviyo integration)
- `POST /api/webhook/klaviyo` - Handle Klaviyo webhooks

#### Mock Data (for testing without Klaviyo)
- `POST /api/mock/events/generate?count=N` - Generate N random events
- `POST /api/mock/events/pattern?userId=X` - Generate realistic email journey

## Quick Start

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Run connector service
cd src/SendFlowr.Connectors
dotnet run
# Service runs on http://localhost:5215

# 3. Generate mock data
curl -X POST "http://localhost:5215/api/mock/events/generate?count=100"

# 4. Verify in Kafka
docker exec -it sendflowr-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic email-events \
  --from-beginning \
  --max-messages 5
```

## Testing with Mock Data

Since you don't have a Klaviyo account yet, use the mock endpoints:

```bash
# Generate 100 random events
curl -X POST "http://localhost:5215/api/mock/events/generate?count=100"

# Generate realistic email journeys
curl -X POST "http://localhost:5215/api/mock/events/pattern?userId=user_001"
curl -X POST "http://localhost:5215/api/mock/events/pattern?userId=user_002"
curl -X POST "http://localhost:5215/api/mock/events/pattern?userId=user_003"

# View Swagger UI
open http://localhost:5215/swagger
```

See `docs/MOCK-DATA.md` for complete mock data guide.

## Configuration

Update `src/SendFlowr.Connectors/appsettings.Development.json` when you get Klaviyo credentials:

```json
{
  "Klaviyo": {
    "ClientId": "your-klaviyo-client-id",
    "ClientSecret": "your-klaviyo-client-secret",
    "AccessToken": "your-klaviyo-api-key",
    "WebhookSecret": "your-webhook-secret"
  }
}
```

## What's Next (Week 2-3)

### Immediate Priorities
1. **Event Consumer**: Read from Kafka → Write to ClickHouse + S3
2. **Backfill Job**: Automated pagination and cursor management
3. **OAuth Token Storage**: Encrypt and store in Postgres
4. **Database Init Fix**: Resolve Postgres timeout in init script

### Week 4-5
- Feature store computation (hourly histograms)
- Python inference API skeleton
- Baseline probability model

### Week 6
- Campaign scheduler
- React dashboard MVP

## Verification

```bash
# Check all services are running
docker-compose ps

# Check Kafka topics
docker exec sendflowr-kafka kafka-topics --list --bootstrap-server localhost:9092

# Monitor events in real-time
docker exec -it sendflowr-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic email-events \
  --from-beginning

# Check ClickHouse (after consumer is built)
curl 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
  -d 'SELECT count() FROM sendflowr.email_events'
```

## Architecture Overview

```
Mock API or Klaviyo → Connector Service → Kafka → [Consumer TBD] → ClickHouse
                              ↓                                           ↓
                      Postgres (metadata)                         S3 (backup)
                                                                          ↓
                                                            Feature Store (Redis)
                                                                          ↓
                                                           Inference API (Python)
```

## Build Status
- ✅ Connector builds successfully
- ✅ All services running in Docker
- ✅ Kafka receiving events
- ✅ Mock data generator working
- ⚠️ Database init script has Postgres timeout (non-blocking)

## Files and Docs
- `README.md` - Project overview
- `SETUP-COMPLETE.md` - This file
- `docs/DEVELOPMENT.md` - Development workflow
- `docs/MOCK-DATA.md` - Mock data testing guide
- `tests/fixtures/` - Sample Klaviyo event payloads

## Next Session Recommendations

1. **Test the mock data flow**:
   ```bash
   docker-compose up -d
   cd src/SendFlowr.Connectors && dotnet run
   curl -X POST "http://localhost:5215/api/mock/events/generate?count=50"
   ```

2. **Implement Event Consumer** to complete the ingestion pipeline (Kafka → ClickHouse)
3. Add unit tests for event parsing
4. Create S3 backup integration
5. Fix Postgres timeout in init script (optional, non-blocking)