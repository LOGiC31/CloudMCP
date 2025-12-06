#!/bin/bash
# Script to stop the backend server

PORT=8000

echo "Checking for processes on port $PORT..."

PID=$(lsof -ti:$PORT 2>/dev/null)

if [ -z "$PID" ]; then
    echo "No process found on port $PORT"
    exit 0
fi

echo "Found process(es) on port $PORT: $PID"
echo "Killing process(es)..."

for pid in $PID; do
    kill -9 $pid 2>/dev/null
    echo "Killed process $pid"
done

sleep 1

# Verify port is free
if lsof -ti:$PORT > /dev/null 2>&1; then
    echo "Warning: Port $PORT may still be in use"
else
    echo "Port $PORT is now free"
fi

