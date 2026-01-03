#!/bin/bash
# Compare Python and Rust driver performance
#
# Usage: ./scripts/compare_drivers.sh [--build]
#
# Options:
#   --build    Rebuild Docker images before testing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Check for --build flag
BUILD_IMAGES=false
if [ "$1" = "--build" ]; then
    BUILD_IMAGES=true
fi

echo "=============================================="
echo "  OfficePlane Driver Comparison Test"
echo "=============================================="
echo ""

# Build images if requested or if they don't exist
if [ "$BUILD_IMAGES" = true ]; then
    echo "🔨 Building Docker images..."
    echo ""

    echo "Building Python driver image..."
    docker build -t officeplane:python -f docker/Dockerfile .
    echo ""

    echo "Building Rust driver image..."
    docker build -t officeplane:rust -f docker/Dockerfile.rust .
    echo ""
else
    # Check if images exist
    if ! docker images -q officeplane:python | grep -q .; then
        echo "⚠️  officeplane:python image not found"
        echo "   Run with --build flag or: docker build -t officeplane:python -f docker/Dockerfile ."
        exit 1
    fi

    if ! docker images -q officeplane:rust | grep -q .; then
        echo "⚠️  officeplane:rust image not found"
        echo "   Run with --build flag or: docker build -t officeplane:rust -f docker/Dockerfile.rust ."
        exit 1
    fi
fi

echo "🧪 Running comparison tests..."
echo ""

# Activate venv if it exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Run the comparison test
pytest tests/test_driver_comparison.py -v -s

echo ""
echo "=============================================="
echo "  Comparison complete!"
echo "=============================================="
