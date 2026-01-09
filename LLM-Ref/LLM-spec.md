
# SendFlowr Timing Layer — System Specification (LLM Reference)

**Status**: Canonical
**Audience**: LLMs, future contributors, code generators
**Purpose**: Enforce architectural consistency and prevent semantic drift

---

## 0. System Identity

* **System Name**: SendFlowr
* **System Type**: Headless Timing Intelligence Layer
* **Primary Output**: Precise message trigger timestamps
* **Non-Goals**:

  * Campaign UI ownership
  * ESP execution logic
  * Content generation
  * Inbox placement heuristics

---

## 1. Backwards Compatibility Contract

### 1.1 STO Fallback Requirement

* Hour-level Send Time Optimization MUST remain supported.
* Minute-level logic MUST degrade gracefully to hourly resolution.

### 1.2 Schema Evolution Rules

* Canonical schemas are append-only.
* Field removal or semantic changes are forbidden.
* New timing fields must coexist with legacy fields.

---

## 2. Canonical Time Model

### 2.1 Time Grid

* Canonical time domain = **10,080 minute slots per week**
* All timing decisions MUST be representable as minute offsets.
* Hourly buckets are treated as derived projections only.

### 2.2 Continuous Representation

* Timing intent is represented as a **continuous probability function**.
* Discrete histograms MAY be used only as priors or cold-start fallbacks.
* All models MUST support interpolation at arbitrary minute indices.

---

## 3. Timing Decision Contract

### 3.1 Core Output

A timing decision MUST resolve to:

```
{
  universal_user_id,
  target_minute,
  trigger_timestamp,
  confidence_score,
  decision_explanation_ref
}
```

### 3.2 Trigger Computation

Trigger time MUST account for delivery latency:

```
trigger_timestamp = target_minute - latency_estimate
```

Latency is time-varying and MUST NOT be assumed constant.

---

## 4. Latency Model

### 4.1 Latency Tracker

* Measures ESP processing delay and queue depth.
* Latency is treated as a first-class signal.
* Historical latency curves MUST be retained.

### 4.2 Latency Usage Rules

* All send triggers MUST reference the latest latency estimate.
* Latency compensation is mandatory, not optional.

---

## 5. Contextual Signal Processing

### 5.1 Hot Paths (Acceleration)

* Signals indicating active user engagement (e.g., Shopify browse, SMS click).
* Effects:

  * Temporarily increase timing propensity.
  * Bias toward immediate minute slots.
* Effects MUST decay over time.

### 5.2 Circuit Breakers (Suppression)

* Signals indicating negative context (e.g., open support ticket).
* Effects:

  * Propensity forced to zero.
  * Suppression duration is configurable (default: 48h).
* Suppression MUST override all other signals.

---

## 6. Probabilistic Scoring Model

### 6.1 Base Curve

* `P_base(t)` represents historical timing intent over time.
* Derived from continuous or smoothed minute-level models.

### 6.2 Contextual Adjustment

Final propensity is computed as:

```
P_final(t) = P_base(t) × ∏ (1 + ω_i(t))
```

Where:

* ω_i ∈ ℝ
* Negative ω_i may force P_final(t) = 0
* Weights MUST be time-decaying and non-persistent

---

## 7. Identity Resolution

### 7.1 Universal ID

All decisions MUST reference a **Universal SendFlowr ID**.

### 7.2 Resolution Keys

**Primary (Deterministic)**

* Hashed email
* Phone number

**Secondary (Probabilistic)**

* ESP user IDs
* Commerce platform IDs
* IP / device signatures

### 7.3 Resolution Rules

* Merges are idempotent.
* No destructive overwrites.
* Resolution steps MUST be auditable.

---

## 8. Headless Architecture Rules

### 8.1 Intelligence Ownership

SendFlowr owns:

* Timing logic
* Learning state
* Identity resolution

ESPs own:

* Message delivery only

### 8.2 Portability Requirement

* Switching ESPs MUST NOT reset timing models or historical learning.
* No ESP-specific assumptions may exist in core logic.

---

## 9. Explainability & Auditability

### 9.1 Decision Logging

Every timing decision MUST log:

* Input signals
* Applied weights
* Latency estimate
* Final trigger timestamp

### 9.2 Transparency Contract

* Decisions must be reconstructable post hoc.
* “Black box” outputs are forbidden.

---

## 10. Evolution Constraints

* All new modules MUST:

  * Respect minute-level time as canonical
  * Account for latency
  * Preserve STO fallback
  * Remain ESP-agnostic
* Any deviation requires explicit spec revision.

---

## 11. Implicit LLM Instructions

When generating code or designs:

* Assume **continuous time**, not buckets
* Assume **latency exists and varies**
* Assume **real-time context matters**
* Assume **ESP execution is unreliable and replaceable**

This specification overrides informal assumptions.
