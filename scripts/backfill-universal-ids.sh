#!/bin/bash
# Backfill universal_id for existing email_events
# 
# This script resolves all recipient_id values to universal_id
# and updates the email_events table.

set -e

echo "=================================================="
echo "Backfilling universal_id in email_events"
echo "=================================================="
echo ""

API_URL="http://localhost:8001"

# Check if API is running
if ! curl -s "$API_URL/health" > /dev/null 2>&1; then
    echo "❌ Error: Inference API is not running on $API_URL"
    echo "   Start it with: cd src/SendFlowr.Inference && python main.py"
    exit 1
fi

echo "✅ API is running"
echo ""

# Get distinct recipient_ids from email_events
echo "Step 1: Fetching distinct recipient_ids..."
RECIPIENT_IDS=$(docker exec -i sendflowr-clickhouse clickhouse-client --query "
SELECT DISTINCT recipient_id
FROM sendflowr.email_events
WHERE universal_id = ''
  AND recipient_id != ''
LIMIT 1000
FORMAT TSV
")

TOTAL=$(echo "$RECIPIENT_IDS" | wc -l | tr -d ' ')
echo "Found $TOTAL recipient_ids to resolve"
echo ""

# Resolve each recipient_id to universal_id
echo "Step 2: Resolving identities..."
RESOLVED=0
FAILED=0

while IFS= read -r recipient_id; do
    if [ -z "$recipient_id" ]; then
        continue
    fi
    
    # Try to resolve as email first
    RESOLUTION=$(curl -s -X POST "${API_URL}/resolve-identity?email=${recipient_id}" 2>/dev/null || echo "")
    
    if [ -z "$RESOLUTION" ]; then
        # Try as phone
        RESOLUTION=$(curl -s -X POST "${API_URL}/resolve-identity?phone=${recipient_id}" 2>/dev/null || echo "")
    fi
    
    if [ -z "$RESOLUTION" ]; then
        # Fallback: use recipient_id as-is (create new Universal ID)
        RESOLUTION=$(curl -s -X POST "${API_URL}/resolve-identity?esp_user_id=${recipient_id}" 2>/dev/null || echo "")
    fi
    
    # Extract universal_id from JSON response
    UNIVERSAL_ID=$(echo "$RESOLUTION" | python3 -c "import sys, json; print(json.load(sys.stdin).get('universal_id', ''))" 2>/dev/null || echo "")
    
    if [ -n "$UNIVERSAL_ID" ]; then
        # Update email_events with universal_id
        docker exec -i sendflowr-clickhouse clickhouse-client --query "
        ALTER TABLE sendflowr.email_events
        UPDATE universal_id = '${UNIVERSAL_ID}'
        WHERE recipient_id = '${recipient_id}'
          AND universal_id = ''
        " 2>/dev/null
        
        ((RESOLVED++))
        echo "✅ Resolved: $recipient_id → $UNIVERSAL_ID"
    else
        ((FAILED++))
        echo "❌ Failed: $recipient_id"
    fi
done <<< "$RECIPIENT_IDS"

echo ""
echo "=================================================="
echo "Backfill Complete"
echo "=================================================="
echo "Resolved: $RESOLVED"
echo "Failed:   $FAILED"
echo ""

# Verify results
UNRESOLVED=$(docker exec -i sendflowr-clickhouse clickhouse-client --query "
SELECT COUNT(*)
FROM sendflowr.email_events
WHERE universal_id = ''
FORMAT TSV
")

echo "Remaining unresolved events: $UNRESOLVED"
echo ""

if [ "$UNRESOLVED" -eq 0 ]; then
    echo "✅ All events have been resolved to universal_id!"
else
    echo "⚠️  Some events still need resolution. Run this script again."
fi
