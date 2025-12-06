#!/bin/bash
# Script to start the backend server

PORT=8000

# Function to check if port is in use
check_port() {
    lsof -ti:$PORT > /dev/null 2>&1
}

# Function to kill process on port
kill_port() {
    echo "Port $PORT is already in use. Attempting to free it..."
    PID=$(lsof -ti:$PORT)
    if [ ! -z "$PID" ]; then
        echo "Killing process $PID on port $PORT..."
        kill -9 $PID 2>/dev/null
        sleep 2
        if check_port; then
            echo "Failed to free port $PORT. Please manually kill the process."
            exit 1
        else
            echo "Port $PORT is now free."
        fi
    fi
}

# Check if port is in use and free it if needed
if check_port; then
    kill_port
fi

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found. Please run: python3 -m venv venv"
    exit 1
fi

source venv/bin/activate

# Run from project root
echo "Starting server on port $PORT..."
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port $PORT

