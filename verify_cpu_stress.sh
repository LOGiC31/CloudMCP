#!/bin/bash

# Script to verify CPU stress is actually running on the instance
# Usage: ./verify_cpu_stress.sh [instance_name] [zone]

INSTANCE_NAME="${1:-test-vm}"
ZONE="${2:-us-central1-a}"

echo "=== Verifying CPU Stress on ${INSTANCE_NAME} ==="
echo ""

# Find gcloud
GCLOUD_PATH=""
if command -v gcloud &> /dev/null; then
    GCLOUD_PATH=$(which gcloud)
elif [ -f "$HOME/google-cloud-sdk/bin/gcloud" ]; then
    GCLOUD_PATH="$HOME/google-cloud-sdk/bin/gcloud"
elif [ -f "$HOME/Downloads/google-cloud-sdk/bin/gcloud" ]; then
    GCLOUD_PATH="$HOME/Downloads/google-cloud-sdk/bin/gcloud"
fi

if [ -z "$GCLOUD_PATH" ]; then
    echo "❌ gcloud CLI not found"
    exit 1
fi

echo "Checking CPU stress processes..."
echo ""

# Check for Python processes consuming CPU
echo "1. Checking for Python CPU stress processes:"
$GCLOUD_PATH compute ssh $INSTANCE_NAME --zone=$ZONE --command="ps aux | grep -E 'python.*cpu|stress' | grep -v grep" 2>/dev/null || echo "  No processes found"

echo ""
echo "2. Checking CPU usage:"
$GCLOUD_PATH compute ssh $INSTANCE_NAME --zone=$ZONE --command="top -bn1 | head -20" 2>/dev/null || echo "  Could not get CPU usage"

echo ""
echo "3. Checking log file:"
$GCLOUD_PATH compute ssh $INSTANCE_NAME --zone=$ZONE --command="if [ -f /tmp/cpu_stress.log ]; then tail -20 /tmp/cpu_stress.log; else echo '  Log file not found'; fi" 2>/dev/null

echo ""
echo "4. Checking number of CPU cores:"
$GCLOUD_PATH compute ssh $INSTANCE_NAME --zone=$ZONE --command="nproc" 2>/dev/null || echo "  Could not get CPU count"

echo ""
echo "=== Verification Complete ==="

