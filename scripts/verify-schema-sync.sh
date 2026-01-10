#!/bin/bash
# Verify that schemas are in sync with production database

set -e

echo "=================================================="
echo "Schema Synchronization Verification"
echo "=================================================="
echo ""

CLICKHOUSE_CMD="docker exec -i sendflowr-clickhouse clickhouse-client"

echo "Checking email_events schema..."
ACTUAL_SCHEMA=$($CLICKHOUSE_CMD --query "DESCRIBE TABLE sendflowr.email_events FORMAT TSV" | grep -E "recipient_id|universal_id")

echo "$ACTUAL_SCHEMA"
echo ""

if echo "$ACTUAL_SCHEMA" | grep -q "universal_id"; then
    echo "✅ universal_id column exists"
else
    echo "❌ universal_id column MISSING"
    exit 1
fi

if echo "$ACTUAL_SCHEMA" | grep -q "recipient_id"; then
    echo "✅ recipient_id column exists (audit trail)"
else
    echo "❌ recipient_id column MISSING"
    exit 1
fi

echo ""
echo "Checking ORDER BY clause..."
ORDER_BY=$($CLICKHOUSE_CMD --query "SHOW CREATE TABLE sendflowr.email_events FORMAT TSV" | grep "ORDER BY")

if echo "$ORDER_BY" | grep -q "universal_id"; then
    echo "✅ ORDER BY uses universal_id"
    echo "   $ORDER_BY"
else
    echo "❌ ORDER BY does not use universal_id"
    echo "   $ORDER_BY"
    exit 1
fi

echo ""
echo "Checking data..."
$CLICKHOUSE_CMD --query "
SELECT 
    countIf(universal_id != '') as resolved,
    countIf(universal_id = '') as unresolved,
    count() as total
FROM sendflowr.email_events
FORMAT Pretty
"

echo ""
echo "=================================================="
echo "✅ Schema verification complete!"
echo "=================================================="
