#!/bin/bash

# OfficePlane Quick Start
# One-command setup and launch

set -e

echo "🚀 OfficePlane Quick Start"
echo "=========================="
echo ""

# Check for .env
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cat > .env <<EOF
OPENAI_API_KEY=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
OFFICEPLANE_DRIVER=libreoffice
DATABASE_URL=postgresql://officeplane:officeplane@localhost:5432/officeplane
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001
EOF
    echo "✅ .env file created"
    echo ""
fi

# Build and start the all-in-one container
echo "🐳 Building and starting OfficePlane (this may take a few minutes)..."
docker compose build
docker compose up -d
echo ""

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
echo "   This can take 30-60 seconds on first run..."
sleep 10

# Wait for health check
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker compose exec -T officeplane curl -f http://localhost:8001/health >/dev/null 2>&1; then
        echo "✅ Services are ready!"
        break
    fi
    attempt=$((attempt + 1))
    echo "   Waiting... ($attempt/$max_attempts)"
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "⚠️  Services might still be starting. Check logs with: docker compose logs -f"
    echo ""
fi

# Initialize database (run migrations inside container)
echo "🗃️  Initializing database..."
docker compose exec -T officeplane bash -c "cd /app && prisma db push" || echo "⚠️  Database might already be initialized"
echo ""

echo "✅ OfficePlane is running!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Access your OfficePlane Management System:"
echo ""
echo "  📊 Management Dashboard:  http://localhost:3000"
echo "  🔌 API Documentation:     http://localhost:8001/docs"
echo "  🗄️  PostgreSQL:            localhost:5433"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f              # View logs"
echo "  docker compose logs -f officeplane  # View all service logs"
echo "  docker compose down                 # Stop services"
echo "  docker compose restart              # Restart services"
echo "  docker compose exec officeplane bash # Access container shell"
echo ""
echo "Inside the container, you can access:"
echo "  - PostgreSQL: psql -U officeplane -d officeplane"
echo "  - Prisma Studio: cd /app && npx prisma studio"
echo "  - Check processes: supervisorctl status"
echo ""
