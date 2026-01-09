# SendFlowr

Email send-time optimization platform that predicts optimal engagement windows for each recipient.

## Quick Start

```bash
# Start local dev environment
docker-compose up -d

# Run connector
cd src/SendFlowr.Connectors
dotnet run

# Run inference API
cd src/SendFlowr.Inference
python -m uvicorn main:app --reload
```

## Architecture

- **Connectors** (C#): OAuth + backfill + webhooks for ESPs
- **Event Store**: ClickHouse for analytics
- **Feature Store**: Redis for fast feature access
- **Inference API** (Python): FastAPI serving probability curves
- **Scheduler** (C#): Campaign orchestration
- **Dashboard** (React): UI for marketers

## Current Status

- [x] Project structure
- [x] Klaviyo connector skeleton
- [ ] OAuth flow
- [ ] Backfill job
- [ ] Webhook handler
