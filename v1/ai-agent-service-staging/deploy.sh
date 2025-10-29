#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Define paths
VENV_PATH="/home/digbiweb/digbi_be/venv_food-rating-service/bin"
PROJECT_PATH="/home/digbiweb/digbi_be/food-rating-service"
ALLOY_BIN="/usr/local/bin/alloy"
ALLOY_CONFIG="alloy-config.alloy"
ALLOY_LOG="/var/log/alloy.log"

echo "🚀 Starting Deployment Script..."

# Step 0: Install Alloy if not present
echo "🧩 Checking for Grafana Alloy..."
if ! [ -x "$ALLOY_BIN" ]; then
    echo "📦 Grafana Alloy not found. Installing..."
    cd /tmp
    curl -O -L https://github.com/grafana/alloy/releases/latest/download/alloy-linux-amd64.zip
    unzip -o alloy-linux-amd64.zip
    chmod +x alloy-linux-amd64
    sudo mv alloy-linux-amd64 $ALLOY_BIN
    echo "✅ Alloy installed to $ALLOY_BIN"
else
    echo "✅ Alloy already installed."
fi

# Function to stop any running Alloy processes
stop_alloy() {
    echo "🛑 Stopping any running Alloy instances..."
    # Send SIGTERM first for graceful shutdown
    pkill -f "$ALLOY_BIN" >/dev/null 2>&1 || true
    
    # Wait for process to exit
    local timeout=5
    while pgrep -f "$ALLOY_BIN" >/dev/null && [ $timeout -gt 0 ]; do
        sleep 1
        ((timeout--))
    done
    
    # Force kill if still running
    if pgrep -f "$ALLOY_BIN" >/dev/null; then
        echo "⚠️  Force killing Alloy processes..."
        pkill -9 -f "$ALLOY_BIN" >/dev/null 2>&1 || true
    fi
    
    # Verify no Alloy processes are running
    if pgrep -f "$ALLOY_BIN" >/dev/null; then
        echo "❌ Failed to stop existing Alloy processes; continuing deployment"
    else
        echo "✅ All Alloy processes stopped"
    fi
}

# Step 0.1: Stop any running Alloy instances
stop_alloy

echo "🔄 Starting Alloy with config: $ALLOY_CONFIG"

# Load environment variables from .env
if [ -f "$PROJECT_PATH/.env" ]; then
    echo "🔧 Loading environment variables from .env"
    # Enable auto-export, source .env, then disable auto-export
    set -a
    source "$PROJECT_PATH/.env"
    set +a
    echo "✅ Environment variables loaded"
else
    echo "⚠️  Warning: .env file not found at $PROJECT_PATH/.env"
fi

# Create log directory if it doesn't exist
ALLOY_LOG_DIR=$(dirname "$ALLOY_LOG")
mkdir -p "$ALLOY_LOG_DIR"
touch "$ALLOY_LOG"
chmod 666 "$ALLOY_LOG" 2>/dev/null || sudo chmod 666 "$ALLOY_LOG"

# Clean up any old PID file
rm -f "$PROJECT_PATH/alloy.pid"

# Start Alloy with environment variables
echo "🚀 Starting Alloy with config: $PROJECT_PATH/$ALLOY_CONFIG"
# Use nohup and disown to properly detach the process
nohup env $(grep -v '^#' "$PROJECT_PATH/.env" | xargs) $ALLOY_BIN run "$PROJECT_PATH/$ALLOY_CONFIG" > "$ALLOY_LOG" 2>&1 &
ALLOY_PID=$!
# Store the PID for later reference
echo $ALLOY_PID > "$PROJECT_PATH/alloy.pid"
# Disown the process to prevent it from being killed when the script exits
disown $ALLOY_PID 2>/dev/null || true

# Verify Alloy started successfully
echo "🌐 Verifying Alloy process (PID: $ALLOY_PID)..."
sleep 5

# Check if process is running
if ! ps -p $ALLOY_PID > /dev/null; then
    echo "❌ Failed to start Alloy. Process not running."
    echo "📝 Last 20 lines of Alloy log ($ALLOY_LOG):"
    tail -n 20 "$ALLOY_LOG"
    echo "⚠️  Continuing deployment without Alloy"
else
    echo "✅ Alloy process is running"
fi

# Check for common errors in logs
if grep -q "error" "$ALLOY_LOG"; then
    echo "⚠️  Errors detected in Alloy log:"
    grep -i "error\\|fail" "$ALLOY_LOG" | tail -n 5
fi


# Clean up function for script exit
cleanup() {
    echo "🧹 Cleaning up..."
    rm -f "$PROJECT_PATH/alloy.pid"
}

# Set up trap to clean up on script exit
trap cleanup EXIT

echo "✅ Alloy started successfully (PID: $ALLOY_PID, Log: $ALLOY_LOG)"
echo "📋 Process information:"
ps -p $ALLOY_PID -o pid,ppid,cmd || true

# Step 1: Activate Virtual Environment & Install Dependencies
echo "📦 Installing dependencies..."
$VENV_PATH/pip install -r $PROJECT_PATH/requirements.txt

# Step 2: Run Tests
echo "🧪 Running tests..."
$VENV_PATH/pytest $PROJECT_PATH/tests/

# Step 3: Restart or Start Gunicorn
echo "✅ Tests passed! Restarting Gunicorn..."
sudo systemctl daemon-reload
if sudo systemctl is-active --quiet gunicorn.service; then
    echo "🔄 Restarting Gunicorn..."
    sudo systemctl restart gunicorn.service
else
    echo "🚀 Starting Gunicorn..."
    sudo systemctl start gunicorn.service
fi

# Step 4: Check Status
echo "📌 Checking Gunicorn status..."
sudo systemctl status gunicorn.service --no-pager

echo "🎉 Deployment completed successfully!"
