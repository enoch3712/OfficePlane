# 🚀 OfficePlane All-in-One Container

> Single Docker container with PostgreSQL + FastAPI + Next.js UI

## Quick Start (30 seconds)

```bash
./quickstart.sh
```

That's it! The script will:
1. ✅ Create `.env` with your API key
2. 🐳 Build the all-in-one Docker container
3. 🚀 Start all services (PostgreSQL, FastAPI, Next.js)
4. 🗃️ Initialize the database
5. ✨ Open the dashboard at http://localhost:3000

## What's Inside the Container?

```
┌────────────────────────────────────────────┐
│         officeplane-allinone               │
│                                            │
│  PostgreSQL 15 + pgvector (port 5432)     │
│  FastAPI Backend      (port 8001)          │
│  Next.js UI           (port 3000)          │
│  LibreOffice + unoserver                   │
│                                            │
│  Managed by: supervisord                   │
└────────────────────────────────────────────┘
```

## Access Points

| Service | URL | Description |
|---------|-----|-------------|
| 📊 **Management UI** | http://localhost:3000 | Temporal-style dashboard |
| 🔌 **API Docs** | http://localhost:8001/docs | Interactive API documentation |
| 🗄️ **PostgreSQL** | localhost:5433 | Database (mapped to avoid conflicts) |

## Container Management

### Start
```bash
./quickstart.sh
```

### Stop
```bash
docker compose down
```

### Restart
```bash
docker compose restart
```

### View Logs
```bash
# All logs
docker compose logs -f

# Last 100 lines
docker compose logs --tail=100 officeplane

# Specific service inside container
docker compose exec officeplane supervisorctl tail -f officeplane-api
```

### Check Status
```bash
./status.sh
```

Shows:
- Container health
- Service status (PostgreSQL, FastAPI, Next.js)
- Resource usage
- Recent logs

### Access Container Shell
```bash
docker compose exec officeplane bash
```

Inside the container:
```bash
# Check service status
supervisorctl status

# View logs
tail -f /var/log/supervisor/officeplane-api.log
tail -f /var/log/supervisor/officeplane-ui.log
tail -f /var/log/supervisor/postgresql.log

# Access PostgreSQL
psql -U officeplane -d officeplane

# Run Prisma Studio
cd /app && npx prisma studio

# Check processes
ps aux | grep -E 'postgres|python|node'
```

## Troubleshooting

### Container won't start
```bash
# View build logs
docker compose build --progress=plain

# View startup logs
docker compose logs -f
```

### Services not responding
```bash
# Check service status inside container
docker compose exec officeplane supervisorctl status

# Restart a specific service
docker compose exec officeplane supervisorctl restart officeplane-api
docker compose exec officeplane supervisorctl restart officeplane-ui
docker compose exec officeplane supervisorctl restart postgresql
```

### Database issues
```bash
# Access PostgreSQL
docker compose exec officeplane psql -U officeplane -d officeplane

# Check if database exists
docker compose exec officeplane psql -U officeplane -l

# Reset database (DANGER!)
docker compose down -v  # Deletes all data
./quickstart.sh         # Fresh start
```

### Port conflicts
If ports 3000, 8001, or 5433 are in use, edit `docker-compose.yml`:

```yaml
ports:
  - "3001:3000"  # Change 3000 to 3001
  - "8002:8001"  # Change 8001 to 8002
  - "5434:5432"  # Change 5433 to 5434
```

### Performance tuning

Edit `docker/supervisord.conf` to adjust workers:

```ini
# Increase API workers
command=/opt/venv/bin/uvicorn officeplane.api.main:app --host 0.0.0.0 --port 8001 --workers 4
```

## Environment Variables

Edit `.env` to configure:

```bash
# OpenAI API Key (required for embeddings)
OPENAI_API_KEY=sk-...

# Driver type: libreoffice, rust, or mock
OFFICEPLANE_DRIVER=libreoffice

# Database connection (inside container)
DATABASE_URL=postgresql://officeplane:officeplane@localhost:5432/officeplane

# API URLs (for Next.js)
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001
```

## Data Persistence

Data is stored in Docker volumes:

```bash
# List volumes
docker volume ls | grep officeplane

# Inspect volume
docker volume inspect agenticdocs_officeplane_data

# Backup database
docker compose exec officeplane pg_dump -U officeplane officeplane > backup.sql

# Restore database
cat backup.sql | docker compose exec -T officeplane psql -U officeplane officeplane
```

## Development Mode

For active development, you can run services locally instead:

```bash
# Terminal 1: PostgreSQL only in Docker
docker run -d -p 5432:5432 \
  -e POSTGRES_DB=officeplane \
  -e POSTGRES_USER=officeplane \
  -e POSTGRES_PASSWORD=officeplane \
  pgvector/pgvector:pg16

# Terminal 2: FastAPI locally
cd src
pip install -e ".[dev]"
uvicorn officeplane.api.main:app --reload --port 8001

# Terminal 3: Next.js locally
cd ui
npm install
npm run dev
```

## Architecture

### Process Manager (supervisord)

All services run under `supervisord` for:
- Auto-restart on failure
- Centralized logging
- Process monitoring
- Graceful shutdown

### Database Schema

Managed by Prisma ORM:
- **Documents, Chapters, Sections, Pages** - Hierarchical document model
- **DocumentInstances** - Track open LibreOffice instances
- **TaskQueue** - Temporal-style task orchestration
- **ExecutionHistory** - Complete audit trail
- **Chunks** - Vector embeddings for RAG search

### API Routes

#### Management System
- `GET /api/instances` - List document instances
- `POST /api/instances` - Create instance
- `GET /api/tasks` - List tasks
- `POST /api/tasks` - Enqueue task
- `WS /ws` - Real-time updates

#### Document Operations
- `POST /render` - Convert documents
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

## Performance

**First Build**: ~5-10 minutes (downloads packages, installs LibreOffice)
**Subsequent Builds**: ~1-2 minutes (uses Docker cache)
**Startup Time**: ~30-60 seconds (PostgreSQL init, migrations, services)
**Memory Usage**: ~1-2 GB (LibreOffice is heavy)
**CPU Usage**: Variable (depends on document processing)

## Security Notes

⚠️ **This is a development setup**. For production:

1. Change default passwords
2. Use secrets management for API keys
3. Enable SSL/TLS
4. Configure firewall rules
5. Use non-root users
6. Enable PostgreSQL authentication
7. Add rate limiting
8. Set up monitoring/alerting

## What's Next?

1. **Open the dashboard**: http://localhost:3000
2. **Create a document instance**: Click "Open Instance"
3. **Queue a task**: Use the API or UI
4. **Watch it work**: Real-time updates via WebSocket

See [MANAGEMENT_README.md](./MANAGEMENT_README.md) for full documentation.

---

Built with ❤️ for agentic document manipulation at scale
