#!/bin/bash
# Quick script to fix GCP authentication RefreshError
# This script recreates the service account key using gcloud CLI

set -e

echo "🔧 GCP Authentication Fix Script"
echo "=================================="
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed."
    echo "   Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Get project ID
if [ -f .env ]; then
    PROJECT_ID=$(grep "GCP_PROJECT_ID" .env | cut -d '=' -f2 | tr -d ' ' | tr -d '"')
fi

if [ -z "$PROJECT_ID" ]; then
    echo "Enter your GCP Project ID:"
    read -r PROJECT_ID
fi

if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: Project ID is required"
    exit 1
fi

echo "📋 Project ID: $PROJECT_ID"
echo ""

# Set project
gcloud config set project "$PROJECT_ID" > /dev/null 2>&1

# Service account email
SA_EMAIL="infra-orchestrator-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Check if service account exists
if ! gcloud iam service-accounts describe "$SA_EMAIL" > /dev/null 2>&1; then
    echo "❌ Error: Service account '$SA_EMAIL' does not exist."
    echo ""
    echo "Create it first with:"
    echo "  gcloud iam service-accounts create infra-orchestrator-sa"
    exit 1
fi

echo "✅ Service account found: $SA_EMAIL"
echo ""

# Backup old key if it exists
if [ -f "gcp-service-account-key.json" ]; then
    BACKUP_FILE="gcp-service-account-key.json.backup.$(date +%Y%m%d_%H%M%S)"
    echo "📦 Backing up old key to: $BACKUP_FILE"
    cp "gcp-service-account-key.json" "$BACKUP_FILE"
    echo ""
fi

# List existing keys
echo "📋 Existing keys for this service account:"
gcloud iam service-accounts keys list --iam-account="$SA_EMAIL" --format="table(name,validAfterTime,validBeforeTime)" || true
echo ""

# Create new key
echo "🔑 Creating new service account key..."
gcloud iam service-accounts keys create gcp-service-account-key.json \
    --iam-account="$SA_EMAIL" \
    --key-file-type=json

if [ $? -eq 0 ]; then
    echo "✅ New key created successfully!"
    echo ""
    
    # Verify key file
    if python3 -m json.tool gcp-service-account-key.json > /dev/null 2>&1; then
        echo "✅ Key file is valid JSON"
    else
        echo "⚠️  Warning: Key file may not be valid JSON"
    fi
    
    # Set permissions
    chmod 600 gcp-service-account-key.json
    echo "✅ Set file permissions to 600 (read/write for owner only)"
    echo ""
    
    # Test authentication
    echo "🧪 Testing authentication..."
    if python3 test_gcp_auth.py 2>/dev/null; then
        echo "✅ Authentication test passed!"
    else
        echo "⚠️  Authentication test failed. You may need to:"
        echo "   1. Check service account permissions"
        echo "   2. Enable required APIs"
        echo "   3. See GCP_SETUP_GUIDE.md for more troubleshooting"
    fi
    
    echo ""
    echo "✅ Done! Your new key is ready to use."
    echo ""
    echo "Next steps:"
    echo "  1. Restart the server: ./stop_server.sh && ./start_server.sh"
    echo "  2. Test the API: curl 'http://localhost:8000/api/resources?include_gcp=true'"
    echo ""
    echo "⚠️  Security reminder:"
    echo "  - Keep gcp-service-account-key.json secure"
    echo "  - Never commit it to version control"
    echo "  - Consider deleting old keys from GCP Console"
    
else
    echo "❌ Failed to create new key"
    exit 1
fi

