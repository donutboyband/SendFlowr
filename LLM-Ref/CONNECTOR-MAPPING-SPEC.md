# SendFlowr Connector Mapping & Portability Spec

## Purpose
Document the user-facing intent story, the architectural layers, and the metadata contract that keeps SendFlowr’s Timing Layer portable across ESPs while still letting brands define *what* to send (e.g., a Klaviyo flow).

## User Story (Klaviyo example)
1. The brand defines an intent: `intent_id = promo_jan`, associates it with Klaviyo campaign `abc123` and template `promo-drip`, and marks it as eligible for hot-path promotion (e.g., Shopify `site_visit` events).
2. SendFlowr watches signals (clicks, circuit breakers, hot paths) and generates minute-level timing decisions (`target_minute_utc`, `trigger_timestamp_utc`, `confidence_score`, `explanation_ref`), packaging the intent metadata (`intent_id`, ESP campaign/template ids) with each output.
3. The connector service (SendFlowr-owned) receives the decision, resolves `intent_id`→Klaviyo trigger mappings from its config store, and schedules the appropriate Klaviyo API call at `trigger_timestamp_utc`, including the metadata for observability.
4. When migrating ESPs, only the connector configuration changes (`intent_id`→ESP trigger mapping); the timing intelligence, explanations, and metadata remain unchanged.

## Architecture Overview
| Layer | Responsibility |
|---|---|
| **Timing Layer (SendFlowr core)** | Produces canonical timing decisions per `LLM-Ref/spec.json`, tracks explainability in ClickHouse (`timing_explanations` table), emits context weights, and respects circuit breakers/hot paths. |
| **Connector Config Store & UI** | Allows operators to define intents, map signals (hot-path, suppression) to those intents, and bind intents to ESP campaign/template identifiers. Persisted config lives in SendFlowr so it can be updated independently of any ESP. |
| **Connector Execution Layer** | Pulls decisions from Kafka/API, reads metadata (`intent_id`, `campaign_id`, `template`, `explanation_ref`), resolves the right ESP trigger via the config store, and invokes the ESP API with the scheduled timestamp. |

## Metadata Contract
- `intent_id` (SendFlowr canonical tag) – user-defined identifier for a logical campaign or flow.
- `campaign_id`, `template`, `notification_id` – ESP-specific identifiers recorded in the config store.
- `trigger_timestamp_utc`, `target_minute_utc`, `latency_estimate_seconds` – timing signal for the ESP execution layer.
- `explanation_ref` – maps back to the ClickHouse `timing_explanations` row so operators can audit why the decision fired.

SendFlowr always emits the timing signal with metadata. The connector uses the metadata to look up the ESP action; if the brand switches ESPs, only the metadata→ESP mapping changes.

## UI/DB Needs
- Store intent definitions, eligible signals (hot path types, suppression sources), and ESP bindings in a SendFlowr-controlled database.
- UI should let operators visually connect hot-path events to intents and associate each intent with one or more ESP campaigns/templates.
- Connector service reads this config to determine which API call to make when a timing decision arrives.

## Portability Guardrails
* The Timing Layer never references ESP-specific APIs or templates; all ESP details live in the connector config layer.
* Configuration data is owned by SendFlowr, ensuring that migrating to a new ESP only requires updating mappings, not retraining timing logic.
* Every decision persisted in `timing_explanations` includes `intent_id`, `explanation_ref`, and context weights so the connector or UI can surface why a send was triggered regardless of execution platform.
