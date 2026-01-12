# VAS-MS-V2 Deployment Guide

## Quick Start

This application runs on:
- **Frontend**: http://10.30.250.245:3200
- **Backend API**: http://10.30.250.245:8085
- **MediaSoup**: http://localhost:3001
- **Database**: PostgreSQL on port 5432
- **Cache**: Redis on port 6379

## Prerequisites

- Docker and Docker Compose installed
- Ports 3200, 8085, 5432, 6379, and 40000-40999 available
- At least 4GB RAM available for containers

## Deployment Steps

### 1. Stop Existing Containers (if any)

```bash
docker-compose down
```

### 2. Build and Start Services

```bash
# Build all services
docker-compose build

# Start all services in detached mode
docker-compose up -d

# Or combine both steps
docker-compose up -d --build
```

### 3. Check Service Status

```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f mediasoup
```

### 4. Run Database Migrations

```bash
# Access the backend container
docker exec -it vas-backend bash

# Inside the container, run migrations
alembic upgrade head

# Exit the container
exit
```

### 5. Verify Deployment

- Frontend: http://10.30.250.245:3200
- Backend Health: http://10.30.250.245:8085/health
- Backend API Docs: http://10.30.250.245:8085/docs

## Service Management

### Stop Services

```bash
docker-compose stop
```

### Restart Services

```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart backend
docker-compose restart frontend
```

### View Service Logs

```bash
# All services
docker-compose logs -f

# Specific service (last 100 lines)
docker-compose logs --tail=100 backend

# Follow logs for multiple services
docker-compose logs -f backend frontend
```

### Access Container Shell

```bash
# Backend
docker exec -it vas-backend bash

# Frontend
docker exec -it vas-frontend sh

# Database
docker exec -it vas-db psql -U vas -d vas_db
```

## Troubleshooting

### Services Won't Start

```bash
# Check logs for errors
docker-compose logs

# Remove old containers and volumes
docker-compose down -v

# Rebuild from scratch
docker-compose build --no-cache
docker-compose up -d
```

### Port Already in Use

If you get port conflict errors:

```bash
# Check what's using the port
sudo lsof -i :3200
sudo lsof -i :8085

# Kill the process or stop the old version
docker-compose -f /path/to/old/docker-compose.yml down
```

### Database Connection Issues

```bash
# Check database is running
docker-compose ps db

# View database logs
docker-compose logs db

# Verify database connection
docker exec -it vas-db psql -U vas -d vas_db -c "SELECT 1;"
```

### Frontend Can't Connect to Backend

1. Verify backend is running: `curl http://10.30.250.245:8085/health`
2. Check NEXT_PUBLIC_API_URL is set correctly in [docker-compose.yml](docker-compose.yml#L88)
3. Rebuild frontend: `docker-compose up -d --build frontend`

## Configuration

### Environment Variables

Edit [docker-compose.yml](docker-compose.yml) to modify:

- **Database credentials**: Lines 9-11
- **Backend API port**: Line 74
- **Frontend port**: Line 93
- **API URL**: Lines 88, 91
- **Authentication**: Lines 68-69
- **MediaSoup ports**: Lines 65-66

### Change Ports

To use different ports, update [docker-compose.yml](docker-compose.yml):

```yaml
frontend:
  ports:
    - "YOUR_PORT:3000"  # Change YOUR_PORT

backend:
  command: uvicorn main:app --host 0.0.0.0 --port YOUR_PORT --reload
```

Also update `NEXT_PUBLIC_API_URL` to match the new backend port.

## Production Recommendations

### 1. Enable Authentication

In [docker-compose.yml](docker-compose.yml):

```yaml
backend:
  environment:
    VAS_REQUIRE_AUTH: "true"
    VAS_API_KEY: "your-secure-api-key-here"
```

### 2. Use Production Database Credentials

```yaml
db:
  environment:
    POSTGRES_PASSWORD: "strong-random-password"
```

### 3. Disable Hot Reload

Remove `--reload` from backend command:

```yaml
backend:
  command: uvicorn main:app --host 0.0.0.0 --port 8085
```

### 4. Set Up Volumes for Persistence

Recordings and snapshots are already configured:
- `recordings:/app/recordings`
- `snapshots:/app/snapshots`

To backup:

```bash
docker run --rm -v vas-ms-v2_recordings:/data -v $(pwd):/backup \
  alpine tar czf /backup/recordings-backup.tar.gz -C /data .
```

### 5. Resource Limits

Add resource limits to prevent service overload:

```yaml
backend:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '1'
        memory: 512M
```

## Maintenance

### Backup Database

```bash
docker exec vas-db pg_dump -U vas vas_db > backup-$(date +%Y%m%d).sql
```

### Restore Database

```bash
cat backup-20260110.sql | docker exec -i vas-db psql -U vas -d vas_db
```

### Update Application

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Run any new migrations
docker exec -it vas-backend alembic upgrade head
```

### Clean Up

```bash
# Remove stopped containers
docker-compose down

# Remove volumes (WARNING: deletes data)
docker-compose down -v

# Clean up Docker system
docker system prune -a
```

## Network Architecture

- **Frontend** (port 3200): Next.js app in bridge network, exposed to host on 3200
- **Backend** (port 8085): FastAPI app in bridge network, exposed to host on 8085
- **MediaSoup** (port 3001, RTC ports 40000-40999): In bridge network with port mappings for WebRTC
- **Database** (port 5432): Internal bridge network (vas_net) + exposed for debugging
- **Redis** (port 6379): Internal bridge network (vas_net) + exposed for debugging

All services communicate within the `vas_net` bridge network:
- Backend connects to DB via `db:5432`
- Backend connects to Redis via `redis:6379`
- Backend connects to MediaSoup via `ws://mediasoup:3001`
- Frontend (browser) connects to Backend via host IP `10.30.250.245:8085`

## Authentication

The V2 API requires JWT authentication:
- **VAS_REQUIRE_AUTH**: Set to `"true"` in docker-compose.yml
- Default credentials configured for development
- Generate JWT tokens via `POST /v2/auth/token` endpoint
- Include token in `Authorization: Bearer <token>` header for all requests

**Important**: Change the default `JWT_SECRET_KEY` and `VAS_API_KEY` in production!

## Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- Verify health: http://10.30.250.245:8085/health
- API documentation: http://10.30.250.245:8085/docs
