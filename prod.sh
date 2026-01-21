#!/bin/bash

# OfficePlane Production Mode
# Runs optimized production builds

set -e

echo "🚀 OfficePlane Production Mode"
echo "=============================="
echo ""

# Check if containers are already running
if docker compose ps | grep -q "Up"; then
    echo "📊 Services are already running in production mode"
    echo ""
    echo "To view logs:"
    echo "  docker compose logs -f"
    echo ""
    echo "To restart:"
    echo "  docker compose restart"
    echo ""
    exit 0
fi

# Start services in production mode
echo "🐳 Starting services in production mode..."
docker compose up -d

# Wait for services to be healthy
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Show status
echo ""
echo "✅ Services are running in production mode!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Access your services:"
echo "  📊 UI:              http://localhost:3000"
echo "  🔌 API:             http://localhost:8001"
echo "  📚 API Docs:        http://localhost:8001/docs"
echo "  🗄️  PostgreSQL:      localhost:5433"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Production features:"
echo "  ✓ Optimized builds"
echo "  ✓ Minimal Docker images"
echo "  ✓ Better performance"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f              # View logs"
echo "  docker compose logs -f ui           # View UI logs only"
echo "  docker compose logs -f api          # View API logs only"
echo "  docker compose restart              # Restart all services"
echo "  docker compose down                 # Stop services"
echo ""
