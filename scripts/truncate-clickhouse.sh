#!/bin/bash
# Truncate all ClickHouse data to start fresh
# Usage: ./scripts/truncate-clickhouse.sh

set -e

echo "🗑️  Truncating all ClickHouse data..."
echo ""

# Truncate main email_events table
docker exec sendflowr-clickhouse clickhouse-client --query "TRUNCATE TABLE sendflowr.email_events"
echo "✅ Truncated sendflowr.email_events"

# Truncate materialized views (they'll repopulate from source on INSERT)
docker exec sendflowr-clickhouse clickhouse-client --query "TRUNCATE TABLE sendflowr.email_events_deduped" 2>/dev/null || true
echo "✅ Truncated sendflowr.email_events_deduped (if exists)"

docker exec sendflowr-clickhouse clickhouse-client --query "TRUNCATE TABLE sendflowr.latency_training_mv" 2>/dev/null || true
echo "✅ Truncated sendflowr.latency_training_mv (if exists)"

# Truncate identity tables
docker exec sendflowr-clickhouse clickhouse-client --query "TRUNCATE TABLE sendflowr.identity_map" 2>/dev/null || true
echo "✅ Truncated sendflowr.identity_map (if exists)"

docker exec sendflowr-clickhouse clickhouse-client --query "TRUNCATE TABLE sendflowr.identity_links" 2>/dev/null || true
echo "✅ Truncated sendflowr.identity_links (if exists)"

# Truncate explanations table
docker exec sendflowr-clickhouse clickhouse-client --query "TRUNCATE TABLE sendflowr.timing_explanations" 2>/dev/null || true
echo "✅ Truncated sendflowr.timing_explanations (if exists)"

echo ""
echo "🌸 All ClickHouse data truncated. Ready for fresh start!"
