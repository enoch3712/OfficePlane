#!/bin/bash

# Check OfficePlane container status

echo "🔍 OfficePlane Container Status"
echo "================================"
echo ""

# Check if container is running
if ! docker compose ps | grep -q "officeplane"; then
    echo "❌ OfficePlane container is not running"
    echo ""
    echo "Start it with: ./quickstart.sh"
    exit 1
fi

echo "✅ Container Status:"
docker compose ps
echo ""

echo "📊 Service Status (inside container):"
docker compose exec officeplane supervisorctl status
echo ""

echo "🏥 Health Check:"
if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ FastAPI: Healthy (http://localhost:8001)"
else
    echo "❌ FastAPI: Not responding"
fi

if curl -sf http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Next.js UI: Healthy (http://localhost:3000)"
else
    echo "❌ Next.js UI: Not responding"
fi

# Check PostgreSQL
if docker compose exec -T officeplane pg_isready -U officeplane > /dev/null 2>&1; then
    echo "✅ PostgreSQL: Healthy (localhost:5433)"
else
    echo "❌ PostgreSQL: Not responding"
fi

echo ""
echo "📈 Resource Usage:"
docker stats --no-stream officeplane-allinone
echo ""

echo "Recent Logs (last 20 lines):"
echo "─────────────────────────────"
docker compose logs --tail=20 officeplane
