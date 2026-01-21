# OfficePlane Docker Setup

This project supports both **Production** and **Development** modes with Docker Compose.

## Quick Start

### Production Mode (Optimized builds)
```bash
./prod.sh
```

### Development Mode (Hot-reload)
```bash
./dev.sh
```

## Modes Comparison

| Feature | Production | Development |
|---------|-----------|-------------|
| **Build Type** | Optimized standalone | Development server |
| **Hot-Reload** | ❌ No | ✅ Yes |
| **Code Changes** | Requires rebuild | Auto-reloads |
| **Performance** | ⚡ Fast | Slower (dev mode) |
| **Docker Image Size** | Smaller | Larger |
| **Use Case** | Deployment | Active development |

## Development Mode Features

### Hot-Reload Enabled ✅
- **UI Changes**: Edit files in `ui/` and see changes instantly
- **API Changes**: Edit files in `src/officeplane/` and API reloads automatically
- **CSS/Tailwind**: Style changes appear immediately
- **TypeScript**: Compilation happens on save

### Volume Mounts
The development mode mounts your source code into the container:
- `./ui` → Container UI code
- `./src/officeplane` → Container API code
- `./prisma` → Prisma schema

### Example Workflow
1. Start dev mode: `./dev.sh`
2. Edit `ui/app/page.tsx` in your editor
3. Save the file
4. Browser auto-refreshes with changes! 🎉

## Production Mode Features

### Optimized for Performance ⚡
- **Standalone builds**: Next.js creates optimized bundles
- **Minimal images**: Only includes production dependencies
- **Static assets**: Pre-compiled CSS and JavaScript
- **No source code**: Container doesn't include source files

### When to Use
- Running in production/staging
- Testing production builds locally
- Performance testing
- Final verification before deployment

## Common Commands

### Development Mode
```bash
# Start development environment
./dev.sh

# View all logs
docker compose -f docker-compose.dev.yml logs -f

# View UI logs only
docker compose -f docker-compose.dev.yml logs -f ui

# View API logs only
docker compose -f docker-compose.dev.yml logs -f api

# Restart a specific service
docker compose -f docker-compose.dev.yml restart ui

# Stop all services
docker compose -f docker-compose.dev.yml down

# Rebuild a service
docker compose -f docker-compose.dev.yml up -d --build ui
```

### Production Mode
```bash
# Start production environment
./prod.sh

# View all logs
docker compose logs -f

# View UI logs only
docker compose logs -f ui

# View API logs only
docker compose logs -f api

# Restart a specific service
docker compose restart ui

# Stop all services
docker compose down

# Rebuild a service
docker compose up -d --build ui
```

## Services

All modes run the same three services:

| Service | Port | Description |
|---------|------|-------------|
| **UI** | 3000 | Next.js frontend |
| **API** | 8001 | FastAPI backend |
| **Database** | 5433 | PostgreSQL + pgvector |

### Service URLs
- **UI**: http://localhost:3000
- **API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs
- **PostgreSQL**: postgresql://officeplane:officeplane@localhost:5433/officeplane

## Troubleshooting

### Styles not loading in production
If CSS doesn't load, rebuild the UI service:
```bash
docker compose down
docker compose up -d --build ui
```

### Hot-reload not working in dev mode
1. Check volume mounts are correct
2. Restart the service:
```bash
docker compose -f docker-compose.dev.yml restart ui
```

### Port conflicts
If ports 3000, 8001, or 5433 are in use:
1. Stop other services using those ports
2. Or modify the ports in `docker-compose.yml` or `docker-compose.dev.yml`

### Permission issues
If you get permission errors:
```bash
# Reset ownership
sudo chown -R $USER:$USER .

# Or run with sudo (not recommended)
sudo ./dev.sh
```

### Database connection issues
```bash
# Check database is healthy
docker compose ps

# View database logs
docker compose logs db

# Reset database
docker compose down -v  # WARNING: This deletes all data
docker compose up -d
```

## File Structure

```
.
├── docker-compose.yml          # Production configuration
├── docker-compose.dev.yml      # Development configuration
├── prod.sh                     # Production startup script
├── dev.sh                      # Development startup script
├── ui/
│   ├── Dockerfile              # Production Dockerfile
│   └── Dockerfile.dev          # Development Dockerfile
├── docker/
│   └── Dockerfile              # API Dockerfile
└── prisma/
    └── schema.prisma          # Database schema
```

## Tips for Development

### 1. Use Dev Mode for Active Development
Always use `./dev.sh` when you're actively coding. Changes will appear instantly.

### 2. Test in Production Mode Before Deploying
Before deploying, test your changes in production mode:
```bash
docker compose -f docker-compose.dev.yml down
./prod.sh
```

### 3. Watch Logs During Development
Keep logs open in a separate terminal:
```bash
docker compose -f docker-compose.dev.yml logs -f
```

### 4. Prisma Schema Changes
When you update the Prisma schema:
```bash
# In development mode, the container will auto-regenerate
# Just restart the affected services
docker compose -f docker-compose.dev.yml restart ui api
```

## Environment Variables

Create a `.env` file in the root directory:

```bash
# OpenAI API Key (optional)
OPENAI_API_KEY=sk-...

# Database (defaults shown)
DATABASE_URL=postgresql://officeplane:officeplane@db:5432/officeplane

# API URLs (defaults shown)
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001
```

## Next Steps

- **Development**: Run `./dev.sh` and start coding!
- **Production**: Run `./prod.sh` for optimized builds
- **Documentation**: Check `README.md` for project overview
- **API Docs**: Visit http://localhost:8001/docs when running
