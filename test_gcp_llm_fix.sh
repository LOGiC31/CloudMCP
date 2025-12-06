#!/bin/bash

# Test script for GCP LLM auto-fix workflow
# Usage: ./test_gcp_llm_fix.sh [redis|compute|sql] [instance_name]

set -e

API_URL="http://localhost:8000"
FAILURE_TYPE=${1:-redis}
INSTANCE_NAME=${2:-test-redis}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

echo "=========================================="
echo "GCP LLM Auto-Fix Test Script"
echo "=========================================="
echo "Failure Type: $FAILURE_TYPE"
echo "Instance Name: $INSTANCE_NAME"
echo ""

# Check if API is running
if ! curl -s "${API_URL}/api/resources" > /dev/null; then
    print_error "Backend API is not running at ${API_URL}"
    print_status "Please start the backend server: ./start_server.sh"
    exit 1
fi

print_success "Backend API is running"

# Step 0: Check initial resource status
print_status "Step 0: Checking initial resource status..."
RESOURCES=$(curl -s "${API_URL}/api/resources?include_gcp=true")
RESOURCE_STATUS=$(echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
gcp_resource = [r for r in resources if r.get('name') == '$INSTANCE_NAME' and r.get('type', '').startswith('gcp-')]
if gcp_resource:
    print(gcp_resource[0].get('status', 'UNKNOWN'))
else:
    print('NOT_FOUND')
" 2>/dev/null)

if [ "$RESOURCE_STATUS" == "NOT_FOUND" ]; then
    print_error "GCP resource '$INSTANCE_NAME' not found"
    print_status "Available GCP resources:"
    echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
gcp_resources = [r for r in resources if r.get('type', '').startswith('gcp-')]
for r in gcp_resources:
    print(f\"  - {r.get('name')} ({r.get('type')}): {r.get('status')}\")
" 2>/dev/null
    exit 1
fi

print_status "Resource '$INSTANCE_NAME' found with status: $RESOURCE_STATUS"

# Ensure resource is healthy before starting
if [ "$RESOURCE_STATUS" != "READY" ] && [ "$RESOURCE_STATUS" != "HEALTHY" ] && [ "$RESOURCE_STATUS" != "RUNNING" ] && [ "$RESOURCE_STATUS" != "RUNNABLE" ]; then
    print_warning "Resource is not in a healthy state: $RESOURCE_STATUS"
    print_status "Attempting to reset resource first..."
    
    case "$FAILURE_TYPE" in
        redis)
            curl -s -X POST "${API_URL}/api/gcp/failures/redis/${INSTANCE_NAME}/reset?memory_gb=1.0" > /dev/null
            print_status "Waiting for Redis to reset..."
            sleep 30
            ;;
        compute)
            ZONE=$(echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
r = [r for r in resources if r.get('name') == '$INSTANCE_NAME'][0]
print(r.get('gcp_zone', 'us-central1-a'))
" 2>/dev/null)
            curl -s -X POST "${API_URL}/api/gcp/failures/compute/${INSTANCE_NAME}/start?zone=${ZONE}" > /dev/null
            print_status "Waiting for Compute instance to start..."
            sleep 30
            ;;
        sql)
            curl -s -X POST "${API_URL}/api/gcp/failures/sql/${INSTANCE_NAME}/start" > /dev/null
            print_status "Waiting for SQL instance to start..."
            sleep 60
            ;;
    esac
fi

# Step 1: Introduce failure
print_status ""
print_status "Step 1: Introducing failure..."
echo ""

case "$FAILURE_TYPE" in
    redis)
        print_status "Scaling down Redis memory to cause degradation..."
        RESPONSE=$(curl -s -X POST "${API_URL}/api/gcp/failures/redis/${INSTANCE_NAME}/degrade?memory_gb=0.5")
        if echo "$RESPONSE" | grep -q "success"; then
            print_success "Redis failure introduced: $(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('message', ''))" 2>/dev/null)"
        else
            print_error "Failed to introduce Redis failure: $RESPONSE"
            exit 1
        fi
        WAIT_TIME=30  # Wait for scaling to start
        ;;
    compute)
        print_status "Stopping Compute Engine instance..."
        RESPONSE=$(curl -s -X POST "${API_URL}/api/gcp/failures/compute/${INSTANCE_NAME}/stop")
        if echo "$RESPONSE" | grep -q "success"; then
            print_success "Compute failure introduced: $(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('message', ''))" 2>/dev/null)"
        else
            print_error "Failed to introduce Compute failure: $RESPONSE"
            exit 1
        fi
        WAIT_TIME=20  # Wait for instance to stop
        ;;
    sql)
        print_status "Stopping Cloud SQL instance..."
        RESPONSE=$(curl -s -X POST "${API_URL}/api/gcp/failures/sql/${INSTANCE_NAME}/stop")
        if echo "$RESPONSE" | grep -q "success"; then
            print_success "SQL failure introduced: $(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('message', ''))" 2>/dev/null)"
        else
            print_error "Failed to introduce SQL failure: $RESPONSE"
            exit 1
        fi
        WAIT_TIME=30  # Wait for instance to stop
        ;;
    *)
        print_error "Unknown failure type: $FAILURE_TYPE"
        print_status "Usage: $0 [redis|compute|sql] [instance_name]"
        exit 1
        ;;
esac

echo ""
sleep 2

# Step 2: Validate failure
print_status "Step 2: Validating failure..."
print_status "Waiting ${WAIT_TIME} seconds for failure to be detected..."
sleep $WAIT_TIME

# Check resource status
RESOURCES=$(curl -s "${API_URL}/api/resources?include_gcp=true")
AFTER_STATUS=$(echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
gcp_resource = [r for r in resources if r.get('name') == '$INSTANCE_NAME' and r.get('type', '').startswith('gcp-')]
if gcp_resource:
    print(gcp_resource[0].get('status', 'UNKNOWN'))
else:
    print('NOT_FOUND')
" 2>/dev/null)

print_status "Resource status after failure: $AFTER_STATUS"

# Check if degraded
if [ "$AFTER_STATUS" == "UPDATING" ] || [ "$AFTER_STATUS" == "DEGRADED" ] || [ "$AFTER_STATUS" == "STOPPING" ] || [ "$AFTER_STATUS" == "TERMINATED" ] || [ "$AFTER_STATUS" == "FAILED" ]; then
    print_success "✅ Failure validated: Resource is now $AFTER_STATUS"
else
    print_warning "⚠️  Resource status is $AFTER_STATUS (expected DEGRADED/FAILED/UPDATING)"
    print_status "Continuing anyway..."
fi

echo ""
sleep 2

# Step 3: Trigger LLM fix
print_status "Step 3: Triggering LLM auto-fix..."
echo ""

FIX_RESPONSE=$(curl -s -X POST "${API_URL}/api/fixes/trigger")
FIX_ID=$(echo "$FIX_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('fix_id', 'unknown'))
except:
    print('unknown')
" 2>/dev/null)

if [ "$FIX_ID" != "unknown" ]; then
    print_success "LLM fix triggered: $FIX_ID"
else
    print_error "Failed to trigger LLM fix: $FIX_RESPONSE"
    exit 1
fi

echo ""
print_status "Waiting for LLM fix to complete (this may take 2-5 minutes)..."
echo ""

# Step 4: Monitor fix progress
MAX_WAIT=300  # 5 minutes
ELAPSED=0
POLL_INTERVAL=10

while [ $ELAPSED -lt $MAX_WAIT ]; do
    FIX_STATUS=$(curl -s "${API_URL}/api/fixes/${FIX_ID}" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('status', 'UNKNOWN'))
except:
    print('UNKNOWN')
" 2>/dev/null)
    
    if [ "$FIX_STATUS" == "SUCCESS" ]; then
        print_success "✅ LLM fix completed successfully!"
        break
    elif [ "$FIX_STATUS" == "FAILED" ]; then
        print_error "❌ LLM fix failed"
        break
    else
        print_status "Fix status: $FIX_STATUS (waiting... ${ELAPSED}s/${MAX_WAIT}s)"
    fi
    
    sleep $POLL_INTERVAL
    ELAPSED=$((ELAPSED + POLL_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    print_warning "⚠️  Timeout waiting for fix to complete"
fi

echo ""
sleep 10

# Step 5: Validate fix
print_status "Step 5: Validating fix..."
echo ""

RESOURCES=$(curl -s "${API_URL}/api/resources?include_gcp=true")
FINAL_STATUS=$(echo "$RESOURCES" | python3 -c "
import sys, json
resources = json.load(sys.stdin)
gcp_resource = [r for r in resources if r.get('name') == '$INSTANCE_NAME' and r.get('type', '').startswith('gcp-')]
if gcp_resource:
    print(gcp_resource[0].get('status', 'UNKNOWN'))
else:
    print('NOT_FOUND')
" 2>/dev/null)

print_status "Final resource status: $FINAL_STATUS"

if [ "$FINAL_STATUS" == "READY" ] || [ "$FINAL_STATUS" == "HEALTHY" ] || [ "$FINAL_STATUS" == "RUNNING" ] || [ "$FINAL_STATUS" == "RUNNABLE" ]; then
    print_success "✅ Fix validated: Resource is now $FINAL_STATUS"
    echo ""
    print_success "🎉 Test completed successfully!"
elif [ "$FINAL_STATUS" == "UPDATING" ] || [ "$FINAL_STATUS" == "CREATING" ]; then
    print_warning "⚠️  Resource is $FINAL_STATUS (fix in progress, may take a few more minutes)"
    print_status "Check status again in a few minutes"
else
    print_error "❌ Fix validation failed: Resource is still $FINAL_STATUS"
    echo ""
    print_status "Fix details:"
    curl -s "${API_URL}/api/fixes/${FIX_ID}" | python3 -m json.tool 2>/dev/null | head -50
fi

echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Failure Type: $FAILURE_TYPE"
echo "Instance: $INSTANCE_NAME"
echo "Initial Status: $RESOURCE_STATUS"
echo "After Failure: $AFTER_STATUS"
echo "Final Status: $FINAL_STATUS"
echo "Fix ID: $FIX_ID"
echo "Fix Status: $FIX_STATUS"
echo ""

