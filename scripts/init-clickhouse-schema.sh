#!/bin/bash
# Initialize ClickHouse with all SendFlowr tables
# Including identity resolution tables per LLM-spec.md §7

set -e

echo "=================================================="
echo "SendFlowr ClickHouse Schema Initialization"
echo "=================================================="
echo ""

CLICKHOUSE_CONTAINER="sendflowr-clickhouse"
CLICKHOUSE_CMD="docker exec -i $CLICKHOUSE_CONTAINER clickhouse-client"

# Check if ClickHouse is running
if ! docker ps | grep -q $CLICKHOUSE_CONTAINER; then
    echo "❌ Error: ClickHouse container '$CLICKHOUSE_CONTAINER' is not running"
    echo "   Run: docker-compose up -d"
    exit 1
fi

echo "✅ ClickHouse container is running"
echo ""

# 1. Create database
echo "Step 1: Creating database 'sendflowr'"
$CLICKHOUSE_CMD --query "CREATE DATABASE IF NOT EXISTS sendflowr"
echo "✅ Database created"
echo ""

# 2. Create email_events table
echo "Step 2: Creating email_events table"
$CLICKHOUSE_CMD < schemas/clickhouse-schema.sql
echo "✅ email_events table created"
echo ""

# 3. Create timing_explanations table
echo "Step 3: Creating timing_explanations table"
$CLICKHOUSE_CMD < schemas/clickhouse-explanations.sql
echo "✅ timing_explanations table created"
echo ""

# 4. Create identity resolution tables
echo "Step 4: Creating identity resolution tables"
$CLICKHOUSE_CMD < schemas/clickhouse-identity.sql
echo "✅ identity_graph table created"
echo "✅ identity_audit_log table created"
echo "✅ resolved_identities table created"
echo ""

# 5. Verify tables
echo "Step 5: Verifying tables"
TABLES=$($CLICKHOUSE_CMD --query "SHOW TABLES FROM sendflowr")
echo "$TABLES"
echo ""

EXPECTED_TABLES=(
    "email_events"
    "email_events_deduped"
    "identity_audit_log"
    "identity_graph"
    "resolved_identities"
    "timing_explanations"
)

for table in "${EXPECTED_TABLES[@]}"; do
    if echo "$TABLES" | grep -q "^$table$"; then
        echo "✅ $table"
    else
        echo "❌ $table (missing)"
    fi
done
echo ""

# 6. Show table counts
echo "Step 6: Table row counts"
echo "---------------------------------------------------"
for table in email_events identity_graph identity_audit_log resolved_identities timing_explanations; do
    COUNT=$($CLICKHOUSE_CMD --query "SELECT COUNT(*) FROM sendflowr.$table")
    printf "%-25s %10s rows\n" "$table:" "$COUNT"
done
echo ""

echo "=================================================="
echo "✅ Schema initialization complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Run inference API: cd src/SendFlowr.Inference && python main.py"
echo "  2. Test identity resolution: ./scripts/test-identity-resolution.sh"
echo "  3. API docs: http://localhost:8001/scalar"
echo ""
