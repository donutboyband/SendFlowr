# SendFlowr v2.0 - Complete Test Suite

This directory contains all test scripts for SendFlowr v2.0 Timing Layer.

## Quick Start

### Complete Setup & Test
```bash
./scripts/setup-and-test-v2.sh
```

This script:
1. ✅ Checks Docker services
2. ✅ Verifies databases (ClickHouse, Redis, Kafka)
3. ✅ Sets up Python environment
4. ✅ Starts v1.0 API (backwards compat)
5. ✅ Starts v2.0 Timing Layer API
6. ✅ Starts Event Consumer
7. ✅ Runs health checks
8. ✅ Executes full pipeline test

## Individual Test Scripts

### 1. Database Initialization
```bash
./scripts/init-databases.sh
```
- Creates ClickHouse schema
- Creates Postgres tables
- Creates Kafka topics

### 2. Generate Test Events
```bash
./scripts/generate-test-events.sh
```
- Generates ~125 mock events
- Creates realistic user journeys
- Publishes to Kafka

### 3. Quick Prediction/Decision

**v1.0 (Hourly STO)**:
```bash
./scripts/quick-predict.sh user_003 24 8000
```

**v2.0 (Minute-Level Timing)**:
```bash
./scripts/quick-predict.sh user_003 300 8001
#                                    ^^^latency seconds
#                                        ^^^^ port
```

### 4. Full Pipeline Test

**v2.0 Timing Layer**:
```bash
./scripts/run-inference-pipeline-v2.sh
```
- Computes minute-level features
- Generates timing decisions for 5 users
- Shows detailed decision analysis
- Displays feature metadata

**v1.0 (Legacy)**:
```bash
./scripts/run-inference-pipeline.sh
```
- Still works for backwards compatibility

## Test Data

### Available Test Users
- `user_001` through `user_005` - Regular users
- `user_heavy` - High engagement
- `user_low_engage` - Low engagement
- `cohort_user_a/b/c` - Test cohort

### Event Types Generated
- `sent` - Email sent
- `delivered` - Email delivered
- `opened` - Email opened (v1.0 signal)
- `clicked` - Email clicked (**v2.0 primary signal**)

## Verification

### Check ClickHouse Events
```bash
curl 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
  -d 'SELECT count() FROM sendflowr.email_events'
```

### Check Redis Features (v2.0)
```bash
docker exec sendflowr-redis redis-cli --scan --pattern "features:v2:*"
```

### Check Kafka Topics
```bash
docker exec sendflowr-kafka kafka-topics \
  --list --bootstrap-server localhost:9092
```

### Monitor Kafka Events
```bash
docker exec -it sendflowr-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic email-events \
  --max-messages 5
```

## API Testing

### v1.0 API (port 8000)
```bash
# Swagger UI
open http://localhost:8000/swagger

# Health check
curl http://localhost:8000/health

# Hourly prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"recipient_id": "user_003", "hours_ahead": 24}'
```

### v2.0 API (port 8001)
```bash
# Interactive docs
open http://localhost:8001/docs

# Health check
curl http://localhost:8001/health

# Timing decision
curl -X POST http://localhost:8001/timing-decision \
  -H "Content-Type: application/json" \
  -d '{"recipient_id": "user_003", "latency_estimate_seconds": 300}'

# Get features
curl http://localhost:8001/features/user_003
```

## Expected Results

### v1.0 Output (Hourly)
```json
{
  "recipient_id": "user_003",
  "model_version": "hourly_fallback_sto",
  "peak_hour": 16,
  "peak_probability": 0.091
}
```

### v2.0 Output (Minute-Level)
```json
{
  "decision_id": "uuid",
  "universal_user_id": "user_003",
  "target_minute_utc": 8618,
  "trigger_timestamp_utc": "2026-01-10T23:33:00Z",
  "latency_estimate_seconds": 300,
  "confidence_score": 0.84,
  "model_version": "minute_level_v2.0_click_based"
}
```

## Troubleshooting

### Docker services not running
```bash
docker-compose up -d
./scripts/init-databases.sh
```

### API not responding
```bash
# v1.0
cd src/SendFlowr.Connectors && dotnet run

# v2.0
cd src/SendFlowr.Inference
source venv/bin/activate
python -m uvicorn main_v2:app --reload --port 8001
```

### No events in ClickHouse
```bash
# Generate test events
./scripts/generate-test-events.sh

# Start consumer
cd src/SendFlowr.Consumer && dotnet run
```

### Python dependencies missing
```bash
cd src/SendFlowr.Inference
source venv/bin/activate
pip install -r requirements.txt scipy
```

## Performance Benchmarks

Expected performance (local development):

| Operation | v1.0 | v2.0 |
|-----------|------|------|
| Feature computation | ~100ms | ~150ms |
| Prediction/Decision | ~50ms | ~80ms |
| Cache hit | ~5ms | ~5ms |

## Test Coverage

- [x] Event ingestion (Kafka → ClickHouse)
- [x] Feature computation (hourly & minute-level)
- [x] v1.0 STO predictions
- [x] v2.0 Timing decisions
- [x] Latency compensation
- [x] Backwards compatibility
- [ ] Contextual signals (hot paths/circuit breakers)
- [ ] Universal ID resolution
- [ ] Latency tracker

## Continuous Testing

For automated testing in CI/CD:

```bash
# Quick smoke test
./scripts/setup-and-test-v2.sh

# Verify outputs
test $(curl -s http://localhost:8001/health | grep -c "healthy") -eq 1
```
