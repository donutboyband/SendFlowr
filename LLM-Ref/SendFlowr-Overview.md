# SendFlowr Technical Blueprint: The Timing Layer Pivot

This document is the **authoritative architectural reference** for SendFlowr.
Its purpose is to ensure **long-term development consistency**, especially when work is assisted by LLMs.

The system must remain:

* Backwards compatible with the original STO implementation
* Incrementally extensible toward the Timing Layer vision
* Deterministic, auditable, and explainable by default

---

## I. Current System State (Backwards Compatible)

This section defines **stable primitives**. New development must not invalidate these assumptions.

### Ingestion & Events

* **Ingestion Engine (C# / .NET 8)**

  * OAuth-based ESP connectors and webhook listeners.
  * All inbound events are normalized immediately into canonical form.
  * Backfills (≥90 days) and real-time ingestion use the same schema.

* **Canonical Event Store**

  * Single source of truth for all engagement events.
  * Events are append-only and replayable.
  * Schema evolution must be additive.

### Features & Inference

* **Baseline Feature Store (Redis)**

  * Hour-level engagement histograms, recency, and frequency features.
  * Features are precomputed and cached for low-latency reads.
  * These features remain valid inputs even after minute-level migration.

* **Inference API (FastAPI)**

  * Stateless service returning engagement probability curves.
  * API contract must remain stable as internal models evolve.
  * Supports both hourly and minute-resolution curves via the same interface.

**Invariant**: Hour-level STO must always remain available as a fallback path.

---

## II. The "Timing Layer" Vision: Core Technical Pillars

This section defines **directional constraints** for all new systems.

SendFlowr is not a scheduler.
It is a **Timing Decision Engine** whose output is a *precise trigger time*, not a window.

---

### 1. Minute-Level Resolution

**The Grid**

* The canonical time domain is **10,080 minute slots per week**.
* Hourly buckets are treated as a lossy projection of this grid.
* All new timing logic must be expressible at minute resolution.

**The Model**

* Timing intent is represented as **continuous probability curves**.
* Discrete histograms may be used only as priors or cold-start fallbacks.
* Curves must support interpolation at arbitrary minute offsets.

**Invariant**: No new feature or model may assume fixed scheduling boundaries.

---

### 2. Predictive Latency Arbitrage

**The Problem**

* ESP and ISP latency materially affects delivery timing.
* “Scheduled time” is not “inbox arrival time”.

**The Solution**

* **Latency Tracker**

  * Measures ESP queue depth and delivery lag continuously.
  * Latency is modeled as a time-varying signal, not a constant.

* **Predictive Offset Logic**

  * All send decisions are computed relative to observed latency:

```
TriggerTime = TargetMinute − CurrentLatencyEstimate
```

* **Shadow Segmentation**

  * Recipient sets are partitioned to avoid synchronized bursts.

**Invariant**: All timing decisions must account for delivery latency explicitly.

---

### 3. Contextual "Circuit Breakers" & "Hot Paths"

Timing decisions are **stateful** and must respond to real-time context.

**Hot Paths (Acceleration)**

* Real-time intent signals (e.g., Shopify browsing, SMS clicks)
* Temporarily increase propensity and bias delivery toward immediate minutes.
* Effects are short-lived and decay unless reinforced.

**Circuit Breakers (Suppression)**

* Negative context (e.g., active Zendesk/Gorgias ticket)
* Forces propensity to zero for a defined cooldown window.
* Overrides all other signals.

**Invariant**: Suppression signals always dominate acceleration signals.

---

### 4. Data Sovereignty (Headless Architecture)

**Intelligence Decoupling**

* SendFlowr owns:

  * Timing logic
  * Identity resolution
  * Learning state
* ESPs execute sends but do not own intelligence.

**Algorithm Portability**

* Historical data and learned timing models are portable across ESPs.
* No optimization state is lost when switching execution providers.

**Invariant**: No ESP-specific assumption may leak into core timing logic.

---

## III. Augmented Technical Roadmap (Solo Engineer)

This roadmap defines **allowed evolution paths**.

| Phase         | Goal                      | Key Modules                                                   |
| ------------- | ------------------------- | ------------------------------------------------------------- |
| **Phase 1–4** | Foundation                | OAuth, Webhooks, Event Store, Hourly Histograms *(Completed)* |
| **Phase 5**   | Minute-Level Intelligence | 10,080-slot grid, continuous curves, click prioritization     |
| **Phase 6**   | Universal ID & EDA        | Identity stitching, event-driven hot paths                    |
| **Phase 7**   | Latency Engine            | Latency tracker, shadow segmentation, predictive offsets      |
| **Phase 8**   | Glass-Box UI              | Decision audit logs, confidence meters, explainability        |

**Constraint**: Each phase must be independently deployable.

---

## IV. Core Schema & Logic (LLM Context)

This section defines **mathematical and logical contracts**.

### Probabilistic Scoring Logic

Final propensity is computed multiplicatively:

```
P_final = P_base × ∏ (1 + ω_i)
```

Where:

* ω ∈ ℝ and represents contextual influence
* Typical values:

  * +0.5 → high-intent signals
  * −1.0 → hard suppression

**Rules**

* Negative intent may zero out propensity.
* Weights are time-decaying and non-persistent.

---

### Identity Resolution Contract

All signals must resolve to a **Universal SendFlowr ID**.

**Primary Deterministic Keys**

* Hashed email
* Phone number (Twilio / Postscript)

**Secondary Probabilistic Keys**

* ESP user IDs (e.g., Klaviyo `k_id`)
* Shopify `customer_id`
* IP / device signatures

**Rules**

* Merges are idempotent.
* No destructive overwrites.
* Resolution steps must be auditable.

---

### Final LLM Guidance (Implicit)

When generating:

* schemas → assume minute-level timing is canonical
* services → assume ESP latency exists and varies
* models → assume continuous time, not buckets
* integrations → assume ESPs are replaceable

This document supersedes informal assumptions.