#!/bin/bash
# Script to start Docker (Colima) and verify connection

echo "Checking Colima status..."

if ! command -v colima &> /dev/null; then
    echo "Error: Colima is not installed."
    echo "Install it with: brew install colima docker docker-compose"
    exit 1
fi

# Check if Colima is running
if colima status &> /dev/null; then
    echo "Colima is running"
else
    echo "Starting Colima..."
    colima start
fi

# Set Docker context
echo "Setting Docker context to colima..."
docker context use colima 2>/dev/null || true

# Wait a moment for socket to be ready
sleep 2

# Test Docker connection
if docker ps &> /dev/null; then
    echo "✅ Docker is ready!"
    echo ""
    echo "You can now run:"
    echo "  docker-compose up -d"
else
    echo "❌ Docker connection failed. Try:"
    echo "  1. colima stop"
    echo "  2. colima start"
    echo "  3. docker context use colima"
    exit 1
fi

