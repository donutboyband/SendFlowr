# Test Scripts

## Quick Test Event Generation

### Generate All Test Events
```bash
./scripts/generate-test-events.sh
```

This generates:
- 100 random events (mixed types and users)
- 5 realistic user journeys (sent → delivered → opened → clicked)
- 12 events for a "heavy user" across multiple campaigns
- 5 low-engagement events
- 10 time-varied events

**Total: ~125 events**

### Run Comprehensive Test Suite
```bash
./scripts/run-tests.sh
```

This runs 5 test scenarios:
1. Single realistic user journey
2. Random events (10)
3. Cohort simulation (3 users)
4. Bulk load (50 events)
5. Kafka verification

**Total: ~73 events**

## Individual Test Commands

### Generate Random Events
```bash
# 10 events
curl -X POST "http://localhost:5215/api/mock/events/generate?count=10"

# 100 events
curl -X POST "http://localhost:5215/api/mock/events/generate?count=100"
```

### Generate Realistic Journey
```bash
# Single user journey (sent → delivered → opened → clicked)
curl -X POST "http://localhost:5215/api/mock/events/pattern?userId=user_001"

# Multiple users
for i in {1..5}; do
  curl -X POST "http://localhost:5215/api/mock/events/pattern?userId=user_00${i}"
done
```

## Verify Events

### Check Kafka
```bash
# View latest events
docker exec -it sendflowr-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic email-events \
  --from-beginning \
  --max-messages 10

# Monitor in real-time
docker exec -it sendflowr-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic email-events
```

### Check Event Counts
```bash
# Count messages in Kafka topic
docker exec sendflowr-kafka kafka-run-class kafka.tools.GetOffsetShell \
  --broker-list localhost:9092 \
  --topic email-events \
  --time -1 | awk -F ":" '{sum += $3} END {print sum}'
```

## Test Data Characteristics

### Users
- `user_001` through `user_005` - Regular users with realistic journeys
- `user_heavy` - High engagement, multiple campaigns
- `user_low_engage` - Opens emails but doesn't click
- `cohort_user_a/b/c` - Test cohort for A/B testing

### Campaigns
- `welcome_series` - Onboarding emails
- `weekly_newsletter` - Regular content
- `promo_jan` - Promotional campaign
- `re_engagement` - Win-back campaign

### Event Types Distribution
In realistic patterns:
- 25% sent
- 25% delivered
- 25% opened
- 25% clicked

In random generation:
- Random distribution across all types
- Random timestamps within last week

## Expected Output

After running `generate-test-events.sh`:
```
✅ Generated 100 random events
✅ Generated journey for user_001 (sent → delivered → opened → clicked)
✅ Generated journey for user_002 (sent → delivered → opened → clicked)
✅ Generated journey for user_003 (sent → delivered → opened → clicked)
✅ Generated journey for user_004 (sent → delivered → opened → clicked)
✅ Generated journey for user_005 (sent → delivered → opened → clicked)
✅ Generated 12 events for heavy user
✅ Generated 5 low-engagement events
✅ Generated 10 time-varied events

📈 Summary:
  - Total events: ~125
  - Events successfully published to Kafka
```

## Troubleshooting

### Connector not running
```bash
cd src/SendFlowr.Connectors
dotnet run
```

### Kafka not receiving events
```bash
# Check Kafka is running
docker ps | grep kafka

# Restart Kafka if needed
docker-compose restart kafka

# Check connector logs
# (Look at the terminal where dotnet run is executing)
```

### Clear Kafka topic (start fresh)
```bash
docker exec sendflowr-kafka kafka-topics \
  --delete --topic email-events \
  --bootstrap-server localhost:9092

docker exec sendflowr-kafka kafka-topics \
  --create --topic email-events \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1
```
