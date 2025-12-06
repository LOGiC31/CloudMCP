#!/bin/bash
# Script to test LLM fix workflow
# 1. Introduce failure
# 2. Validate failure
# 3. Call LLM to fix
# 4. Validate results

set -e

API_URL="http://localhost:8000"
SAMPLE_APP_URL="http://localhost:8001"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "🧪 LLM Fix Test Script"
echo "======================"
echo ""

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if services are running
print_status "Checking if services are running..."
if ! curl -s "${API_URL}/health" > /dev/null; then
    print_error "Backend API is not running on ${API_URL}"
    exit 1
fi

if ! curl -s "${SAMPLE_APP_URL}/health" > /dev/null 2>&1; then
    print_warning "Sample app may not be running on ${SAMPLE_APP_URL}"
fi

print_success "Services are running"
echo ""

# Step 0: Ensure resources start from HEALTHY state
print_status "Step 0: Ensuring resources start from HEALTHY state..."
echo ""

FAILURE_TYPE="${1:-redis}"  # Default to redis, can be: redis, database, or both

# Reset Redis to HEALTHY state
if [ "$FAILURE_TYPE" == "redis" ] || [ "$FAILURE_TYPE" == "both" ]; then
    print_status "Resetting Redis to HEALTHY state..."
    docker exec redis redis-cli FLUSHALL > /dev/null 2>&1
    sleep 2
    print_success "Redis flushed"
fi

# Reset PostgreSQL to HEALTHY state
if [ "$FAILURE_TYPE" == "database" ] || [ "$FAILURE_TYPE" == "both" ]; then
    print_status "Resetting PostgreSQL to HEALTHY state..."
    # Kill any long-running queries/connections (both active and idle)
    docker exec postgres psql -U postgres -d sample_app -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid();" > /dev/null 2>&1
    sleep 3
    print_success "PostgreSQL connections and queries cleared"
fi

# Verify both are HEALTHY
print_status "Verifying initial HEALTHY state..."
sleep 3

RESOURCES=$(curl -s "${API_URL}/api/resources")
REDIS_HEALTHY=$(echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
redis = [r for r in resources if r.get('name') == 'redis']
if redis:
    print('1' if redis[0].get('status') == 'HEALTHY' else '0')
else:
    print('0')
" 2>/dev/null || echo "0")

POSTGRES_HEALTHY=$(echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
pg = [r for r in resources if r.get('name') == 'postgres']
if pg:
    print('1' if pg[0].get('status') == 'HEALTHY' else '0')
else:
    print('0')
" 2>/dev/null || echo "0")

if [ "$FAILURE_TYPE" == "redis" ]; then
    if [ "$REDIS_HEALTHY" == "1" ]; then
        print_success "Redis is HEALTHY (ready for test)"
    else
        print_error "Redis is not HEALTHY. Status: $(echo "$RESOURCES" | python3 -c "import sys, json; resources = json.load(sys.stdin); redis = [r for r in resources if r.get('name') == 'redis']; print(redis[0].get('status') if redis else 'UNKNOWN')" 2>/dev/null)"
        exit 1
    fi
elif [ "$FAILURE_TYPE" == "database" ]; then
    if [ "$POSTGRES_HEALTHY" == "1" ]; then
        print_success "PostgreSQL is HEALTHY (ready for test)"
    else
        print_error "PostgreSQL is not HEALTHY. Status: $(echo "$RESOURCES" | python3 -c "import sys, json; resources = json.load(sys.stdin); pg = [r for r in resources if r.get('name') == 'postgres']; print(pg[0].get('status') if pg else 'UNKNOWN')" 2>/dev/null)"
        exit 1
    fi
else
    if [ "$REDIS_HEALTHY" == "1" ] && [ "$POSTGRES_HEALTHY" == "1" ]; then
        print_success "Both Redis and PostgreSQL are HEALTHY (ready for test)"
    else
        print_error "Not all resources are HEALTHY. Redis: $([ "$REDIS_HEALTHY" == "1" ] && echo "HEALTHY" || echo "NOT HEALTHY"), PostgreSQL: $([ "$POSTGRES_HEALTHY" == "1" ] && echo "HEALTHY" || echo "NOT HEALTHY")"
        exit 1
    fi
fi

echo ""
sleep 2

# Step 1: Introduce failure
print_status "Step 1: Introducing failure..."
echo ""

case "$FAILURE_TYPE" in
    redis)
        print_status "Filling Redis with data to cause memory pressure..."
        RESPONSE=$(curl -s -X POST "${SAMPLE_APP_URL}/load/redis?size_mb=250")
        if echo "$RESPONSE" | grep -q "Filled Redis"; then
            print_success "Redis failure introduced: $RESPONSE"
        else
            print_error "Failed to introduce Redis failure: $RESPONSE"
            exit 1
        fi
        ;;
    database)
        print_status "Creating database blocking queries (won't auto-recover)..."
        RESPONSE=$(curl -s -X POST "${SAMPLE_APP_URL}/load/database/blocking?queries=85")
        if echo "$RESPONSE" | grep -q "blocking queries"; then
            print_success "Database failure introduced: $RESPONSE"
        else
            print_error "Failed to introduce database failure: $RESPONSE"
            exit 1
        fi
        ;;
    both)
        print_status "Introducing both Redis and database failures..."
        curl -s -X POST "${SAMPLE_APP_URL}/load/redis?size_mb=250" > /dev/null
        curl -s -X POST "${SAMPLE_APP_URL}/load/database/blocking?queries=85" > /dev/null
        print_success "Both failures introduced (database uses blocking queries that won't auto-recover)"
        ;;
    *)
        print_error "Unknown failure type: $FAILURE_TYPE"
        print_status "Usage: $0 [redis|database|both]"
        exit 1
        ;;
esac

echo ""
sleep 2

# Step 2: Validate failure
print_status "Step 2: Validating failure..."
echo ""

# Wait for resource monitor to update (connections take time to establish)
if [ "$FAILURE_TYPE" == "database" ]; then
    print_status "Waiting for database connections to establish..."
    sleep 8
elif [ "$FAILURE_TYPE" == "redis" ]; then
    print_status "Waiting for Redis memory to be detected..."
    sleep 5
elif [ "$FAILURE_TYPE" == "both" ]; then
    print_status "Waiting for failures to be detected (database connections + Redis memory)..."
    sleep 8
else
    sleep 3
fi

# Check resource status
RESOURCES=$(curl -s "${API_URL}/api/resources")

# Filter by failure type
if [ "$FAILURE_TYPE" == "redis" ]; then
    TARGET_RESOURCE="redis"
    FAILED_COUNT=$(echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
redis = [r for r in resources if r.get('name') == 'redis']
if redis and redis[0].get('status') != 'HEALTHY':
    print('1')
else:
    print('0')
" 2>/dev/null || echo "0")
elif [ "$FAILURE_TYPE" == "database" ]; then
    TARGET_RESOURCE="postgres"
    FAILED_COUNT=$(echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
pg = [r for r in resources if r.get('name') == 'postgres']
if pg and pg[0].get('status') != 'HEALTHY':
    print('1')
else:
    print('0')
" 2>/dev/null || echo "0")
else
    # For "both", check all
    FAILED_COUNT=$(echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
failed = [r for r in resources if r.get('status') != 'HEALTHY']
print(len(failed))
" 2>/dev/null || echo "0")
fi

# Validate that resource is in DEGRADED status
if [ "$FAILURE_TYPE" == "redis" ]; then
    REDIS_STATUS=$(echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
redis = [r for r in resources if r.get('name') == 'redis']
print(redis[0].get('status') if redis else 'UNKNOWN')
" 2>/dev/null || echo "UNKNOWN")
    
    if [ "$REDIS_STATUS" == "DEGRADED" ] || [ "$REDIS_STATUS" == "FAILED" ]; then
        print_success "✅ Validation: Redis is in DEGRADED/FAILED status"
        echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
redis = [r for r in resources if r.get('name') == 'redis']
if redis:
    r = redis[0]
    metrics = r.get('metrics', {})
    mem_pct = metrics.get('redis_memory_usage_percent', 0)
    print(f\"  - Redis: {r.get('status')} (Memory: {mem_pct:.1f}%)\")
" 2>/dev/null
    else
        print_error "❌ Validation FAILED: Redis is not DEGRADED. Current status: $REDIS_STATUS"
        print_error "Expected: DEGRADED or FAILED, Got: $REDIS_STATUS"
        exit 1
    fi
elif [ "$FAILURE_TYPE" == "database" ]; then
    POSTGRES_STATUS=$(echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
pg = [r for r in resources if r.get('name') == 'postgres']
print(pg[0].get('status') if pg else 'UNKNOWN')
" 2>/dev/null || echo "UNKNOWN")
    
    if [ "$POSTGRES_STATUS" == "DEGRADED" ] || [ "$POSTGRES_STATUS" == "FAILED" ]; then
        print_success "✅ Validation: PostgreSQL is in DEGRADED/FAILED status"
        echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
pg = [r for r in resources if r.get('name') == 'postgres']
if pg:
    p = pg[0]
    metrics = p.get('metrics', {})
    conn_pct = metrics.get('connection_usage_percent', 0)
    total = metrics.get('total_connections', 0)
    max_conn = metrics.get('max_connections', 0)
    print(f\"  - PostgreSQL: {p.get('status')} (Connections: {total}/{max_conn} = {conn_pct:.1f}%)\")
" 2>/dev/null
    else
        print_error "❌ Validation FAILED: PostgreSQL is not DEGRADED. Current status: $POSTGRES_STATUS"
        print_error "Expected: DEGRADED or FAILED, Got: $POSTGRES_STATUS"
        exit 1
    fi
else
    # For "both", check both
    REDIS_STATUS=$(echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
redis = [r for r in resources if r.get('name') == 'redis']
print(redis[0].get('status') if redis else 'UNKNOWN')
" 2>/dev/null || echo "UNKNOWN")
    
    POSTGRES_STATUS=$(echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
pg = [r for r in resources if r.get('name') == 'postgres']
print(pg[0].get('status') if pg else 'UNKNOWN')
" 2>/dev/null || echo "UNKNOWN")
    
    if [ "$REDIS_STATUS" == "DEGRADED" ] || [ "$REDIS_STATUS" == "FAILED" ] || [ "$POSTGRES_STATUS" == "DEGRADED" ] || [ "$POSTGRES_STATUS" == "FAILED" ]; then
        print_success "✅ Validation: At least one resource is in DEGRADED/FAILED status"
        echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
for r in resources:
    if r.get('status') in ['DEGRADED', 'FAILED']:
        metrics = r.get('metrics', {})
        if r.get('name') == 'redis':
            mem_pct = metrics.get('redis_memory_usage_percent', 0)
            print(f\"  - {r.get('name')}: {r.get('status')} (Memory: {mem_pct:.1f}%)\")
        elif r.get('name') == 'postgres':
            conn_pct = metrics.get('connection_usage_percent', 0)
            print(f\"  - {r.get('name')}: {r.get('status')} (Connections: {conn_pct:.1f}%)\")
        else:
            print(f\"  - {r.get('name')}: {r.get('status')}\")
" 2>/dev/null
    else
        print_error "❌ Validation FAILED: No resources are DEGRADED. Redis: $REDIS_STATUS, PostgreSQL: $POSTGRES_STATUS"
        exit 1
    fi
fi

echo ""
sleep 2

# Step 3: Call LLM to fix
print_status "Step 3: Triggering LLM fix..."
echo ""

FIX_RESPONSE=$(curl -s -X POST "${API_URL}/api/fixes/trigger" \
    -H "Content-Type: application/json" \
    -d '{}')

FIX_ID=$(echo "$FIX_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('id', 'unknown'))
except:
    print('unknown')
" 2>/dev/null || echo "unknown")

if [ "$FIX_ID" != "unknown" ]; then
    print_success "Fix triggered successfully: $FIX_ID"
else
    print_error "Failed to trigger fix"
    echo "$FIX_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$FIX_RESPONSE"
    exit 1
fi

# Validate that LLM has given a fix (check for tool_results)
print_status "Validating LLM provided a fix..."
sleep 3  # Wait a bit for fix to be processed

FIX_DETAILS=$(curl -s "${API_URL}/api/fixes/${FIX_ID}" 2>/dev/null || echo "{}")
HAS_TOOLS=$(echo "$FIX_DETAILS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tool_results = data.get('tool_results', [])
    if tool_results and len(tool_results) > 0:
        print('1')
    else:
        print('0')
except:
    print('0')
" 2>/dev/null || echo "0")

if [ "$HAS_TOOLS" == "1" ]; then
    TOOL_COUNT=$(echo "$FIX_DETAILS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tool_results = data.get('tool_results', [])
    print(len(tool_results))
except:
    print('0')
" 2>/dev/null || echo "0")
    print_success "✅ Validation: LLM provided a fix with $TOOL_COUNT tool(s)"
    
    # Show which tools were used
    echo "$FIX_DETAILS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tool_results = data.get('tool_results', [])
    print('  Tools used:')
    for tr in tool_results:
        # tool_results structure: {step: {tool_name, ...}, result: {...}}
        step = tr.get('step', {})
        tool_name = step.get('tool_name', 'unknown')
        success = tr.get('result', {}).get('success', False)
        status = '✅' if success else '❌'
        print(f\"    $status {tool_name}\")
except Exception as e:
    print(f\"    Error parsing tools: {e}\")
" 2>/dev/null
else
    print_warning "⚠️  LLM fix may still be processing (no tools executed yet)"
fi

# Wait for fix to complete (with retries, may take longer)
print_status "Waiting for fix to complete (with retries, this may take 60-120 seconds)..."
echo ""

MAX_WAIT=120  # Increased for retries
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    sleep 5
    WAITED=$((WAITED + 5))
    
    # Check if fix is complete by looking at the latest fix
    LATEST_FIX=$(curl -s "${API_URL}/api/fixes?limit=1" | python3 -c "
import sys, json
fixes = json.load(sys.stdin)
if fixes:
    print(json.dumps(fixes[0]))
" 2>/dev/null || echo "{}")
    
    STATUS=$(echo "$LATEST_FIX" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('execution_status', 'PENDING'))
except:
    print('PENDING')
" 2>/dev/null || echo "PENDING")
    
    TOTAL_ATTEMPTS=$(echo "$LATEST_FIX" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('total_attempts', 1))
except:
    print('1')
" 2>/dev/null || echo "1")
    
    if [ "$STATUS" != "PENDING" ] && [ "$STATUS" != "" ]; then
        if [ "$TOTAL_ATTEMPTS" -gt 1 ]; then
            print_success "Fix completed with status: $STATUS (after $TOTAL_ATTEMPTS attempts)"
        else
            print_success "Fix completed with status: $STATUS"
        fi
        break
    fi
    
    echo -n "."
done

if [ $WAITED -ge $MAX_WAIT ]; then
    print_warning "Fix may still be in progress (waited ${MAX_WAIT}s)"
fi

echo ""
echo ""

# Step 4: Validate results
print_status "Step 4: Validating fix results..."
echo ""

# Run the check script
if [ -f "./check_llm_fixes.sh" ]; then
    ./check_llm_fixes.sh
else
    print_error "check_llm_fixes.sh not found"
    exit 1
fi

echo ""

# Additional validation
print_status "Additional validation:"
echo ""

# Validate that fix is applied and resource is now HEALTHY
print_status "Validating fix is applied and resource is HEALTHY..."
echo ""

FINAL_RESOURCES=$(curl -s "${API_URL}/api/resources")

# Check specific resource based on failure type
if [ "$FAILURE_TYPE" == "redis" ]; then
    FINAL_REDIS_STATUS=$(echo "$FINAL_RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
redis = [r for r in resources if r.get('name') == 'redis']
print(redis[0].get('status') if redis else 'UNKNOWN')
" 2>/dev/null || echo "UNKNOWN")
    
    if [ "$FINAL_REDIS_STATUS" == "HEALTHY" ]; then
        print_success "✅ Validation: Redis is now HEALTHY (fix applied successfully)"
        echo "$FINAL_RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
redis = [r for r in resources if r.get('name') == 'redis']
if redis:
    r = redis[0]
    metrics = r.get('metrics', {})
    mem_pct = metrics.get('redis_memory_usage_percent', 0)
    print(f\"  - Redis: {r.get('status')} (Memory: {mem_pct:.1f}%)\")
" 2>/dev/null
    else
        print_error "❌ Validation FAILED: Redis is not HEALTHY. Current status: $FINAL_REDIS_STATUS"
        print_error "Fix may not have been successful"
    fi
elif [ "$FAILURE_TYPE" == "database" ]; then
    FINAL_POSTGRES_STATUS=$(echo "$FINAL_RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
pg = [r for r in resources if r.get('name') == 'postgres']
print(pg[0].get('status') if pg else 'UNKNOWN')
" 2>/dev/null || echo "UNKNOWN")
    
    if [ "$FINAL_POSTGRES_STATUS" == "HEALTHY" ]; then
        print_success "✅ Validation: PostgreSQL is now HEALTHY (fix applied successfully)"
        echo "$FINAL_RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
pg = [r for r in resources if r.get('name') == 'postgres']
if pg:
    p = pg[0]
    metrics = p.get('metrics', {})
    conn_pct = metrics.get('connection_usage_percent', 0)
    total = metrics.get('total_connections', 0)
    max_conn = metrics.get('max_connections', 0)
    print(f\"  - PostgreSQL: {p.get('status')} (Connections: {total}/{max_conn} = {conn_pct:.1f}%)\")
" 2>/dev/null
    else
        print_error "❌ Validation FAILED: PostgreSQL is not HEALTHY. Current status: $FINAL_POSTGRES_STATUS"
        print_error "Fix may not have been successful"
    fi
else
    # For "both", check both resources
    FINAL_REDIS_STATUS=$(echo "$FINAL_RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
redis = [r for r in resources if r.get('name') == 'redis']
print(redis[0].get('status') if redis else 'UNKNOWN')
" 2>/dev/null || echo "UNKNOWN")
    
    FINAL_POSTGRES_STATUS=$(echo "$FINAL_RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
pg = [r for r in resources if r.get('name') == 'postgres']
print(pg[0].get('status') if pg else 'UNKNOWN')
" 2>/dev/null || echo "UNKNOWN")
    
    REDIS_HEALTHY=$([ "$FINAL_REDIS_STATUS" == "HEALTHY" ] && echo "1" || echo "0")
    POSTGRES_HEALTHY=$([ "$FINAL_POSTGRES_STATUS" == "HEALTHY" ] && echo "1" || echo "0")
    
    if [ "$REDIS_HEALTHY" == "1" ] && [ "$POSTGRES_HEALTHY" == "1" ]; then
        print_success "✅ Validation: Both Redis and PostgreSQL are now HEALTHY (fix applied successfully)"
        echo "$FINAL_RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
for r in resources:
    if r.get('name') in ['redis', 'postgres']:
        metrics = r.get('metrics', {})
        if r.get('name') == 'redis':
            mem_pct = metrics.get('redis_memory_usage_percent', 0)
            print(f\"  - Redis: {r.get('status')} (Memory: {mem_pct:.1f}%)\")
        elif r.get('name') == 'postgres':
            conn_pct = metrics.get('connection_usage_percent', 0)
            print(f\"  - PostgreSQL: {r.get('status')} (Connections: {conn_pct:.1f}%)\")
" 2>/dev/null
    else
        print_warning "⚠️  Some resources may still be unhealthy:"
        echo "$FINAL_RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
for r in resources:
    if r.get('name') in ['redis', 'postgres']:
        metrics = r.get('metrics', {})
        status_icon = '✅' if r.get('status') == 'HEALTHY' else '❌'
        if r.get('name') == 'redis':
            mem_pct = metrics.get('redis_memory_usage_percent', 0)
            print(f\"  $status_icon Redis: {r.get('status')} (Memory: {mem_pct:.1f}%)\")
        elif r.get('name') == 'postgres':
            conn_pct = metrics.get('connection_usage_percent', 0)
            print(f\"  $status_icon PostgreSQL: {r.get('status')} (Connections: {conn_pct:.1f}%)\")
" 2>/dev/null
        if [ "$REDIS_HEALTHY" == "0" ]; then
            print_warning "  Note: Redis may have become DEGRADED due to restart resetting maxmemory to 256MB while data persisted. This is a known issue - see REDIS_RESTART_ISSUE.md"
        fi
    fi
fi

echo ""

# Overall resource health check
FINAL_HEALTHY=$(echo "$FINAL_RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
healthy = [r for r in resources if r.get('status') == 'HEALTHY']
print(len(healthy))
" 2>/dev/null || echo "0")

TOTAL_RESOURCES=$(echo "$FINAL_RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
print(len(resources))
" 2>/dev/null || echo "0")

print_status "Overall resource health: $FINAL_HEALTHY/$TOTAL_RESOURCES healthy"

# Check fix evaluation
LATEST_FIX=$(curl -s "${API_URL}/api/fixes?limit=1" | python3 -c "
import sys, json
fixes = json.load(sys.stdin)
if fixes:
    print(json.dumps(fixes[0]))
" 2>/dev/null || echo "{}")

SUCCESSFUL_TOOLS=$(echo "$LATEST_FIX" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    results = data.get('tool_results', [])
    successful = sum(1 for r in results if r.get('result', {}).get('success'))
    total = len(results)
    print(f\"{successful}/{total}\")
except:
    print('0/0')
" 2>/dev/null || echo "0/0")

print_status "Tool execution: $SUCCESSFUL_TOOLS tools succeeded"

echo ""
print_success "Test complete!"
echo ""
print_status "To view detailed fix information:"
echo "  curl ${API_URL}/api/fixes/${FIX_ID} | python3 -m json.tool"
echo ""

