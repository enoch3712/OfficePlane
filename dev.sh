#!/bin/bash

# OfficePlane Development Mode
# Runs with hot-reload for both API and UI

set -e

echo "🔥 OfficePlane Development Mode (Hot-Reload)"
echo "============================================"
echo ""

# Check if containers are already running
if docker compose -f docker-compose.dev.yml ps | grep -q "Up"; then
    echo "📊 Services are already running"
    echo ""
    echo "To view logs:"
    echo "  docker compose -f docker-compose.dev.yml logs -f"
    echo ""
    echo "To restart:"
    echo "  docker compose -f docker-compose.dev.yml restart"
    echo ""
    exit 0
fi

# Start services in development mode
echo "🐳 Starting services in development mode..."
docker compose -f docker-compose.dev.yml up -d

# Wait for services to be healthy
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Show status
echo ""
echo "✅ Services are running in development mode!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Access your services:"
echo "  📊 UI (Hot-Reload):     http://localhost:3000"
echo "  🔌 API (Hot-Reload):    http://localhost:8001"
echo "  📚 API Docs:            http://localhost:8001/docs"
echo "  🗄️  PostgreSQL:          localhost:5433"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Development features:"
echo "  ✓ UI changes reload automatically"
echo "  ✓ API changes reload automatically"
echo "  ✓ TypeScript compilation on save"
echo ""
echo "Useful commands:"
echo "  docker compose -f docker-compose.dev.yml logs -f      # View logs"
echo "  docker compose -f docker-compose.dev.yml logs -f ui   # View UI logs only"
echo "  docker compose -f docker-compose.dev.yml logs -f api  # View API logs only"
echo "  docker compose -f docker-compose.dev.yml restart      # Restart all services"
echo "  docker compose -f docker-compose.dev.yml down         # Stop services"
echo ""
