# SendFlowr - Initial Setup Complete ✅

## What's Been Built

### 1. Project Structure
```
SendFlowr/
├── src/
│   └── SendFlowr.Connectors/     # C# connector service
├── schemas/                       # Database schemas
├── scripts/                       # Initialization scripts
├── docs/                         # Documentation
└── docker-compose.yml            # Local dev environment
```

### 2. Klaviyo Connector (C#)
- ✅ **OAuth Flow**: Initiate authorization and token exchange
- ✅ **Backfill**: Pull historical events from Klaviyo API
- ✅ **Webhook Handler**: Real-time event ingestion with signature validation
- ✅ **Event Publisher**: Kafka integration for event streaming
- ✅ **Canonical Event Model**: Normalized schema across all ESPs

### 3. Infrastructure (Docker Compose)
- ✅ ClickHouse for event storage
- ✅ Redis for feature caching
- ✅ Kafka for event streaming
- ✅ Postgres for metadata

### 4. Database Schemas
- ✅ ClickHouse: Partitioned event store with deduplication
- ✅ Postgres: ESP account management, backfill tracking, webhook events

### 5. API Endpoints

#### OAuth
- `GET /api/connector/oauth/authorize` - Start OAuth flow
- `GET /api/connector/oauth/callback` - OAuth callback handler

#### Backfill
- `POST /api/connector/backfill?days=90` - Backfill historical events

#### Webhooks
- `POST /api/webhook/klaviyo` - Handle Klaviyo webhooks

## Quick Start

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Initialize databases
./scripts/init-databases.sh

# 3. Run connector service
cd src/SendFlowr.Connectors
dotnet run

# 4. Access Swagger UI
open http://localhost:5000/swagger
```

## Configuration Needed

Before running, update `src/SendFlowr.Connectors/appsettings.Development.json`:

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
4. **Webhook Registration**: Auto-register webhooks with Klaviyo

### Week 4-5
- Feature store computation (hourly histograms)
- Python inference API skeleton
- Baseline probability model

### Week 6
- Campaign scheduler
- React dashboard MVP

## Testing the Setup

```bash
# Check Kafka topics
docker exec -it sendflowr-kafka kafka-topics --list --bootstrap-server localhost:9092

# Monitor Kafka events
docker exec -it sendflowr-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic email-events \
  --from-beginning

# Query ClickHouse
curl 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
  -d 'SELECT count() FROM sendflowr.email_events'
```

## Architecture Overview

```
Klaviyo → OAuth → Connector Service → Kafka → [Consumer TBD] → ClickHouse
                        ↓                                           ↓
                  Postgres (metadata)                       S3 (backup)
                                                                    ↓
                                                          Feature Store (Redis)
                                                                    ↓
                                                          Inference API (Python)
```

## Build Status
- ✅ Connector builds successfully (4 nullable warnings, no errors)
- ✅ All services defined in docker-compose
- ✅ Database schemas created
- ✅ API structure complete

## Next Session Recommendations

1. Start infrastructure: `docker-compose up -d`
2. Initialize DBs: `./scripts/init-databases.sh`
3. Implement the **Event Consumer** service to complete the ingestion pipeline
4. Add unit tests for Klaviyo connector
5. Create S3 backup integration
