#!/bin/bash

# Script to delete all fix evaluations from the database

echo "🗑️  Deleting all fix evaluations..."

# Delete via API
RESPONSE=$(curl -s -X DELETE http://localhost:8000/api/fixes)

if [ $? -eq 0 ]; then
    echo "$RESPONSE" | python3 -m json.tool
    echo ""
    echo "✅ All fixes deleted successfully!"
else
    echo "❌ Failed to delete fixes. Is the server running?"
    exit 1
fi

