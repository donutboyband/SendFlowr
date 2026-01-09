### Overview
You can absolutely build this solo. The plan below is a pragmatic, low‑overhead roadmap and tech stack tuned for one engineer who knows **C# and JavaScript** and will use **Copilot CLI** for heavy lifting. It prioritizes fast feedback loops, low ops, and incremental model improvements so you ship an MVP quickly and iterate from real customer data.

---

### Solo founder roadmap with timelines
| **Phase** | **Goal** | **Duration |
|---|---:|---:|
| **Discovery and infra skeleton** | Define contracts, infra, and connector pattern | 1 week |
| **MVP connector and ingestion** | One ESP connector, backfill, webhooks, event store | 2 weeks |
| **Baseline model and inference API** | Hourly histograms + survival baseline, cached curves | 2 weeks |
| **Scheduler and dashboard** | Campaign scheduler, simple React UI, beta test | 2 weeks |
| **Improve models and online updates** | Add survival training, online posterior updates | 3 weeks |
| **Expand connectors and harden** | Add 1–2 more ESPs, monitoring, billing basics | 3 weeks |

**Total solo MVP timeline**: **~10–13 weeks** to a usable beta you can test with customers.

---

### Priorities and minimal scope for solo MVP
- **Must have**: OAuth connector for one ESP, backfill of last 90 days, webhook ingestion, canonical event store, simple feature store (Redis), baseline probabilistic model, inference API, scheduler that returns per‑recipient windows, tiny dashboard to inspect curves.
- **Nice to have**: Batch campaign mode, basic A/B test harness, simple billing.
- **Defer**: Cross‑channel SDKs, neural temporal models, enterprise SSO, multi‑region infra.

---

### Tech stack in depth
| **Layer** | **Recommended tech** | **Why it fits a solo C# JS engineer** |
|---|---:|---|
| **Connectors** | **C# (.NET 7/8)** | Familiar language; strong HTTP/OAuth libraries; easy to run locally and in containers. |
| **Auth and secrets** | **Azure Key Vault** or **AWS Secrets Manager** | Managed secrets; integrates with CI/CD and Kubernetes. |
| **Streaming ingestion** | **Kafka (Confluent Cloud)** or **AWS Kinesis** | Durable, replayable streams; managed options reduce ops. |
| **Event store** | **ClickHouse** or **Postgres + Timescale** | ClickHouse for fast analytics; Postgres simpler for solo dev. |
| **Feature store / cache** | **Redis** | Simple, low-latency store for precomputed histograms and recency features. |
| **ML training** | **Python** with **PyTorch**, **lifelines**, **NumPyro** | Best ecosystem for survival models and temporal point processes. Run as separate service. |
| **Model serving** | **FastAPI** (Python) behind **gRPC** or REST | Lightweight, easy to containerize; low-latency inference. |
| **Scheduler and business logic** | **C# service** | Use ASP.NET Core for campaign orchestration and to call inference API. |
| **Dashboard** | **Node.js + React** | Rapid UI development; many charting libs. |
| **Orchestration** | **Docker + Kubernetes** or **ECS Fargate** | Start with single Docker Compose locally; move to managed containers for production. |
| **CI/CD** | **GitHub Actions** | Easy to configure; integrates with Copilot CLI workflows. |
| **Observability** | **Prometheus + Grafana**, **Sentry** | Track latency, errors, model drift. |
| **Storage for raw events** | **S3** | Cheap, durable backups and replay. |
| **Local dev tooling** | **Copilot CLI**, **Docker Compose**, **dotnet watch** | Copilot CLI accelerates scaffolding and code generation. |

---

### Architecture and data flow for solo build
1. **Connector (C#)**: OAuth → backfill job → emit canonical events to Kafka topic.  
2. **Ingestion consumer (C# or Node)**: read Kafka → dedupe → write to ClickHouse or Postgres and S3 backup.  
3. **Feature builder (Python or C#)**: hourly job computes `hour_histogram_24`, `weekday_histogram_7`, `last_open_ts`, `open_count_30d` and writes to Redis.  
4. **Model training (Python)**: nightly batch trains hierarchical survival baseline and stores model artifact.  
5. **Inference service (Python FastAPI)**: loads model, reads features from Redis, returns minute-level probability curve; cache in Redis.  
6. **Scheduler (C#)**: calls inference API for recipients, applies campaign constraints, returns recommended windows to ESP via their send API or to marketer UI.  
7. **Dashboard (React)**: visualize per-user curves, campaign scheduling, connector health.  
8. **Monitoring**: log predictions and outcomes to compute calibration and A/B lift.

---

### Solo engineering workflow and Copilot CLI usage
- **Scaffold quickly**: use Copilot CLI to generate connector skeletons, OAuth flows, and API stubs.  
- **Iterate locally**: Docker Compose with services for connector, Kafka (or local mock), ClickHouse/Postgres, Redis, and FastAPI.  
- **Test with fixtures**: record a few real ESP webhook payloads and use them as fixtures for local testing.  
- **CI**: GitHub Actions runs unit tests, lints, and builds containers. Use Copilot to generate test cases and mocks.  
- **Deploy**: start with a single small cloud VM or managed container service; migrate to EKS/ECS when load grows.  
- **Backups and replay**: store raw events in S3 so you can replay ingestion if you change normalization.

---

### Week by week solo sprint plan with tasks
#### Week 1 Discovery and infra
- **Tasks**: finalize canonical schema; repo skeleton; Docker Compose dev stack; Copilot CLI project scaffolding.  
- **Deliverable**: local dev environment running connector stub, Kafka mock, Redis, and Postgres/ClickHouse.

#### Week 2 Connector and backfill
- **Tasks**: implement OAuth flow for chosen ESP; implement backfill job that pages events and writes canonical events to Kafka; store tokens encrypted.  
- **Deliverable**: backfill of last 90 days into event store.

#### Week 3 Webhooks and ingestion
- **Tasks**: register webhook endpoint, implement signature verification, enqueue events to Kafka, consumer writes to event store and S3 backup.  
- **Deliverable**: real-time events appear in event store within 5 seconds.

#### Week 4 Feature store and baseline histograms
- **Tasks**: compute per-user `hour_histogram_24` and `weekday_histogram_7` hourly; store in Redis; build simple API to fetch features.  
- **Deliverable**: feature store populated and queryable.

#### Week 5 Baseline model and inference API
- **Tasks**: implement histogram smoothing + simple survival model using `lifelines`; build FastAPI inference endpoint that returns 24h probability curve; cache results.  
- **Deliverable**: inference API returns curves for sample users.

#### Week 6 Scheduler and dashboard
- **Tasks**: implement C# scheduler to call inference API and produce recommended windows; build React UI to inspect curves and schedule a campaign.  
- **Deliverable**: end‑to‑end flow from connector to recommended windows visible in UI.

#### Week 7 Beta testing and A/B harness
- **Tasks**: onboard 1–2 beta customers; run A/B test comparing default send time vs predicted windows; log outcomes.  
- **Deliverable**: initial lift metrics and calibration plots.

#### Weeks 8–10 Model improvements and hardening
- **Tasks**: add survival model training pipeline, online posterior updates on webhooks, add one more ESP connector, add monitoring and alerts.  
- **Deliverable**: improved model accuracy and multi‑ESP support.

---

### First step detailed checklist and acceptance criteria
**Objective** Build the first ESP connector with backfill and webhook ingestion.

**Tasks**
1. **Canonical schema doc** — finalize JSON schema and store in repo.  
2. **Connector skeleton** — C# project with `IEspConnector` interface, OAuth helpers, token storage.  
3. **OAuth flow** — implement connect page, token exchange, secure storage in secrets manager.  
4. **Backfill job** — paginated pull of events, normalize to canonical schema, push to Kafka topic or local queue.  
5. **Webhook handler** — verify signature, normalize payload, enqueue event.  
6. **Ingestion consumer** — read queue, dedupe, write to ClickHouse/Postgres and S3 backup.  
7. **Smoke tests** — run backfill for 90 days and verify event counts; replay webhook fixtures.

**Acceptance criteria**
- OAuth connect completes and token stored encrypted.  
- Backfill ingests at least 90 days of events with <2% missing compared to ESP counts.  
- Webhook events appear in event store within 5 seconds.  
- Admin UI shows connector status and recent events.

---

### Quick implementation tips and code pointers
- **C# OAuth**: use `Microsoft.Identity.Client` or `HttpClient` with `OpenIdConnect` helpers; store tokens encrypted with Key Vault.  
- **Webhook verification**: verify HMAC signatures and respond 200 quickly; do heavy work asynchronously.  
- **Backfill paging**: implement idempotent paging using `since_id` or `since_ts` and persist progress cursor.  
- **Dedupe**: use event_id + esp + campaign_id unique constraint in ClickHouse/Postgres.  
- **Feature compute**: compute histograms as arrays and store as compact JSON or binary in Redis for fast reads.  
- **Model prototyping**: start with `lifelines` Cox or Aalen models and a smoothed hourly prior; move to PyTorch if needed.

---

### Metrics to track from day one
- **Operational**: webhook lag, backfill progress, connector error rate.  
- **Model**: Brier score, calibration by hour, log-likelihood.  
- **Business**: open rate lift in A/B tests, CTR lift, conversion lift.