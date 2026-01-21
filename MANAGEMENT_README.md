# OfficePlane Management System

> Temporal-style orchestration UI for managing Office document instances at scale

## 🎯 Overview

The OfficePlane Management System provides a comprehensive web-based dashboard for managing document instances, task queues, and execution monitoring - think **Temporal UI for Office documents**.

### Key Features

- **📄 Document Instance Lifecycle** - Open, close, and monitor Word/Excel/PowerPoint documents in memory
- **⚡ Task Queue System** - Temporal-style task orchestration with automatic retries and exponential backoff
- **📊 Real-time Dashboard** - Live updates via WebSockets showing system state
- **📈 Metrics & Observability** - Track performance, failures, and resource usage
- **🔍 Execution History** - Complete audit trail of all events and state transitions
- **🎨 Modern UI** - Clean, responsive Next.js dashboard with TailwindCSS

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Next.js UI (Port 3000)                   │
│  Dashboard • Instances Panel • Queue Panel • History        │
└────────────────────┬────────────────────────────────────────┘
                     │ WebSocket + REST API
                     ▼
┌─────────────────────────────────────────────────────────────┐
│               FastAPI Backend (Port 8001)                    │
│  Instance Manager • Task Queue • Event Broadcasting          │
└────────────────────┬────────────────────────────────────────┘
                     │ Prisma Client (Python)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            PostgreSQL + pgvector (Port 5432)                 │
│  Documents • Instances • Tasks • History • Metrics           │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### 1. Setup

```bash
# Run the setup script
chmod +x setup.sh
./setup.sh

# Edit .env and add your OPENAI_API_KEY
nano .env
```

### 2. Start Services (Docker)

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

### 3. Initialize Database

```bash
# Run Prisma migrations
npx prisma migrate dev --name init

# Or apply migrations in production
npx prisma migrate deploy
```

### 4. Access the UI

- **Management Dashboard**: http://localhost:3000
- **API Documentation**: http://localhost:8001/docs
- **Prisma Studio**: `npx prisma studio`

## 📊 Dashboard Components

### Metrics Panel
Real-time system metrics:
- Active instances count
- Queued/running/completed tasks
- Average task duration
- Memory and CPU usage

### Instances Panel
Manage document instances:
- **Open Instance** - Create a new LibreOffice instance
- **View Details** - See PID, driver type, memory usage
- **Close Instance** - Gracefully shutdown an instance
- **Delete Instance** - Remove closed instances

### Task Queue Panel
Monitor and control tasks:
- **View Queue** - See all queued, running, and completed tasks
- **Priority Indicators** - Color-coded priority levels
- **Retry Status** - Track retry attempts
- **Cancel Tasks** - Stop running tasks
- **Manual Retry** - Retry failed tasks

### Execution History
Complete audit trail:
- All events and state transitions
- Task execution timings
- Error messages and stack traces
- Document operations

## 🔌 API Endpoints

### Instances
```bash
GET    /api/instances              # List all instances
POST   /api/instances              # Create new instance
GET    /api/instances/{id}         # Get instance details
POST   /api/instances/{id}/close   # Close instance
DELETE /api/instances/{id}         # Delete instance
```

### Tasks
```bash
GET    /api/tasks                  # List all tasks
POST   /api/tasks                  # Enqueue new task
GET    /api/tasks/{id}             # Get task details
POST   /api/tasks/{id}/cancel      # Cancel task
POST   /api/tasks/{id}/retry       # Retry task
```

### History & Metrics
```bash
GET    /api/history                # Get execution history
GET    /api/metrics                # Get system metrics
```

### WebSocket
```bash
WS     /ws                         # Real-time updates
```

## 💻 Development

### Local Development (without Docker)

```bash
# Terminal 1: Start PostgreSQL
docker run -d \
  -e POSTGRES_DB=officeplane \
  -e POSTGRES_USER=officeplane \
  -e POSTGRES_PASSWORD=officeplane \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# Terminal 2: Start FastAPI backend
cd src
uvicorn officeplane.api.main:app --reload --port 8001

# Terminal 3: Start Next.js UI
cd ui
npm run dev
```

### Generate Prisma Clients

```bash
# JavaScript client (for Next.js)
npx prisma generate

# Python client (for FastAPI)
prisma generate
```

### Database Migrations

```bash
# Create a new migration
npx prisma migrate dev --name <migration_name>

# View migration history
npx prisma migrate status

# Reset database (DANGER)
npx prisma migrate reset
```

## 🎯 Usage Examples

### Create and Open a Document Instance

```python
import requests

# Create instance
response = requests.post("http://localhost:8001/api/instances", json={
    "driverType": "libreoffice",
    "documentId": "doc-123",
    "filePath": "/path/to/document.docx"
})

instance = response.json()
instance_id = instance["id"]

# Instance will transition: OPENING → OPEN → IDLE
```

### Enqueue a Task

```python
# Enqueue document conversion task
response = requests.post("http://localhost:8001/api/tasks", json={
    "taskType": "convert_to_pdf",
    "taskName": "Convert quarterly report",
    "documentId": "doc-123",
    "instanceId": instance_id,
    "payload": {
        "dpi": 300,
        "output": "pdf"
    },
    "priority": "HIGH",
    "maxRetries": 3
})

task = response.json()
# Task will be picked up by a worker automatically
```

### Monitor via WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8001/ws');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log(`Event: ${message.type}`, message.data);
};

// Events you'll receive:
// - instance_update: Instance state changes
// - task_update: Task state changes
// - metrics_update: System metrics updates
```

## 🔧 Configuration

### Environment Variables

```bash
# Database
DATABASE_URL="postgresql://user:pass@host:5432/officeplane"

# OfficePlane
OFFICEPLANE_DRIVER=libreoffice  # or 'rust' or 'mock'
POOL_SIZE=6
CONVERT_TIMEOUT_SEC=45

# OpenAI (for embeddings)
OPENAI_API_KEY=sk-...

# Next.js
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001
```

### Task Queue Workers

Modify worker count in `task_queue.py`:

```python
class TaskQueue:
    def __init__(self):
        self.worker_count = 3  # Adjust based on load
```

### Instance Heartbeat

Modify heartbeat interval in `instance_manager.py`:

```python
async def _heartbeat_monitor(self, instance_id: str):
    # ...
    await asyncio.sleep(5)  # Heartbeat every 5 seconds
```

## 📦 Tech Stack

- **Frontend**: Next.js 15, React 19, TailwindCSS, React Query
- **Backend**: FastAPI, Python 3.10+, Prisma ORM
- **Database**: PostgreSQL 16 + pgvector
- **Real-time**: WebSockets
- **Containerization**: Docker + Docker Compose

## 🚨 Troubleshooting

### Database Connection Issues

```bash
# Check if PostgreSQL is running
docker compose ps

# View PostgreSQL logs
docker compose logs pgvector

# Test connection
psql postgresql://officeplane:officeplane@localhost:5432/officeplane
```

### Prisma Client Not Found

```bash
# Regenerate clients
npx prisma generate
prisma generate

# Reinstall dependencies
npm install
pip3 install -e ".[dev]"
```

### WebSocket Not Connecting

```bash
# Check if FastAPI is running
curl http://localhost:8001/health

# Check WebSocket endpoint
wscat -c ws://localhost:8001/ws
```

### UI Not Loading

```bash
# Check Next.js build
cd ui
npm run build

# Check environment variables
echo $NEXT_PUBLIC_API_URL
```

## 📚 Resources

- [OfficePlane Core Documentation](./README.md)
- [Prisma Documentation](https://www.prisma.io/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)

## 🤝 Contributing

This is an agentic framework designed to scale Office document manipulation. Contributions welcome!

## 📄 License

See main [README](./README.md) for license information.
