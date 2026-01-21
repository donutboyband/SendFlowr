# SendFlowr

SendFlowr is a personal project I built to learn about real-time data processing, event streaming, and modern backend tech. It's not a professional app—just a playground for experimenting with things like Kafka, ClickHouse, FastAPI, and some machine learning ideas.

## What is this?

SendFlowr is a sandbox for:
- Trying out Kafka for real-time event streaming
- Using ClickHouse for fast analytics on event data
- Building APIs with FastAPI (Python)
- Playing with identity resolution and timing logic
- Connecting services with Docker Compose
- Writing a bit of C# for fun (connectors/consumers)

The "theme" is email campaign timing and identity stitching, but the real goal was to get hands-on with the tech stack.

## Why?

I wanted to:
- Learn how Kafka works in practice
- See what ClickHouse is good at
- Build a FastAPI service from scratch
- Try out some simple ML for timing decisions
- Practice wiring up multiple services with Docker

## How to Run

```bash
docker-compose up -d
# Then run the Python API:
cd src/SendFlowr.Inference
source venv/bin/activate
python main.py
# Docs at http://localhost:8001/docs
```

## Example API Call

```bash
curl -X POST http://localhost:8001/timing-decision \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "klaviyo_id": "k_abc123",
    "send_after": "2026-01-10T00:00:00Z",
    "send_before": "2026-01-17T00:00:00Z",
    "latency_estimate_seconds": 300
  }'
```

Sample response:
```json
{
  "universal_id": "sf_b8783dbfc0024695",
  "trigger_timestamp_utc": "2026-01-16T23:55:00Z",
  "confidence_score": 0.72
}
```

## Project Structure

- `src/SendFlowr.Inference/` – Python API (FastAPI)
- `src/SendFlowr.Connectors/` – C# connectors (just for fun)
- `schemas/` – SQL and JSON schemas
- `scripts/` – Helper scripts

## Docs

- [docs/IDENTITY-RESOLUTION.md](docs/IDENTITY-RESOLUTION.md) – Identity resolution notes
- [LLM-Ref/SendFlowr-Overview.md](LLM-Ref/SendFlowr-Overview.md) – Architecture overview
- [docs/TESTING.md](docs/TESTING.md) – Testing notes

## Status

This is a work in progress, not production-ready, and probably full of rough edges. If you want to poke around or have ideas, feel free!
