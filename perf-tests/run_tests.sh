#!/bin/bash
# Run Kairos performance tests
# Usage: ./run_tests.sh [kairos-url]

set -e

KAIROS_URL="${1:-http://localhost:8000}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================="
echo "Kairos Performance Tests"
echo "========================================="
echo "Target: $KAIROS_URL"
echo ""

# Check if Kairos is reachable
echo "Checking Kairos availability..."
if ! curl -s --connect-timeout 5 "$KAIROS_URL/api/health" > /dev/null 2>&1; then
    echo "ERROR: Cannot reach Kairos at $KAIROS_URL"
    echo "Make sure Kairos is running and accessible."
    exit 1
fi
echo "Kairos is reachable."
echo ""

# Check if running in Docker or locally
if command -v docker &> /dev/null && [ -f "$SCRIPT_DIR/docker-compose.yml" ]; then
    echo "Running tests via Docker..."
    cd "$SCRIPT_DIR"
    KAIROS_URL="$KAIROS_URL" docker-compose --profile testing up --build --exit-code-from perf-tests
else
    echo "Running tests locally..."

    # Check dependencies
    if ! python3 -c "import playwright" 2>/dev/null; then
        echo "Installing dependencies..."
        pip install -r "$SCRIPT_DIR/requirements.txt"
        playwright install chromium
    fi

    cd "$SCRIPT_DIR"
    KAIROS_URL="$KAIROS_URL" python3 -m pytest test_performance.py -v --tb=short
fi

echo ""
echo "========================================="
echo "Performance tests completed!"
echo "========================================="
