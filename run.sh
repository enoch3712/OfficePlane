#!/bin/bash

# Simple OfficePlane Runner
# Runs DB + API in Docker, UI locally

set -e

echo "🚀 OfficePlane Simple Start"
echo "==========================="
echo ""

# Start database and API in Docker
echo "🐳 Starting PostgreSQL + FastAPI in Docker..."
docker compose up -d
echo ""

# Wait for API to be ready
echo "⏳ Waiting for API to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
        echo "✅ API is ready!"
        break
    fi
    attempt=$((attempt + 1))
    printf "."
    sleep 1
done
echo ""

if [ $attempt -eq $max_attempts ]; then
    echo "⚠️  API not responding. Check logs: docker compose logs"
    exit 1
fi

# Run database migrations
echo "🗃️  Running database migrations..."
sleep 2
npx prisma db push --accept-data-loss || echo "⚠️  Database might already be initialized"
echo ""

echo "✅ Backend is running!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Backend Services:"
echo "  🔌 API: http://localhost:8001"
echo "  📚 API Docs: http://localhost:8001/docs"
echo "  🗄️  PostgreSQL: localhost:5433"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "To start the UI (in a new terminal):"
echo "  cd ui && npm run dev"
echo ""
echo "Then open: http://localhost:3000"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f   # View logs"
echo "  docker compose down      # Stop services"
echo "  npx prisma studio        # Database GUI"
echo ""
