# SendFlowr Docker Setup

All SendFlowr services are now containerized for easy deployment and development.

## Services

- **ClickHouse** - Event storage and analytics (ports 8123, 9000)
- **Redis** - Feature caching (port 6379)
- **Kafka** - Event streaming (ports 9092, 9093)
- **Postgres** - Metadata and identity storage (port 5432)
- **Inference** - Python timing intelligence service (port 8001)
- **Connector** - .NET event ingestion service (port 5215)
- **Consumer** - .NET Kafka→ClickHouse pipeline

## Quick Start

```bash
# Start all services with initialization
./scripts/start-docker.sh

# Or manually:
docker-compose up -d

# Create Kafka topic (required on first run)
docker exec sendflowr-kafka kafka-topics --create \
  --topic email-events \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1 \
  --if-not-exists

# Check status
docker-compose ps

# View logs
docker-compose logs -f connector
docker-compose logs -f consumer
docker-compose logs -f inference

# Stop all services
docker-compose down

# Stop and remove all data
docker-compose down -v
```

## Development Workflow

### Rebuild after code changes:

```bash
# Rebuild specific service
docker-compose up -d --build connector

# Rebuild all application services
docker-compose up -d --build connector consumer inference
```

### Generate synthetic test data:

```bash
# Generate 100 enhanced events with timing model training signals
python3 scripts/generate-synthetic-data.py --count 100
```

### Query events:

```bash
# ClickHouse queries
docker exec sendflowr-clickhouse clickhouse-client --query \
  "SELECT event_type, count() FROM sendflowr.email_events GROUP BY event_type"

# Check synthetic data quality
docker exec sendflowr-clickhouse clickhouse-client --query \
  "SELECT 
    JSONExtractString(metadata, 'persona') as persona,
    count() as events,
    avg(JSONExtractInt(metadata, 'latency_seconds')) as avg_latency
   FROM sendflowr.email_events 
   WHERE persona != ''
   GROUP BY persona"
```

### Test API endpoints:

```bash
# Health check
curl http://localhost:8001/health | jq .

# Timing decision
curl -X POST http://localhost:8001/timing/decide \
  -H "Content-Type: application/json" \
  -d '{
    "universal_id": "sf_test123",
    "latency_seconds": 15
  }' | jq .

# Generate mock events
curl -X POST http://localhost:5215/api/mock/events/generate?count=5
```

## Architecture

```
Third-Party Webhook
      ↓
  Connector (port 5215)
    - Identity Resolution
    - Email Hashing
      ↓
    Kafka
      ↓
   Consumer
      ↓
  ClickHouse
      ↑
  Inference (port 8001)
    - Feature Computation
    - Timing Decisions
      ↑
    Redis
```

## Environment Variables

All services use environment variables for configuration:

### Connector
- `Kafka__BootstrapServers` - Kafka connection
- `InferenceService__Url` - Inference API URL

### Consumer
- `Kafka__BootstrapServers` - Kafka connection
- `ClickHouse__Host` - ClickHouse hostname
- `ClickHouse__Port` - ClickHouse HTTP port (8123)
- `ClickHouse__Database` - Database name
- `ClickHouse__User` - Username
- `ClickHouse__Password` - Password

### Inference
- `REDIS_HOST` - Redis hostname
- `REDIS_PORT` - Redis port
- `CLICKHOUSE_HOST` - ClickHouse hostname
- `CLICKHOUSE_PORT` - ClickHouse native port (9000)
- `POSTGRES_HOST` - Postgres hostname
- `POSTGRES_PORT` - Postgres port
- `POSTGRES_DB` - Database name
- `POSTGRES_USER` - Username
- `POSTGRES_PASSWORD` - Password

## Troubleshooting

### Service won't start

```bash
# Check logs
docker-compose logs <service-name>

# Restart service
docker-compose restart <service-name>
```

### Clear all data

```bash
# Truncate ClickHouse table
docker exec sendflowr-clickhouse clickhouse-client --query \
  "TRUNCATE TABLE sendflowr.email_events"

# Clear Redis cache
docker exec sendflowr-redis redis-cli FLUSHALL
```

### Rebuild from scratch

```bash
# Stop, remove volumes, rebuild
docker-compose down -v
docker-compose up -d --build
```

## Production Considerations

- ✅ All services are stateless except datastores
- ✅ Horizontal scaling ready (Kafka partitions, multiple consumers)
- ✅ Health checks configured for all services
- ✅ Automatic restart on failure
- 🚧 Add secrets management (don't use default passwords!)
- 🚧 Configure resource limits
- 🚧 Set up monitoring and alerts
- 🚧 Enable TLS/SSL for external connections
