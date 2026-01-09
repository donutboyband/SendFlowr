# Mock Data Guide

Since you don't have a Klaviyo account yet, use these mock endpoints to simulate email events.

## Mock Endpoints

### Generate Random Events
```bash
# Generate 50 random events
curl -X POST "http://localhost:5000/api/mock/events/generate?count=50"
```

This creates random events across:
- **Users**: user_001 through user_005
- **Campaigns**: welcome_series, weekly_newsletter, promo_jan, re_engagement
- **Event Types**: sent, delivered, opened, clicked
- **Time Range**: Random times in the last week

### Generate Realistic Email Journey
```bash
# Generate a realistic sequence: sent → delivered → opened → clicked
curl -X POST "http://localhost:5000/api/mock/events/pattern?userId=user_001"
```

This simulates a complete email journey with proper timing:
1. Email sent
2. Email delivered (1 min later)
3. Email opened (15 min later)
4. Link clicked (5 min after open)

## Test Workflow

### 1. Start Services
```bash
docker-compose up -d
cd src/SendFlowr.Connectors
dotnet run
```

### 2. Generate Mock Data
```bash
# Generate 100 events
curl -X POST "http://localhost:5000/api/mock/events/generate?count=100"

# Generate realistic patterns for multiple users
curl -X POST "http://localhost:5000/api/mock/events/pattern?userId=user_001"
curl -X POST "http://localhost:5000/api/mock/events/pattern?userId=user_002"
curl -X POST "http://localhost:5000/api/mock/events/pattern?userId=user_003"
```

### 3. Verify Events in Kafka
```bash
# Monitor Kafka topic
docker exec -it sendflowr-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic email-events \
  --from-beginning \
  --max-messages 10
```

### 4. Query ClickHouse (after implementing consumer)
```bash
# Count events by type
curl 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
  -d 'SELECT event_type, count() FROM sendflowr.email_events GROUP BY event_type'

# Recent events
curl 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
  -d 'SELECT * FROM sendflowr.email_events ORDER BY timestamp DESC LIMIT 10'
```

## Sample Fixture Files

Located in `tests/fixtures/`:
- `klaviyo-opened-event.json` - Single open event
- `klaviyo-clicked-event.json` - Single click event
- `klaviyo-backfill-response.json` - Multiple events (backfill format)

Use these to test webhook parsing:
```bash
curl -X POST http://localhost:5000/api/webhook/klaviyo \
  -H "Content-Type: application/json" \
  -H "X-Klaviyo-Signature: dev-signature" \
  -d @tests/fixtures/klaviyo-opened-event.json
```

## When You Get Klaviyo Access

Replace mock data with real OAuth:

1. Update `appsettings.Development.json` with real credentials
2. Visit: `http://localhost:5000/api/connector/oauth/authorize?callbackUrl=http://localhost:5000/api/connector/oauth/callback`
3. Complete OAuth flow
4. Backfill real data: `curl -X POST http://localhost:5000/api/connector/backfill?days=90`
