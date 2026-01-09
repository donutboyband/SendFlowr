# SendFlowr — Negative Specification

## Explicit Non-Goals, Forbidden Behaviors, and Anti-Patterns

**Status**: Canonical
**Audience**: LLMs, contributors, reviewers
**Purpose**: Prevent architectural regression, scope creep, and incorrect abstractions

---

## 1. What SendFlowr Is NOT

SendFlowr is **not**:

* An ESP
* A campaign builder
* A content optimization tool
* A subject-line generator
* A CRM
* A marketing automation suite
* A deterministic rules engine
* A real-time message dispatcher
* A batch scheduler

Any design or implementation that moves SendFlowr toward these roles is **invalid by definition**.

---

## 2. Forbidden Time Abstractions

The following are **explicitly disallowed** as primary timing primitives:

* “Best hour”
* “Best day”
* Fixed cron schedules
* Quarter-hour slots (:00, :15, :30)
* Window-based scheduling (“send between 9–11am”)
* Static timezone-based heuristics

**Rule**

> All timing logic must be reducible to **minute-level continuous probability curves**.
> Any abstraction that cannot be expressed at minute resolution is invalid.

---

## 3. Forbidden Deterministic Logic

SendFlowr must **never** rely on:

* Hard rules like:

  * “If last open < 7 days, send”
  * “If user is active, send immediately”
* Binary segmentation logic as a final decision step
* One-to-one trigger → send execution

**Rule**

> All decisions must be probabilistic, weighted, and explainable.
> Deterministic logic may exist only as **guardrails**, never as decision engines.

---

## 4. Forbidden ESP Coupling

The following are **architectural violations**:

* Embedding ESP-specific concepts (lists, campaigns, flows) into core logic
* Assuming reliable or immediate ESP execution
* Assuming a single ESP per brand
* Storing learned intelligence inside ESP-native constructs

**Rule**

> ESPs are **replaceable execution pipes**.
> If removing an ESP breaks SendFlowr’s intelligence, the design is wrong.

---

## 5. Forbidden Execution Models

SendFlowr must **not**:

* Fire individual API calls per user at send time
* Depend on synchronous ESP responses
* Attempt to bypass ESP rate limits with retries
* Assume delivery == trigger time

**Rule**

> Execution must be **latency-aware and batch-amortized**.
> Micro-batching and shadow segmentation are mandatory abstractions.

---

## 6. Forbidden Metric Dependence (MPP Reality)

The following metrics must **never** be treated as ground truth:

* Open rate
* Pixel-based open timestamps
* Any signal not resilient to Apple MPP–style proxying

**Rule**

> Opens are weak signals.
> Clicks, conversions, replies, and real-time activity dominate all inference.

Any model that optimizes directly for open rate is invalid.

---

## 7. Forbidden Identity Assumptions

SendFlowr must **not** assume:

* Stable cookies
* Persistent device IDs
* Guaranteed deterministic identity resolution
* Single-channel identity sources

**Rule**

> Identity is probabilistic, layered, and auditable.
> Failure to resolve identity must degrade gracefully, not fail hard.

---

## 8. Forbidden Black-Box Behavior

The following are **explicitly disallowed**:

* Unexplainable timing decisions
* Hidden feature importance
* Non-reconstructable outputs
* “The model decided” as an explanation

**Rule**

> Every decision must be explainable post hoc.
> If a human cannot understand *why* an email was sent at a given minute, the system is incomplete.

---

## 9. Forbidden Autonomy Models

SendFlowr must **not**:

* Take irreversible actions without guardrails
* Override suppression logic
* Optimize aggressively without confidence thresholds
* Remove human override paths

**Rule**

> Autonomy must be earned gradually.
> Champion/challenger, shadow mode, and confidence gating are required patterns.

---

## 10. Forbidden Data Ownership Patterns

SendFlowr must **never**:

* Lock learned intelligence inside proprietary formats
* Prevent brands from exporting timing models or history
* Require full ESP migration to extract value

**Rule**

> Intelligence belongs to the brand.
> Anything that recreates a “walled garden” is a strategic failure.

---

## 11. Forbidden Optimization Goals

SendFlowr must **not** optimize for:

* Maximum volume
* Maximum send frequency
* Inbox flooding
* Vanity engagement metrics

**Rule**

> The system optimizes for **right moment**, not **more messages**.
> Knowing when *not* to send is a first-class outcome.

---

## 12. Anti-Patterns (Immediate Rejection)

If any of the following appear in code, docs, or design discussions, they are red flags:

* “Let’s just schedule it at 9am”
* “The ESP will handle that”
* “We can fix it with retries”
* “Opens are good enough”
* “We don’t need explainability yet”
* “We’ll add latency later”
* “This is basically STO but better”

---

## 13. LLM Enforcement Instructions (Implicit)

When generating code, schemas, or designs:

* Reject hour-based logic
* Reject deterministic triggers
* Reject ESP assumptions
* Reject black-box outputs
* Reject open-rate optimization
* Reject synchronous execution models

If a proposed solution violates **any** rule above, it must be discarded.

---

## Final Constraint

> If SendFlowr ever behaves like a smarter scheduler instead of a **probabilistic, latency-aware timing intelligence layer**, the system has failed its core thesis.
