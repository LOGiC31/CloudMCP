#!/bin/bash
# Script to restart backend server to enable Docker detection

echo "Stopping backend server on port 8000..."

# Kill any process on port 8000
PID=$(lsof -ti:8000 2>/dev/null)
if [ ! -z "$PID" ]; then
    echo "Found process $PID on port 8000, killing it..."
    kill -9 $PID 2>/dev/null
    sleep 2
    echo "Server stopped."
else
    echo "No server found on port 8000."
fi

# Verify Docker is running
if ! docker ps &> /dev/null; then
    echo "⚠️  Warning: Docker is not accessible. Make sure Docker/Colima is running."
    echo "   Run: ./start_docker.sh"
    exit 1
fi

echo "✅ Docker is accessible"
echo "Containers running:"
docker ps --format "  - {{.Names}} ({{.Status}})"

echo ""
echo "Starting backend server..."
source venv/bin/activate
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

