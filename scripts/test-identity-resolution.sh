#!/bin/bash
# Identity Resolution Testing Script

set -e

API_URL="http://localhost:8001"

echo "=================================================="
echo "SendFlowr Identity Resolution Testing"
echo "=================================================="
echo ""

# Test 1: Create new identity with email + phone
echo "TEST 1: Create new identity (email + phone)"
echo "---------------------------------------------------"
curl -s -X POST "${API_URL}/resolve-identity?email=alice@example.com&phone=4155551234" | python -m json.tool
echo ""
echo ""

# Test 2: Resolve same email (should return same Universal ID)
echo "TEST 2: Idempotent resolution (same email)"
echo "---------------------------------------------------"
curl -s -X POST "${API_URL}/resolve-identity?email=alice@example.com" | python -m json.tool
echo ""
echo ""

# Get the email hash for linking
EMAIL_HASH=$(python -c "import hashlib; print(hashlib.sha256('alice@example.com'.lower().encode()).hexdigest())")

# Test 3: Link Klaviyo ID to email
echo "TEST 3: Link Klaviyo ID to email"
echo "---------------------------------------------------"
curl -s -X POST "${API_URL}/link-identifiers?identifier_a=${EMAIL_HASH}&type_a=email_hash&identifier_b=k_alice123&type_b=klaviyo_id&weight=1.0&source=test_script" | python -m json.tool
echo ""
echo ""

# Test 4: Resolve via Klaviyo ID (should find same Universal ID)
echo "TEST 4: Probabilistic resolution (Klaviyo ID only)"
echo "---------------------------------------------------"
curl -s -X POST "${API_URL}/resolve-identity?klaviyo_id=k_alice123" | python -m json.tool
echo ""
echo ""

# Test 5: Link Shopify customer ID
echo "TEST 5: Link Shopify customer ID"
echo "---------------------------------------------------"
curl -s -X POST "${API_URL}/link-identifiers?identifier_a=${EMAIL_HASH}&type_a=email_hash&identifier_b=shopify_12345&type_b=shopify_customer_id&weight=1.0&source=test_script" | python -m json.tool
echo ""
echo ""

# Test 6: Resolve via Shopify ID (should find same Universal ID)
echo "TEST 6: Probabilistic resolution (Shopify ID only)"
echo "---------------------------------------------------"
curl -s -X POST "${API_URL}/resolve-identity?shopify_customer_id=shopify_12345" | python -m json.tool
echo ""
echo ""

# Test 7: Timing decision with multiple identity keys
echo "TEST 7: Timing decision with identity resolution"
echo "---------------------------------------------------"
curl -s -X POST "${API_URL}/timing-decision" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com",
    "klaviyo_id": "k_alice123",
    "shopify_customer_id": "shopify_12345",
    "send_after": "2026-01-10T00:00:00Z",
    "send_before": "2026-01-17T00:00:00Z",
    "latency_estimate_seconds": 300
  }' | python -m json.tool
echo ""
echo ""

echo "=================================================="
echo "Database Verification"
echo "=================================================="
echo ""

echo "Identity Audit Log:"
echo "---------------------------------------------------"
docker exec -i sendflowr-clickhouse clickhouse-client --query "
SELECT 
    universal_id,
    input_type,
    resolution_step,
    confidence_score,
    created_at
FROM sendflowr.identity_audit_log
WHERE universal_id LIKE 'sf_%'
ORDER BY created_at DESC
LIMIT 10
FORMAT Pretty"
echo ""

echo "Identity Graph:"
echo "---------------------------------------------------"
docker exec -i sendflowr-clickhouse clickhouse-client --query "
SELECT 
    identifier_type_a,
    identifier_type_b,
    weight,
    source,
    created_at
FROM sendflowr.identity_graph
ORDER BY created_at DESC
LIMIT 10
FORMAT Pretty"
echo ""

echo "Resolved Identities Cache:"
echo "---------------------------------------------------"
docker exec -i sendflowr-clickhouse clickhouse-client --query "
SELECT 
    identifier_type,
    universal_id,
    confidence_score,
    last_seen
FROM sendflowr.resolved_identities
WHERE universal_id LIKE 'sf_%'
ORDER BY last_seen DESC
LIMIT 10
FORMAT Pretty"
echo ""

echo "=================================================="
echo "All Tests Complete!"
echo "=================================================="
