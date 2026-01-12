# Phase 5: Testing & Validation - Quick Start Guide

**Goal:** Validate VAS-MS-V2 is production-ready with Ruth-AI integration as the critical success criterion.

---

## Quick Setup (15 minutes)

### 1. Install Test Dependencies

```bash
# Backend dependencies
cd backend
pip install pytest pytest-asyncio pytest-cov aiohttp

# Frontend dependencies
cd ../frontend
npm install --save-dev vitest @vitest/ui @testing-library/react
```

### 2. Create Test Directory Structure

```bash
# Backend test structure
mkdir -p backend/tests/{unit,integration}
mkdir -p backend/load_tests
mkdir -p backend/failure_tests

# Frontend test structure
mkdir -p frontend/tests/unit
```

### 3. Configure pytest

**File:** `backend/pytest.ini`
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --cov=app --cov-report=html --cov-report=term
```

### 4. Configure Vitest

**File:** `frontend/vitest.config.ts`
```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './'),
    },
  },
});
```

---

## Critical Path: Ruth-AI Integration (ONE AFTERNOON)

This is the **#1 priority** - if Ruth-AI can successfully integrate, everything else will follow.

### Prerequisites

1. **Backend running** with V2 API endpoints
2. **Router capabilities endpoint** implemented: `GET /api/v2/streams/{id}/router-capabilities`
3. **OAuth2 client** created for Ruth-AI:
   ```sql
   INSERT INTO oauth_clients (client_id, client_secret, name)
   VALUES ('ruth-ai', 'ruth-secret', 'Ruth-AI Detector');
   ```

### Run Ruth-AI Integration Test

```bash
cd backend/integration_tests

# Make executable
chmod +x test_ruth_ai_integration.py

# Run test
python3 test_ruth_ai_integration.py
```

**Expected Output:**
```
==========================================================
Ruth-AI Integration Test - ONE AFTERNOON
==========================================================

[1/6] Authenticating Ruth-AI...
✅ Authenticated - Token: eyJhbGciOiJIUzI1NiI...

[2/6] Discovering live stream...
✅ Stream discovered: stream-abc123

[3/6] Consuming stream...
✅ Consumer attached: consumer-xyz789

[4/6] Detecting person event...
✅ Person detected at 2026-01-10T15:30:45Z
   Confidence: 95.0%

[5/6] Creating AI-generated bookmark...
✅ Bookmark created: bookmark-def456
   Video URL: http://localhost:8080/media/bookmarks/bookmark-def456.mp4
   Event type: person_detected
   Confidence: 0.95

[6/6] Querying person detection bookmarks...
✅ Found 1 person detection bookmarks
   - bookmark-def456: Person detected by Ruth-AI (confidence: 0.95)

[BONUS] Downloading bookmark video...
✅ Video downloaded: ruth_ai_training_bookmark-def456.mp4 (2456789 bytes)
   Ready for Ruth-AI training dataset!

==========================================================
✅ ALL TESTS PASSED - Ruth-AI Integration Complete!
==========================================================

Ruth-AI can now:
  ✅ Authenticate and consume streams
  ✅ Create AI-generated bookmarks
  ✅ Query bookmarks by event type
  ✅ Download videos for training

🎉 ONE AFTERNOON SUCCESS CRITERION MET!
```

**If this test passes, Phase 5 is 80% complete!**

---

## Testing Workflow (Week 7-8)

### Week 7: Core Tests

#### Monday-Tuesday: Unit Tests
```bash
# Day 1: Backend unit tests
cd backend
pytest tests/unit/test_stream_state_machine.py -v
pytest tests/unit/test_jwt_auth.py -v
pytest tests/unit/test_consumer_service.py -v

# Day 2: More unit tests
pytest tests/unit/test_bookmark_service.py -v
pytest tests/unit/test_snapshot_service.py -v

# Generate coverage report
pytest --cov=app --cov-report=html
open htmlcov/index.html  # View coverage
```

#### Wednesday-Thursday: Integration Tests
```bash
# Day 3: curl-based test
cd backend/integration_tests
chmod +x test_stream_consumption.sh
./test_stream_consumption.sh

# Day 4: Ruth-AI integration (CRITICAL)
python3 test_ruth_ai_integration.py
```

#### Friday: Backend Endpoint
- Backend team implements router capabilities endpoint
- Test MediaSoupPlayerV2 with real backend
- Validate full WebRTC flow

### Week 8: Load, Failure & Docs

#### Monday-Tuesday: Load Tests
```bash
# Day 6: Concurrent streams
cd backend/load_tests
python3 test_concurrent_streams.py

# Bookmark throughput
python3 test_bookmark_throughput.py
```

#### Wednesday: Failure Tests
```bash
# Day 7: Crash recovery
cd backend/failure_tests
python3 test_ffmpeg_crash.py
python3 test_network_interruption.py
```

#### Thursday-Friday: Documentation
```bash
# Day 8-9: Complete docs
# - Write OpenAPI spec
# - Create integration guide
# - Write SDK examples
# - Record demo video
```

---

## Quick Test Commands

### Run All Tests
```bash
# Backend
cd backend
pytest tests/ -v --cov=app

# Frontend
cd frontend
npm test
```

### Run Specific Test Suite
```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Single test file
pytest tests/unit/test_jwt_auth.py -v
```

### Run with Coverage
```bash
# Backend with coverage
pytest --cov=app --cov-report=term-missing

# Frontend with coverage
npm run test:coverage
```

---

## Troubleshooting

### Test Failures

**Authentication errors (401)**
```bash
# Check OAuth client exists
psql -d vas_ms_v2 -c "SELECT * FROM oauth_clients WHERE client_id='test_client';"

# Create test client if missing
psql -d vas_ms_v2 -c "INSERT INTO oauth_clients (client_id, client_secret, name) VALUES ('test_client', 'test_secret', 'Test Client');"
```

**Stream not found (404)**
```bash
# Check active streams
curl http://localhost:8080/api/v2/streams?state=live

# Start test stream
curl -X POST http://localhost:8080/api/v1/devices/test-device/start-stream
```

**Router capabilities endpoint missing**
```bash
# Test endpoint exists
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8080/api/v2/streams/STREAM_ID/router-capabilities

# If 404, backend team needs to implement this endpoint
# See: MEDIASOUP_V2_BACKEND_REQUIREMENTS.md
```

---

## Success Criteria Checklist

### Critical Success Criteria

- [ ] **Ruth-AI integration test passes in ONE AFTERNOON** ⭐
  - [ ] Authenticates successfully
  - [ ] Consumes stream
  - [ ] Detects person event
  - [ ] Creates AI-generated bookmark
  - [ ] Queries bookmarks by event type
  - [ ] Downloads bookmark video

### Additional Success Criteria

- [ ] All unit tests pass (>80% coverage)
- [ ] curl-based integration test passes
- [ ] Load tests meet targets:
  - [ ] 10 concurrent streams
  - [ ] 50 consumers per stream
  - [ ] 500 bookmarks/hour
- [ ] Failure tests demonstrate graceful recovery
- [ ] OpenAPI documentation complete
- [ ] Integration guide written
- [ ] SDK examples working

---

## Next Steps After Phase 5

When all tests pass:

1. **Deploy to staging** environment
2. **Integrate Ruth-AI** in production
3. **Monitor metrics** (consumers, bookmarks, errors)
4. **Plan Phase 6**: Production deployment & monitoring

---

## Resources

- **Full Test Plan:** [PHASE_5_IMPLEMENTATION.md](PHASE_5_IMPLEMENTATION.md)
- **Backend Requirements:** [MEDIASOUP_V2_BACKEND_REQUIREMENTS.md](MEDIASOUP_V2_BACKEND_REQUIREMENTS.md)
- **Phase 4 Summary:** [PHASE_4_COMPLETION_SUMMARY.md](PHASE_4_COMPLETION_SUMMARY.md)

---

**Document Version:** 1.0
**Created:** 2026-01-10
**Status:** Ready to Execute

🚀 **Start with Ruth-AI integration test - it's the critical success criterion!**
