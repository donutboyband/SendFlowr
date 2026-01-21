# Synthetic Data Generator

## Overview

The synthetic data generator now uses **production flow** - events are sent through the Connector API which handles:
- ✅ Identity resolution (email → universal_id)
- ✅ Email hashing (SHA-256 for privacy)
- ✅ Publishing to Kafka
- ✅ Same flow as production webhooks

## Prerequisites

1. **Docker services running:**
   ```bash
   docker-compose up -d
   ```

2. **Inference service running:**
   ```bash
   cd src/SendFlowr.Inference
   uvicorn main:app --host 0.0.0.0 --port 8001
   ```

3. **Connector running:**
   ```bash
   cd src/SendFlowr.Connectors
   dotnet run
   ```

4. **Consumer running:**
   ```bash
   cd src/SendFlowr.Consumer
   dotnet run
   ```

## Usage

### Quick Generate (Recommended for Testing)

Generate a small number of events quickly:

```bash
python3 scripts/generate-synthetic-data.py --count 100
```

Options:
- `--count N` - Generate N events (default: 100)
- `--dry-run` - Test without actually generating

### Verify Generated Data

```bash
# Count events with universal_id
docker exec sendflowr-clickhouse clickhouse-client --query \
  "SELECT count() FROM sendflowr.email_events WHERE universal_id LIKE 'sf_%'"

# Show recent events
docker exec sendflowr-clickhouse clickhouse-client --query \
  "SELECT universal_id, substring(recipient_email_hash, 1, 16), event_type 
   FROM sendflowr.email_events 
   WHERE universal_id LIKE 'sf_%' 
   ORDER BY timestamp DESC LIMIT 10"
```

### Full Historical Data Generation

Generate complete dataset with all personas and time-based patterns:

```bash
python3 scripts/generate-synthetic-data.py
```

This will generate ~80-100K events with:
- ESP latency modeling
- Minute-level engagement spikes
- Campaign fatigue patterns
- Hot path boosts
- Circuit breaker events

### Summary Only

See what would be generated without actually generating:

```bash
python3 scripts/generate-synthetic-data.py --summary
```

## How It Works

```
Python Script → Connector API → Identity Resolution → Kafka → Consumer → ClickHouse
                (/api/mock/events/generate)         (email-events)
```

**Key Benefits:**
1. **Production-like** - Same flow as real webhooks
2. **Privacy-first** - Emails hashed before storage
3. **Identity resolution** - Consistent universal_ids
4. **Realistic data** - Includes timing patterns, fatigue, etc.

## Examples

```bash
# Generate 10 events for quick test
python3 scripts/generate-synthetic-data.py --count 10

# Test the script without generating
python3 scripts/generate-synthetic-data.py --dry-run --count 100

# See data summary
python3 scripts/generate-synthetic-data.py --summary
```

## Troubleshooting

**"Connector API not available"**
```bash
# Start the connector
cd src/SendFlowr.Connectors && dotnet run
```

**Events not appearing in ClickHouse**
```bash
# Check consumer is running
cd src/SendFlowr.Consumer && dotnet run

# Check Kafka has events
docker exec sendflowr-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group sendflowr-consumer --describe
```

**Slow generation**
- The script rate-limits to 100 req/sec
- For large datasets, this is intentional to avoid overwhelming the API
- Use `--count` for smaller batches
