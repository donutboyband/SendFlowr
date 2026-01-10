# Synthetic Data Generator - SendFlowr ML Training

## Critical Design Principles

This generator creates realistic email engagement data for training SendFlowr's timing intelligence layer, following the architectural spec from LLM-Ref.

## Key Features

### 1. ✅ ESP Latency Modeling

**Realistic congestion modeling** for latency-aware timing:

```python
def _sample_esp_latency(send_time):
    base = lognormal(median=12s)
    
    # Top-of-hour congestion (3-6x slower)
    if minute in [0, 1, 2]:
        base *= 3.0-6.0
    
    # Morning/evening batch pressure (1.5-2.5x slower)
    if hour in [8, 9, 18, 19]:
        base *= 1.5-2.5
    
    # Weekends are faster (0.7x)
    if weekend:
        base *= 0.7
```

**ML Impact**: Model learns **when to trigger** to hit target delivery window

---

### 2. ✅ Engagement Based on DELIVERY Time

**Critical**: Engagement is checked against **delivery time**, not send time:
```python
delivered_time = send_time + esp_latency
should_engage = _should_engage_at_time(user, delivered_time)  # ✅
```

**Why This Matters**: Users engage when they **receive** email, not when you sent it.

---

### 3. ✅ Minute-Level Intent Spikes

**Specific minute boosts** for granular patterns:

```python
# Peak minutes per persona
peak_minutes = [15, 22, 38, 47]

if minute in peak_minutes:
    engagement_prob *= 1.3  # 30% boost

# Top-of-hour fatigue
if minute in [0, 1, 59]:
    engagement_prob *= 0.7  # 30% penalty
```

**ML Impact**: Learns why **18:47 beats 18:00** (everyone's inbox slammed at top of hour)

---

### 4. ✅ Circuit Breaker Events

**Negative intent events** for suppression logic:

```python
# Generate suppression events
{
  "event_type": "support_ticket",
  "timestamp": "...",
  "source": "zendesk"
}

# Suppress engagement for 48h after
circuit_breaker_until = timestamp + 48h
```

**Event Types**:
- `support_ticket` → 48h suppression
- `complaint` → 48h suppression  
- `unsubscribe_request` → 168h (1 week) suppression

**ML Impact**: Trains confidence collapse and "do not send" outcomes

---

### 5. ✅ Hot Path Boosts

**Problem**: V1 had no acceleration signals  
**Solution**: Real-time activity boosts

```python
# Generate hot path events
{
  "event_type": "site_visit",  # or sms_click, product_view
  "timestamp": "...",
  "metadata": {"hot_path": true}
}

# Boost engagement within 30 min (exponential decay)
if minutes_since_hot_path < 30:
    engagement_mult = 2.0 * exp(-minutes / 15)
```

**ML Impact**: Trains event-driven overrides and recency weighting

---

### 6. ✅ Campaign Fatigue

**Problem**: V1 had static engagement rates  
**Solution**: Decay after repeated sends

```python
# Track sends in last 24h
recent_sends = count_sends_last_24h(user)

if recent_sends == 0:
    fatigue_mult = 1.0
elif recent_sends == 1:
    fatigue_mult = 0.95
elif recent_sends == 2:
    fatigue_mult = 0.85
elif recent_sends >= 3:
    fatigue_mult = 0.60  # Significant fatigue
```

**ML Impact**: Teaches **when NOT to send**

---

### 7. ✅ Confidence Drift

**Problem**: V1 personas were perfectly static (overfitting risk)  
**Solution**: Slow drift over time

```python
# Monthly drift
config['click_rate'] *= random.uniform(0.998, 1.002)
config['open_rate'] *= random.uniform(0.998, 1.002)
```

**ML Impact**: Prevents overfitting to exact persona parameters

---

## How to Use

### Generate V2 Data

```bash
# See summary
python3 scripts/generate-synthetic-data-v2.py --summary

# Dry run (no Kafka)
python3 scripts/generate-synthetic-data-v2.py --dry-run

# Generate for real
pip install confluent-kafka
python3 scripts/generate-synthetic-data-v2.py
```

### Recompute Features

```bash
# After generation, recompute minute-level features
curl -X POST http://localhost:8001/compute-features
```

### Validate

```bash
# Check events by type
curl 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
  -d "SELECT event_type, count() FROM sendflowr.email_events GROUP BY event_type"

# Check latency tracking
curl 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
  -d "SELECT avg(latency_seconds), quantile(0.5)(latency_seconds), quantile(0.95)(latency_seconds)
      FROM sendflowr.email_events 
      WHERE event_type = 'delivered' AND latency_seconds > 0"

# Check circuit breakers
curl 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
  -d "SELECT event_type, count() FROM sendflowr.email_events 
      WHERE event_type IN ('support_ticket', 'complaint', 'unsubscribe_request')
      GROUP BY event_type"

# Check hot paths
curl 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
  -d "SELECT event_type, count() FROM sendflowr.email_events 
      WHERE event_type IN ('site_visit', 'sms_click', 'product_view')
      GROUP BY event_type"
```

---

## Data Volume

**V1**: ~71K events  
**V2**: ~80-100K events (includes circuit breakers, hot paths)

**Breakdown**:
- Email events: ~71K (sent, delivered, opened, clicked)
- Circuit breakers: ~700-1000 (1% of users)
- Hot paths: ~3500-5000 (5% occurrence rate)

---

## ML Training Now Possible

### V1 Could Train
✅ When users like to engage (time of day, day of week)  
✅ Persona clustering  
✅ Continuous curve generation

### V2 Additionally Trains
✅ **When to trigger** to hit target window (latency offset)  
✅ **Why top-of-hour is bad** (congestion penalties)  
✅ **Suppression logic** (circuit breakers)  
✅ **Acceleration logic** (hot paths)  
✅ **Fatigue modeling** (when not to send)  
✅ **Confidence gating** (drift + uncertainty)

---

## Expected Confidence Improvements

**Before V1 Data**: 4% confidence (380 events, sparse)  
**After V1 Data**: 30-40% confidence (better curves)  
**After V2 Data**: **60-80% confidence** (full timing layer signals)

---

## Validation Queries

### Latency Distribution
```sql
SELECT 
    toHour(timestamp) as hour,
    toStartOfMinute(timestamp) as minute,
    avg(latency_seconds) as avg_latency,
    quantile(0.95)(latency_seconds) as p95_latency
FROM sendflowr.email_events
WHERE event_type = 'delivered' AND latency_seconds > 0
GROUP BY hour, minute
ORDER BY hour, minute
```

**Expected**: Spikes at top-of-hour (:00-:02) and peak send times (8-9 AM, 6-7 PM)

### Hot Path Impact
```sql
-- Users who had hot path events
WITH hot_path_users AS (
    SELECT DISTINCT recipient_id
    FROM sendflowr.email_events
    WHERE event_type IN ('site_visit', 'sms_click', 'product_view')
)
SELECT 
    h.recipient_id,
    countIf(e.event_type = 'clicked') as clicks,
    countIf(e.event_type = 'opened') as opens
FROM hot_path_users h
JOIN sendflowr.email_events e ON h.recipient_id = e.recipient_id
GROUP BY h.recipient_id
ORDER BY clicks DESC
LIMIT 10
```

**Expected**: Hot path users should have higher click rates

### Circuit Breaker Effectiveness
```sql
-- Events after circuit breaker
SELECT 
    recipient_id,
    event_type,
    timestamp
FROM sendflowr.email_events
WHERE recipient_id IN (
    SELECT DISTINCT recipient_id 
    FROM sendflowr.email_events 
    WHERE event_type = 'support_ticket'
)
ORDER BY recipient_id, timestamp
```

**Expected**: Minimal engagement 48h after support tickets

---

## Differences from V1

| Feature | V1 | V2 |
|---------|----|----|
| Latency | Uniform 1-30s | Congestion-aware (log-normal + spikes) |
| Engagement Timing | Based on send time ❌ | Based on delivery time ✅ |
| Minute Spikes | None | Per-persona peak minutes |
| Circuit Breakers | None | Support tickets, complaints, unsubscribes |
| Hot Paths | None | Site visits, SMS clicks, product views |
| Fatigue | None | Decay after 3+ sends/24h |
| Drift | None | Monthly confidence drift |
| ML Training | Curves only | **Full timing layer** |

---

## Next Steps

1. **Generate V2 data** (~5 min)
2. **Recompute features** with latency awareness
3. **Validate latency distributions** (should see top-of-hour spikes)
4. **Train offset predictor** (trigger_time = target - predicted_latency)
5. **Test circuit breaker detection**
6. **Test hot path acceleration**
7. **Measure confidence improvement** (should be 60-80%)

---

## Summary

V2 transforms this from **"synthetic email data"** into **"SendFlowr-native training data"**.

Now you can train:
- ✅ Latency arbitrage (the core value prop!)
- ✅ Suppression logic
- ✅ Acceleration logic  
- ✅ Fatigue modeling
- ✅ Confidence gating

This is **production-ready ML training data**. 🚀
