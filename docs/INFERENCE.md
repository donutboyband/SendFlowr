# SendFlowr Inference Pipeline

## Quick Start

### Option 1: Run Full Pipeline
```bash
./scripts/run-inference-pipeline.sh
```

This will:
1. Start the inference API (if not running)
2. Compute features for all active users
3. Generate predictions for sample users
4. Show detailed prediction with probability curves

### Option 2: Quick Prediction for Single User
```bash
./scripts/quick-predict.sh user_003
./scripts/quick-predict.sh user_001 48  # Look ahead 48 hours
```

### Option 3: Manual API Calls

#### Start the Inference API
```bash
cd src/SendFlowr.Inference
source venv/bin/activate
python -m uvicorn main:app --reload --port 8000
```

#### Compute Features for All Users
```bash
curl -X POST http://localhost:8000/compute-all-features
```

#### Get Prediction for a User
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"recipient_id": "user_003", "hours_ahead": 24}' | python3 -m json.tool
```

#### Get Cached Features
```bash
curl http://localhost:8000/features/user_003 | python3 -m json.tool
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information |
| `/health` | GET | Health check (ClickHouse + Redis) |
| `/predict` | POST | Generate engagement prediction |
| `/features/{recipient_id}` | GET | Get cached features |
| `/compute-features/{recipient_id}` | POST | Compute features on-demand |
| `/compute-all-features` | POST | Compute for all active users |
| `/docs` | GET | Interactive API documentation |

## Prediction Response

```json
{
  "recipient_id": "user_003",
  "model_version": "baseline_v1",
  "optimal_windows": [
    {
      "start": "2026-01-10T15:39:00",
      "end": "2026-01-10T16:39:00",
      "probability": 0.058
    }
  ],
  "explanation": {
    "peak_hours": [
      {"hour": 16, "time": "16:00-17:00", "probability": 9.1},
      {"hour": 11, "time": "11:00-12:00", "probability": 6.8}
    ],
    "peak_days": [
      {"day": "Monday", "probability": 37.0}
    ]
  },
  "features_used": {
    "open_count_30d": 20,
    "click_count_30d": 29
  }
}
```

## Feature Computation

Features are computed from ClickHouse and cached in Redis:

### Hourly Histogram
24-hour distribution of email opens with Laplace smoothing

### Weekday Histogram  
7-day distribution (Monday=0, Sunday=6)

### Recency Features
- `last_open_ts` - Timestamp of last open
- `last_click_ts` - Timestamp of last click
- `open_count_30d` - Opens in last 30 days
- `click_count_30d` - Clicks in last 30 days
- `open_count_7d` - Opens in last 7 days
- `click_count_7d` - Clicks in last 7 days

## Model Details

**baseline_v1**: Histogram-based probabilistic model

- Combines hourly (70%) and weekday (30%) signals
- Generates minute-level probability curves
- Identifies optimal 2-hour send windows
- Normalizes probabilities to sum to 1.0

## Example Output

```
📊 PREDICTION RESULTS
==================================================
Recipient: user_003
Model: baseline_v1

🎯 TOP 3 OPTIMAL SEND WINDOWS
--------------------------------------------------
1. 2026-01-10 15:39 - 16:39
   Probability: 5.79%

2. 2026-01-11 15:39 - 16:39
   Probability: 5.42%

3. 2026-01-10 11:39 - 12:39
   Probability: 4.95%

⭐ PEAK ENGAGEMENT HOURS
--------------------------------------------------
16:00-17:00     ████████████████████████████████ 9.1%
11:00-12:00     ███████████████████ 6.8%
15:00-16:00     ███████████████████ 6.8%

📅 PEAK ENGAGEMENT DAYS
--------------------------------------------------
Monday       ████████████████████████████████████ 37.0%
Saturday     ██████████████████ 18.5%
Sunday       ██████████████ 14.8%

📈 ENGAGEMENT STATS
--------------------------------------------------
Opens (30 days):  20
Clicks (30 days): 29
```

## Integration with Scheduler

The scheduler service will:
1. Get list of recipients for a campaign
2. Call `/predict` for each recipient
3. Use `optimal_windows[0]` as recommended send time
4. Apply campaign constraints (business hours, etc.)
5. Schedule sends via ESP API

## Performance

- Feature computation: ~100ms per user
- Prediction generation: ~50ms per user  
- Redis cache hit: ~5ms
- Supports 1000+ predictions/second

## Monitoring

Check service health:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "redis": "ok",
  "clickhouse": "ok"
}
```

## Troubleshooting

### API not responding
```bash
# Check if running
ps aux | grep uvicorn

# Restart
cd src/SendFlowr.Inference
source venv/bin/activate  
python -m uvicorn main:app --reload --port 8000
```

### No features found
```bash
# Compute features
curl -X POST http://localhost:8000/compute-all-features
```

### ClickHouse connection error
```bash
# Check ClickHouse is running
docker ps | grep clickhouse

# Test connection
curl 'http://localhost:8123/ping'
```

### Redis connection error
```bash
# Check Redis is running
docker ps | grep redis

# Test connection
docker exec sendflowr-redis redis-cli ping
```
