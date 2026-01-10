# Synthetic Data Generation for ML Training

## Problem

Currently we have only **380 events** across **10 users** over **8 days**. This is insufficient for ML training:

- Minute-level models need dense temporal coverage
- Click prediction requires 100s-1000s of click events per user
- Persona detection needs variety in behavioral patterns
- Cold-start handling requires testing with new users

## Solution

Generate **synthetic data** with realistic patterns:

### User Personas (350 users total)

| Persona | Count | Peak Hours | Active Days | Click Rate | Open Rate |
|---------|-------|------------|-------------|------------|-----------|
| **morning_person** | 50 | 7-9 AM | Weekdays | 15% | 35% |
| **evening_person** | 50 | 6-10 PM | All days | 18% | 40% |
| **night_owl** | 30 | 10 PM-2 AM | Weekends | 12% | 28% |
| **lunch_browser** | 40 | 12-1 PM | Weekdays | 20% | 45% |
| **weekend_warrior** | 35 | 10 AM-4 PM | Weekends | 25% | 50% |
| **commuter** | 45 | 8-9 AM, 5-6 PM | Weekdays | 16% | 38% |
| **sporadic** | 50 | Random | All days | 8% | 20% |
| **highly_engaged** | 20 | Multiple peaks | All days | 35% | 65% |
| **low_engaged** | 30 | Rare | All days | 3% | 10% |

### Data Volume

**Time Period**: 101 days (Oct 1, 2025 - Jan 10, 2026)

**Expected Events**:
- Total: ~500,000-1,000,000 events
- Per user: ~1,500-3,000 events
- Clicks: ~80,000-120,000
- Opens: ~150,000-200,000

### Realistic Event Sequences

```
sent → delivered (99%, 1-30s delay)
     → opened (varies by persona, 1min-48hr delay)
          → clicked (conditional on open, 1-60min delay)
```

## Usage

### 1. Show Summary
```bash
python3 scripts/generate-synthetic-data.py --summary
```

Output:
```
📊 Expected Data Summary:
  Total Users: 350
  Time Period: 101 days
  Expected Events: ~70,700 (rough estimate)
```

### 2. Dry Run (Calculate without publishing)
```bash
python3 scripts/generate-synthetic-data.py --dry-run
```

This will:
- Generate all events in memory
- Count totals
- NOT publish to Kafka
- ~1-2 minutes to complete

### 3. Generate Real Data
```bash
# Make sure services are running
docker-compose up -d

# Start consumer first (to process events)
cd src/SendFlowr.Consumer && dotnet run &

# Generate data (WARNING: creates ~500K-1M events!)
python3 scripts/generate-synthetic-data.py
```

This will:
- Generate 101 days of synthetic data
- Publish to Kafka topic `email-events`
- Consumer writes to ClickHouse
- Takes ~5-10 minutes

## Dependencies

```bash
pip install confluent-kafka numpy
```

Or use dry-run mode without Kafka:
```bash
python3 scripts/generate-synthetic-data.py --dry-run
```

## Why This Helps ML

### 1. Dense Temporal Coverage
- Events across all 10,080 minute slots
- Multiple observations per slot
- Seasonal/weekly patterns emerge

### 2. Persona Diversity
- 9 distinct behavioral patterns
- Varying engagement levels
- Different time-of-day preferences

### 3. Click Prediction
- 80K-120K click events
- Conditional on opens (realistic)
- Time delays modeled

### 4. Model Validation
- Holdout sets for testing
- Cold-start scenarios (new users)
- Confidence calibration

### 5. Feature Engineering
- Sufficient data for minute-level histograms
- Smooth continuous curves
- Recency/frequency patterns

## Data Quality

### Realistic Aspects
✅ Temporal patterns (time of day, day of week)
✅ Event sequences (sent → delivered → opened → clicked)
✅ Variable delays (exponential distribution)
✅ Persona-specific behavior
✅ Campaign variations
✅ Conditional probabilities (click|open)

### Limitations
⚠️ No seasonality (holidays, summer slumps)
⚠️ No email fatigue modeling
⚠️ No A/B testing effects
⚠️ Fixed personas (no drift over time)
⚠️ No deliverability issues (99% delivered)

## Validation

After generation, verify:

```bash
# Total events
curl 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
  -d 'SELECT count() FROM sendflowr.email_events'

# Events by type
curl 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
  -d 'SELECT event_type, count() FROM sendflowr.email_events GROUP BY event_type'

# Users with most clicks
curl 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
  -d 'SELECT recipient_id, countIf(event_type = '\''clicked'\'') as clicks 
      FROM sendflowr.email_events 
      GROUP BY recipient_id 
      ORDER BY clicks DESC 
      LIMIT 10'

# Time distribution
curl 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
  -d 'SELECT toHour(timestamp) as hour, count() as events
      FROM sendflowr.email_events
      WHERE event_type = '\''clicked'\''
      GROUP BY hour
      ORDER BY hour'
```

## Next Steps

After generating synthetic data:

1. **Recompute Features**
   ```bash
   curl -X POST http://localhost:8001/compute-features
   ```

2. **Validate Curves**
   - Check confidence scores (should be higher)
   - Verify peak windows match personas
   - Test predictions on holdout users

3. **Model Training**
   - Train on 80% of users
   - Validate on 20% holdout
   - Measure RMSE, MAE on click timing

4. **Feature Engineering**
   - Minute-level curves should be smooth
   - Personas should be detectable
   - Recency/frequency should correlate

## Alternatives

If synthetic data isn't sufficient:

1. **Use real production data** (with privacy measures)
2. **Augment with GANs** (generative models)
3. **Transfer learning** from similar domains
4. **Start with simple heuristics** (rule-based) then learn

## Example Output

```
🌸 Generating synthetic data for 350 users
📅 Date range: 2025-10-01 to 2026-01-10 (101 days)

📊 2025-10-01: 1,234 events | Total: 1,234
📊 2025-10-07: 1,189 events | Total: 8,456
📊 2025-11-01: 1,298 events | Total: 45,123
...
✅ Generated 543,210 total events
📧 Avg per user: 1,552 events

👥 Users by persona:
  morning_person      : 50 users
  evening_person      : 50 users
  night_owl           : 30 users
  ...
```
