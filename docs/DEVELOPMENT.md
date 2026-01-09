# SendFlowr Development Guide

## Quick Start

### 1. Start Infrastructure

```bash
# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps

# Initialize databases and Kafka topics
./scripts/init-databases.sh
```

### 2. Run Connector Service

```bash
cd src/SendFlowr.Connectors
dotnet run
```

The connector API will be available at `http://localhost:5000` with Swagger UI at `http://localhost:5000/swagger`.

## API Endpoints

### OAuth Flow

1. **Initiate OAuth**
   ```bash
   GET http://localhost:5000/api/connector/oauth/authorize?callbackUrl=http://localhost:5000/api/connector/oauth/callback
   ```

2. **OAuth Callback** (automatically called by ESP after user authorizes)
   ```bash
   GET http://localhost:5000/api/connector/oauth/callback?code={code}&state={state}
   ```

### Backfill Events

```bash
POST http://localhost:5000/api/connector/backfill?days=90
```

### Webhook Handler

```bash
POST http://localhost:5000/api/webhook/klaviyo
Headers:
  X-Klaviyo-Signature: {signature}
Body: {webhook payload}
```

## Configuration

Update `src/SendFlowr.Connectors/appsettings.Development.json` with your Klaviyo credentials:

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

## Testing Event Flow

1. Start infrastructure and connector
2. Trigger a backfill or send a webhook event
3. Check Kafka for published events:

```bash
docker exec -it sendflowr-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic email-events \
  --from-beginning
```

4. Query events in ClickHouse:

```bash
curl 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
  -d 'SELECT * FROM sendflowr.email_events LIMIT 10'
```

## Next Steps

- [ ] Implement event consumer to write Kafka events to ClickHouse
- [ ] Add feature computation service
- [ ] Build Python inference API
- [ ] Create scheduler service
- [ ] Build React dashboard
