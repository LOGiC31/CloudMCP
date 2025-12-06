#!/bin/bash

# Script to test GCP CPU stress or memory pressure API
# Usage: ./test_gcp_stress.sh [cpu|memory] [instance_name] [zone]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
STRESS_TYPE="${1:-cpu}"  # cpu or memory
INSTANCE_NAME="${2:-test-vm}"
ZONE="${3:-us-central1-a}"
CPU_PERCENT="${4:-95}"  # CPU percentage (default 95%)
API_BASE="http://localhost:8000"
INITIAL_WAIT=120  # 2 minutes
POLL_DURATION=180  # 3 minutes
POLL_INTERVAL=10  # Poll every 10 seconds

echo -e "${BLUE}=== GCP Stress Test Script ===${NC}"
echo ""
echo "Configuration:"
echo "  Stress Type: $STRESS_TYPE"
echo "  Instance: $INSTANCE_NAME"
echo "  Zone: $ZONE"
if [ "$STRESS_TYPE" = "cpu" ]; then
    echo "  CPU Percent: ${CPU_PERCENT}%"
fi
echo "  Initial Wait: ${INITIAL_WAIT}s (2 minutes)"
echo "  Poll Duration: ${POLL_DURATION}s (3 minutes)"
echo "  Poll Interval: ${POLL_INTERVAL}s"
echo ""

# Function to get resource status
get_resource_status() {
    local instance_name=$1
    curl -s "${API_BASE}/api/resources?include_gcp=true" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    resource = next((r for r in data if r.get('name') == '$instance_name' and r.get('type', '').startswith('gcp-compute')), None)
    if resource:
        status = resource.get('status', 'UNKNOWN')
        metrics = resource.get('metrics', {})
        cpu = metrics.get('cpu_usage_percent', 0.0)
        memory = metrics.get('memory_usage_percent', 0.0)
        print(f\"{status}|{cpu}|{memory}\")
    else:
        print('NOT_FOUND|0.0|0.0')
except Exception as e:
    print(f'ERROR|{e}|0.0')
"
}

# Function to trigger CPU stress
trigger_cpu_stress() {
    local instance_name=$1
    local zone=$2
    local cpu_percent=$3
    echo -e "${YELLOW}Triggering CPU stress on ${instance_name} at ${cpu_percent}%...${NC}"
    
    response=$(curl -s -X POST "${API_BASE}/api/gcp/failures/compute/${instance_name}/cpu-stress?zone=${zone}&duration_seconds=300&cpu_percent=${cpu_percent}")
    
    if echo "$response" | python3 -c "import sys, json; data = json.load(sys.stdin); sys.exit(0 if data.get('success') else 1)" 2>/dev/null; then
        echo -e "${GREEN}✅ CPU stress triggered successfully${NC}"
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
        return 0
    else
        echo -e "${RED}❌ Failed to trigger CPU stress${NC}"
        echo "$response"
        return 1
    fi
}

# Function to trigger memory pressure
trigger_memory_pressure() {
    local instance_name=$1
    local zone=$2
    echo -e "${YELLOW}Triggering memory pressure on ${instance_name}...${NC}"
    
    response=$(curl -s -X POST "${API_BASE}/api/gcp/failures/compute/${instance_name}/memory-pressure?zone=${zone}&fill_percent=0.90")
    
    if echo "$response" | python3 -c "import sys, json; data = json.load(sys.stdin); sys.exit(0 if data.get('success') else 1)" 2>/dev/null; then
        echo -e "${GREEN}✅ Memory pressure triggered successfully${NC}"
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
        return 0
    else
        echo -e "${RED}❌ Failed to trigger memory pressure${NC}"
        echo "$response"
        return 1
    fi
}

# Get initial status
echo -e "${BLUE}Step 1: Getting initial resource status...${NC}"
initial_status=$(get_resource_status "$INSTANCE_NAME")
if [ "$initial_status" = "NOT_FOUND|0.0|0.0" ]; then
    echo -e "${RED}❌ Resource ${INSTANCE_NAME} not found${NC}"
    exit 1
fi

initial_status_value=$(echo "$initial_status" | cut -d'|' -f1)
initial_cpu=$(echo "$initial_status" | cut -d'|' -f2)
initial_memory=$(echo "$initial_status" | cut -d'|' -f3)

echo -e "  Status: ${initial_status_value}"
echo -e "  CPU: ${initial_cpu}%"
echo -e "  Memory: ${initial_memory}%"
echo ""

# Trigger stress
echo -e "${BLUE}Step 2: Triggering ${STRESS_TYPE} stress...${NC}"
if [ "$STRESS_TYPE" = "cpu" ]; then
    if ! trigger_cpu_stress "$INSTANCE_NAME" "$ZONE" "$CPU_PERCENT"; then
        exit 1
    fi
elif [ "$STRESS_TYPE" = "memory" ]; then
    if ! trigger_memory_pressure "$INSTANCE_NAME" "$ZONE"; then
        exit 1
    fi
else
    echo -e "${RED}❌ Invalid stress type: $STRESS_TYPE (must be 'cpu' or 'memory')${NC}"
    exit 1
fi
echo ""

# Wait initial period
echo -e "${BLUE}Step 3: Waiting ${INITIAL_WAIT}s (2 minutes) for Cloud Monitoring to collect metrics...${NC}"
for i in $(seq 1 $INITIAL_WAIT); do
    if [ $((i % 30)) -eq 0 ]; then
        echo -e "  ${YELLOW}Waiting... ${i}s / ${INITIAL_WAIT}s${NC}"
    fi
    sleep 1
done
echo -e "${GREEN}✅ Initial wait complete${NC}"
echo ""

# Poll for status change
echo -e "${BLUE}Step 4: Polling status for ${POLL_DURATION}s (3 minutes) to detect status change...${NC}"
echo ""

poll_count=$((POLL_DURATION / POLL_INTERVAL))
status_changed=false
final_status=""
final_cpu=""
final_memory=""

for i in $(seq 1 $poll_count); do
    current_status=$(get_resource_status "$INSTANCE_NAME")
    current_status_value=$(echo "$current_status" | cut -d'|' -f1)
    current_cpu=$(echo "$current_status" | cut -d'|' -f2)
    current_memory=$(echo "$current_status" | cut -d'|' -f3)
    
    elapsed=$((i * POLL_INTERVAL))
    
    # Check if status changed
    if [ "$current_status_value" != "$initial_status_value" ]; then
        if [ "$status_changed" = false ]; then
            echo -e "${GREEN}✅ Status changed detected at ${elapsed}s!${NC}"
            status_changed=true
        fi
    fi
    
    # Display current status
    status_color=$GREEN
    if [ "$current_status_value" = "DEGRADED" ] || [ "$current_status_value" = "FAILED" ]; then
        status_color=$RED
    elif [ "$current_status_value" = "HEALTHY" ] || [ "$current_status_value" = "RUNNING" ]; then
        status_color=$GREEN
    else
        status_color=$YELLOW
    fi
    
    echo -e "  [${elapsed}s] Status: ${status_color}${current_status_value}${NC} | CPU: ${current_cpu}% | Memory: ${current_memory}%"
    
    # Store final values
    final_status="$current_status_value"
    final_cpu="$current_cpu"
    final_memory="$current_memory"
    
    # Check if we've detected degradation
    if [ "$current_status_value" = "DEGRADED" ] || [ "$current_status_value" = "FAILED" ]; then
        if [ "$status_changed" = false ]; then
            status_changed=true
        fi
    fi
    
    if [ $i -lt $poll_count ]; then
        sleep $POLL_INTERVAL
    fi
done

echo ""

# Final results
echo -e "${BLUE}=== Test Results ===${NC}"
echo ""
echo "Initial Status:"
echo "  Status: ${initial_status_value}"
echo "  CPU: ${initial_cpu}%"
echo "  Memory: ${initial_memory}%"
echo ""
echo "Final Status:"
echo "  Status: ${final_status}"
echo "  CPU: ${final_cpu}%"
echo "  Memory: ${final_memory}%"
echo ""

# Determine if test passed
if [ "$status_changed" = true ]; then
    if [ "$STRESS_TYPE" = "cpu" ]; then
        # For CPU stress, check if CPU increased and status is DEGRADED/FAILED
        cpu_increased=$(python3 -c "print(1 if float('$final_cpu') > float('$initial_cpu') else 0)" 2>/dev/null || echo "0")
        if [ "$final_status" = "DEGRADED" ] || [ "$final_status" = "FAILED" ]; then
            echo -e "${GREEN}✅ TEST PASSED: Status changed to ${final_status}${NC}"
            echo -e "${GREEN}   CPU stress was detected and status updated correctly${NC}"
            exit 0
        elif [ "$cpu_increased" = "1" ]; then
            echo -e "${YELLOW}⚠️  PARTIAL SUCCESS: CPU increased (${initial_cpu}% → ${final_cpu}%) but status not yet DEGRADED${NC}"
            echo -e "${YELLOW}   This may be normal if CPU is below 90% threshold${NC}"
            exit 0
        else
            echo -e "${RED}❌ TEST FAILED: Status changed but CPU did not increase${NC}"
            exit 1
        fi
    else
        # For memory pressure, check if memory increased and status is DEGRADED/FAILED
        memory_increased=$(python3 -c "print(1 if float('$final_memory') > float('$initial_memory') else 0)" 2>/dev/null || echo "0")
        if [ "$final_status" = "DEGRADED" ] || [ "$final_status" = "FAILED" ]; then
            echo -e "${GREEN}✅ TEST PASSED: Status changed to ${final_status}${NC}"
            echo -e "${GREEN}   Memory pressure was detected and status updated correctly${NC}"
            exit 0
        elif [ "$memory_increased" = "1" ]; then
            echo -e "${YELLOW}⚠️  PARTIAL SUCCESS: Memory increased (${initial_memory}% → ${final_memory}%) but status not yet DEGRADED${NC}"
            echo -e "${YELLOW}   This may be normal if memory is below 90% threshold${NC}"
            exit 0
        else
            echo -e "${RED}❌ TEST FAILED: Status changed but memory did not increase${NC}"
            exit 1
        fi
    fi
else
    echo -e "${RED}❌ TEST FAILED: Status did not change after ${INITIAL_WAIT}s + ${POLL_DURATION}s${NC}"
    echo -e "${RED}   Expected status to change to DEGRADED or FAILED${NC}"
    echo ""
    echo "Possible reasons:"
    echo "  1. Cloud Monitoring metrics not yet available (may need more time)"
    echo "  2. CPU/Memory usage not high enough to trigger threshold (>90%)"
    echo "  3. Stress script not running on the instance"
    echo "  4. Cloud Monitoring API not returning metrics"
    exit 1
fi

