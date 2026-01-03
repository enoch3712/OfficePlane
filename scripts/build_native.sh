#!/bin/bash
# Build the native Rust module for OfficePlane
#
# Usage:
#   ./scripts/build_native.sh          # Development build
#   ./scripts/build_native.sh release  # Production build

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
NATIVE_DIR="$PROJECT_ROOT/native/officeplane-core"

echo "==> Building OfficePlane Native Core"

# Check for Rust
if ! command -v cargo &> /dev/null; then
    echo "Error: Rust not found. Install from https://rustup.rs"
    exit 1
fi

# Check for maturin
if ! command -v maturin &> /dev/null; then
    echo "==> Installing maturin..."
    pip install maturin
fi

cd "$NATIVE_DIR"

BUILD_TYPE="${1:-develop}"

if [ "$BUILD_TYPE" = "release" ]; then
    echo "==> Building release wheel..."
    maturin build --release
    echo ""
    echo "Wheel built in: $NATIVE_DIR/target/wheels/"
    echo "Install with: pip install target/wheels/officeplane_core-*.whl"
else
    echo "==> Building development version..."
    maturin develop --release
    echo ""
    echo "Native module installed in development mode."
    echo "Use OFFICEPLANE_DRIVER=rust to enable."
fi

echo ""
echo "==> Build complete!"
