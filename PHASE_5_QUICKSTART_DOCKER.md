# Phase 5: Testing & Validation - Docker Compose Quick Start

**Goal:** Run comprehensive tests against VAS-MS-V2 using Docker Compose

---

## Important: Port Configuration

This VAS-MS-V2 instance runs on different ports to avoid conflicts with the older VAS instance:

- **Backend API**: http://10.30.250.245:8085 (not 8080)
- **Frontend**: http://10.30.250.245:3200 (not 3000)
- **Database**: Port 5433 (not 5432)
- **MediaSoup**: Port 3002 (not 3001)

---

## Quick Start (15 minutes)

### 1. Build and Start All Services

```bash
cd /home/atgin-rnd-ubuntu/vas-ms-v2

# Build and start all services
docker-compose up --build -d

# Check status
docker-compose ps

# Expected output:
# NAME                STATUS              PORTS
# vas-v2-backend      Up (healthy)        0.0.0.0:8085->8085/tcp
# vas-v2-frontend     Up (healthy)        0.0.0.0:3200->3000/tcp
# vas-v2-db           Up (healthy)        0.0.0.0:5433->5432/tcp
# vas-v2-mediasoup    Up (healthy)        0.0.0.0:3002->3001/tcp
# vas-v2-redis        Up (healthy)        0.0.0.0:6380->6379/tcp
```

### 2. Check Service Health

```bash
# Check backend health
curl http://10.30.250.245:8085/health

# Expected: {"status":"healthy"}

# Check backend logs
docker-compose logs backend --tail=50

# Check if all services are healthy
docker-compose ps | grep healthy
```

### 3. Apply Database Migrations

```bash
# Run migrations inside backend container
docker-compose exec backend alembic upgrade head

# Verify tables exist
docker-compose exec db psql -U vas -d vas_db -c "\dt"

# Expected tables:
# - streams
# - producers
# - consumers
# - stream_state_transitions
# - bookmarks
# - snapshots
# - api_clients (for OAuth)
```

### 4. Create Test OAuth Client

```bash
# Create test OAuth client in database
docker-compose exec db psql -U vas -d vas_db << 'EOF'
INSERT INTO api_clients (client_id, client_secret, name, scopes, created_at)
VALUES (
    'test-client',
    'test-secret',
    'Integration Test Client',
    ARRAY['streams:read', 'streams:consume', 'bookmarks:read', 'bookmarks:write', 'snapshots:read', 'snapshots:write'],
    NOW()
)
ON CONFLICT (client_id) DO NOTHING;

-- Create Ruth-AI client
INSERT INTO api_clients (client_id, client_secret, name, scopes, created_at)
VALUES (
    'ruth-ai',
    'ruth-secret',
    'Ruth-AI Person Detection',
    ARRAY['streams:read', 'streams:consume', 'bookmarks:read', 'bookmarks:write', 'snapshots:read', 'snapshots:write'],
    NOW()
)
ON CONFLICT (client_id) DO NOTHING;
EOF

# Verify clients created
docker-compose exec db psql -U vas -d vas_db -c "SELECT client_id, name FROM api_clients;"
```

### 5. Start a Test Stream (Optional)

If you have a test RTSP camera:

```bash
# Create a device via V1 API
curl -X POST http://10.30.250.245:8085/api/v1/devices \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Camera",
    "rtsp_url": "rtsp://your-camera-ip:554/stream"
  }'

# Start stream
curl -X POST http://10.30.250.245:8085/api/v1/devices/DEVICE_ID/start-stream
```

---

## Run Integration Tests

### Test 1: curl-based Integration Test

```bash
cd /home/atgin-rnd-ubuntu/vas-ms-v2/backend/integration_tests

# Set environment variables
export API_URL=http://10.30.250.245:8085
export TEST_CLIENT_ID=test-client
export TEST_CLIENT_SECRET=test-secret

# Make script executable
chmod +x test_stream_consumption.sh

# Run test
./test_stream_consumption.sh
```

**Expected output:**
```
========================================
VAS-MS-V2 Integration Test Suite
========================================
API URL: http://10.30.250.245:8085

[1] GET /api/v2/health - System health check
✅ PASS: System is healthy

[2] POST /api/v2/auth/token - OAuth2 authentication
✅ PASS: Authentication successful

...

========================================
Test Results Summary
========================================
Tests run:    12
Tests passed: 12
Tests failed: 0

✅ ALL INTEGRATION TESTS PASSED!
```

---

### Test 2: Ruth-AI Integration Test ⭐ CRITICAL

```bash
cd /home/atgin-rnd-ubuntu/vas-ms-v2/backend/integration_tests

# Install httpx if not already installed
pip install httpx

# Set environment
export API_URL=http://10.30.250.245:8085
export TEST_CLIENT_ID=ruth-ai
export TEST_CLIENT_SECRET=ruth-secret
export OUTPUT_DIR=/tmp/ruth_ai_test

# Run test
python3 test_ruth_ai_integration.py
```

**Expected output:**
```
================================================================================
RUTH-AI INTEGRATION TEST - VAS-MS-V2
================================================================================

[1/7] Authenticating Ruth-AI with VAS-MS-V2
✅ Authenticated as 'ruth-ai'

[2/7] Discovering available streams
✅ Discovered 1 live stream(s)

[3/7] Attaching WebRTC consumer to stream
✅ Consumer attached successfully

[4/7] Simulating AI person detection
✅ Person detected by Ruth-AI!

[5/7] Creating AI-generated bookmark
✅ AI-generated bookmark created!

[6/7] Querying person detection bookmarks
✅ Found 1 person detection bookmark(s)

[7/7] Downloading bookmark video for training dataset
✅ Bookmark video downloaded!

================================================================================
✅ SUCCESS! RUTH-AI INTEGRATION TEST PASSED
================================================================================

🎉 ONE AFTERNOON SUCCESS CRITERION MET!
```

---

## Troubleshooting

### Issue: Services not starting

```bash
# Check logs
docker-compose logs backend
docker-compose logs mediasoup
docker-compose logs db

# Restart services
docker-compose restart

# Full rebuild
docker-compose down
docker-compose up --build -d
```

### Issue: Database connection failed

```bash
# Check database is running
docker-compose ps db

# Check database logs
docker-compose logs db --tail=100

# Test connection
docker-compose exec backend python -c "
from sqlalchemy import create_engine
engine = create_engine('postgresql://vas:vas_password@db:5432/vas_db')
conn = engine.connect()
print('✅ Database connection successful')
"
```

### Issue: Migrations not applied

```bash
# Check current migration
docker-compose exec backend alembic current

# Apply migrations
docker-compose exec backend alembic upgrade head

# If migration fails, check logs
docker-compose logs backend | grep alembic
```

### Issue: MediaSoup not responding

```bash
# Check MediaSoup health
curl http://10.30.250.245:3002/health

# Check MediaSoup logs
docker-compose logs mediasoup --tail=100

# Restart MediaSoup
docker-compose restart mediasoup
```

### Issue: No live streams for testing

```bash
# Check streams via V2 API
curl -H "Authorization: Bearer TOKEN" \
  http://10.30.250.245:8085/api/v2/streams

# Check stream status in database
docker-compose exec db psql -U vas -d vas_db -c \
  "SELECT id, name, state FROM streams;"
```

### Issue: 401 Authentication errors

```bash
# Verify OAuth clients exist
docker-compose exec db psql -U vas -d vas_db -c \
  "SELECT client_id, name FROM api_clients;"

# Test authentication manually
curl -X POST http://10.30.250.245:8085/api/v2/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"test-client","client_secret":"test-secret"}'

# Expected: {"access_token":"...","token_type":"Bearer","expires_in":3600}
```

---

## Viewing Logs

### Backend logs
```bash
docker-compose logs backend --tail=100 -f
```

### All services logs
```bash
docker-compose logs --tail=50 -f
```

### Specific service
```bash
docker-compose logs mediasoup --tail=100
docker-compose logs db --tail=100
docker-compose logs redis --tail=100
```

---

## Running Tests Inside Backend Container

If you want to run tests inside the backend container:

```bash
# Enter backend container
docker-compose exec backend bash

# Inside container:
cd /app

# Run unit tests
pytest tests/unit/ -v

# Run specific test
pytest tests/unit/test_jwt_auth.py -v

# Run with coverage
pytest tests/unit/ --cov=app --cov-report=html

# Exit container
exit
```

---

## Accessing Services

### Backend API
- Base URL: http://10.30.250.245:8085
- Health: http://10.30.250.245:8085/health
- API Docs (if enabled): http://10.30.250.245:8085/docs

### Frontend
- URL: http://10.30.250.245:3200
- Login with OAuth credentials

### Database
```bash
# Connect to database from host
psql -h 10.30.250.245 -p 5433 -U vas -d vas_db

# Inside container
docker-compose exec db psql -U vas -d vas_db
```

### Redis
```bash
# Connect to Redis
redis-cli -h 10.30.250.245 -p 6380

# Inside container
docker-compose exec redis redis-cli
```

---

## Stopping Services

### Stop all services
```bash
docker-compose down
```

### Stop and remove volumes (clean slate)
```bash
docker-compose down -v
```

### Stop specific service
```bash
docker-compose stop backend
docker-compose start backend
```

---

## Next Steps

After integration tests pass:

1. **Unit tests** - Implement remaining unit tests
2. **Load tests** - Test with 50 concurrent consumers
3. **Failure tests** - Test crash recovery
4. **Documentation** - Complete OpenAPI spec

---

## Success Criteria Checklist

Phase 5 is complete when:

- [ ] curl-based integration test passes (12/12 tests)
- [ ] Ruth-AI integration test passes ⭐
- [ ] All services healthy in docker-compose
- [ ] No errors in backend logs
- [ ] Database migrations applied
- [ ] OAuth clients created
- [ ] At least one live stream working

---

**Created:** 2026-01-10
**Status:** Ready for execution with Docker Compose
**Port:** Backend on 8085, Frontend on 3200
