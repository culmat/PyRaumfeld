#!/bin/bash
# Start the Raumfeld Control Web API

cd "$(dirname "$0")"

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo "Installing dependencies..."
    .venv/bin/pip install -r requirements.txt
fi

# Set environment variables (optional)
export PORT="${PORT:-8080}"
export DEBUG="${DEBUG:-False}"

echo "Starting Raumfeld Control API on port $PORT..."
echo "Access it at: http://localhost:$PORT"
echo "Zones endpoint: http://localhost:$PORT/zones"
echo ""

.venv/bin/python RaumfeldControl.py
