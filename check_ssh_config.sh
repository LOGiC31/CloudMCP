#!/bin/bash

# Script to check SSH configuration for GCP Compute Engine instances
# Works with virtual environments

echo "=== GCP SSH Configuration Check ==="
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
    echo "✅ Virtual environment activated"
    echo ""
fi

# Find gcloud in common locations
GCLOUD_PATH=""
if command -v gcloud &> /dev/null; then
    GCLOUD_PATH=$(which gcloud)
elif [ -f "$HOME/google-cloud-sdk/bin/gcloud" ]; then
    GCLOUD_PATH="$HOME/google-cloud-sdk/bin/gcloud"
elif [ -f "/usr/local/bin/gcloud" ]; then
    GCLOUD_PATH="/usr/local/bin/gcloud"
elif [ -f "/opt/homebrew/bin/gcloud" ]; then
    GCLOUD_PATH="/opt/homebrew/bin/gcloud"
fi

if [ -z "$GCLOUD_PATH" ]; then
    echo "❌ gcloud CLI is not installed or not found"
    echo "   Install from: https://cloud.google.com/sdk/docs/install"
    echo ""
    echo "   After installation, add to PATH:"
    echo "   export PATH=\$HOME/google-cloud-sdk/bin:\$PATH"
    exit 1
fi

echo "✅ gcloud CLI found at: $GCLOUD_PATH"
echo ""

# Check if SSH keys are configured
echo "Checking SSH key configuration..."
if $GCLOUD_PATH compute config-ssh --dry-run &> /dev/null; then
    echo "✅ SSH keys are configured"
else
    echo "⚠️  SSH keys may need configuration"
    echo ""
    echo "To configure SSH keys, run:"
    echo "  $GCLOUD_PATH compute config-ssh"
    echo ""
fi

# Load GCP settings from .env if available
if [ -f .env ]; then
    export $(cat .env | grep -E '^GCP_PROJECT_ID=|^GCP_ZONE=' | xargs)
fi

# Check if project and zone are set
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "⚠️  GCP_PROJECT_ID is not set in .env"
    echo "   Set it in your .env file or use: $GCLOUD_PATH config set project PROJECT_ID"
    exit 1
fi

if [ -z "$GCP_ZONE" ]; then
    echo "⚠️  GCP_ZONE is not set in .env"
    echo "   Set it in your .env file or use: $GCLOUD_PATH config set compute/zone ZONE"
    exit 1
fi

echo "Project ID: $GCP_PROJECT_ID"
echo "Zone: $GCP_ZONE"
echo ""

# List instances
echo "Available Compute Engine instances:"
$GCLOUD_PATH compute instances list --project=$GCP_PROJECT_ID --format="table(name,zone,status,EXTERNAL_IP)" 2>&1 | head -10
echo ""

# Test SSH access to test-vm if it exists
INSTANCE_NAME="test-vm"
if $GCLOUD_PATH compute instances describe $INSTANCE_NAME --zone=$GCP_ZONE --project=$GCP_PROJECT_ID &> /dev/null; then
    echo "Testing SSH access to $INSTANCE_NAME..."
    if $GCLOUD_PATH compute ssh $INSTANCE_NAME --zone=$GCP_ZONE --project=$GCP_PROJECT_ID --command="echo 'SSH connection successful'" 2>&1 | grep -q "SSH connection successful"; then
        echo "✅ SSH access to $INSTANCE_NAME is working"
    else
        echo "❌ SSH access to $INSTANCE_NAME failed"
        echo ""
        echo "Troubleshooting steps:"
        echo "1. Configure SSH keys: $GCLOUD_PATH compute config-ssh"
        echo "2. Check firewall rules allow SSH (port 22)"
        echo "3. Verify instance has external IP or IAP tunnel is configured"
        echo "4. Test manually: $GCLOUD_PATH compute ssh $INSTANCE_NAME --zone=$GCP_ZONE --project=$GCP_PROJECT_ID"
    fi
else
    echo "⚠️  Instance '$INSTANCE_NAME' not found in zone $GCP_ZONE"
    echo "   Create it or update GCP_ZONE in .env"
fi

echo ""
echo "=== Check Complete ==="
