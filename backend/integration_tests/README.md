# VAS-MS-V2 Integration Tests

End-to-end integration tests that validate the complete V2 API flow.

## Prerequisites

1. **Backend running** on `http://localhost:8080`
2. **Database migrated** with V2 schema
3. **OAuth client created** for testing
4. **At least one live stream** running

## Setup

### Create Test OAuth Client

```sql
-- Connect to database
psql -U postgres -d vas_ms_v2

-- Create test client
INSERT INTO api_clients (client_id, client_secret, name, scopes)
VALUES (
    'test-client',
    'test-secret',
    'Integration Test Client',
    ARRAY['streams:read', 'streams:consume', 'bookmarks:read', 'bookmarks:write', 'snapshots:read', 'snapshots:write']
);
```

### Set Environment Variables

```bash
export TEST_CLIENT_ID=test-client
export TEST_CLIENT_SECRET=test-secret
export API_URL=http://localhost:8080
```

## Tests

### 1. curl-based Integration Test

**File:** `test_stream_consumption.sh`

Tests the complete V2 API using only HTTP/REST calls (no UI).

**Run:**
```bash
cd backend/integration_tests
./test_stream_consumption.sh
```

**What it tests:**
- ✅ System health
- ✅ OAuth2 authentication
- ✅ Stream discovery (list streams)
- ✅ Stream details retrieval
- ✅ Stream health metrics
- ✅ Consumer attachment (WebRTC signaling)
- ✅ Live bookmark creation
- ✅ Bookmark querying with filters
- ✅ Live snapshot creation
- ✅ Consumer detachment
- ✅ Cleanup (delete bookmarks/snapshots)

**Expected output:**
```
========================================
VAS-MS-V2 Integration Test Suite
========================================

[1] GET /api/v2/health - System health check
✅ PASS: System is healthy

[2] POST /api/v2/auth/token - OAuth2 authentication
✅ PASS: Authentication successful

[3] GET /api/v2/streams - List available streams
✅ PASS: Listed 2 stream(s)

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

### 2. Ruth-AI Integration Test ⭐ CRITICAL

**File:** `test_ruth_ai_integration.py`

**Critical Success Criterion:** Ruth-AI can integrate in ONE AFTERNOON

This test simulates a third-party AI application consuming VAS-MS-V2:

**Run:**
```bash
cd backend/integration_tests

# Install dependencies
pip install httpx

# Run test
python3 test_ruth_ai_integration.py
```

**What it tests:**
1. ✅ OAuth2 authentication
2. ✅ Stream discovery (find live streams)
3. ✅ Consumer attachment (WebRTC signaling)
4. ✅ AI event detection (person detection simulation)
5. ✅ AI-generated bookmark creation
6. ✅ Bookmark querying by event type
7. ✅ Video download for training dataset

**Expected output:**
```
================================================================================
RUTH-AI INTEGRATION TEST - VAS-MS-V2
================================================================================

Critical Success Criterion: Complete integration in ONE AFTERNOON
Started: 2026-01-10 15:30:00

============================================================
[1/7] Authenticating Ruth-AI with VAS-MS-V2
============================================================

✅ Authenticated as 'ruth-ai'
   Access token: eyJhbGciOiJIUzI1NiI...
   Token expires in: 3600 seconds

============================================================
[2/7] Discovering available streams
============================================================

✅ Discovered 2 live stream(s)
   - Front Door Camera (ID: stream-abc123, State: live)

...

============================================================
[7/7] Downloading bookmark video for training dataset
============================================================

✅ Bookmark video downloaded!
   Filename: ruth_ai_training_bookmark-def456.mp4
   File size: 1.23 MB
   Saved to: /tmp/ruth_ai_test/ruth_ai_training_bookmark-def456.mp4

================================================================================
✅ SUCCESS! RUTH-AI INTEGRATION TEST PASSED
================================================================================

Ruth-AI can now:
  ✅ Authenticate via OAuth2
  ✅ Discover and consume live streams
  ✅ Detect events with AI
  ✅ Create AI-generated bookmarks
  ✅ Query bookmarks by event type
  ✅ Download videos for training dataset

Test execution time: 3.2 minutes
🎉 ONE AFTERNOON SUCCESS CRITERION MET!
```

---

## Troubleshooting

### Authentication Errors (401)

```bash
# Check OAuth client exists
psql -d vas_ms_v2 -c "SELECT * FROM api_clients WHERE client_id='test-client';"

# Create if missing
psql -d vas_ms_v2 << 'EOF'
INSERT INTO api_clients (client_id, client_secret, name)
VALUES ('test-client', 'test-secret', 'Test Client');
EOF
```

### No Live Streams (404)

```bash
# Check streams
curl http://localhost:8080/api/v2/streams?state=live

# Start a stream
curl -X POST http://localhost:8080/api/v1/devices/DEVICE_ID/start-stream
```

### Dependencies Missing

```bash
# Python dependencies
pip install httpx pytest

# jq for shell scripts
sudo apt-get install jq  # Ubuntu/Debian
brew install jq          # macOS
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: vas_ms_v2_test

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install httpx pytest

      - name: Start backend
        run: |
          cd backend
          python main.py &
          sleep 10

      - name: Run integration tests
        env:
          TEST_CLIENT_ID: test-client
          TEST_CLIENT_SECRET: test-secret
          API_URL: http://localhost:8080
        run: |
          cd backend/integration_tests
          ./test_stream_consumption.sh
          python3 test_ruth_ai_integration.py
```

---

## Success Criteria

Phase 5 is complete when:

- ✅ `test_stream_consumption.sh` passes (all 12 tests)
- ✅ `test_ruth_ai_integration.py` passes (completes in <10 minutes for automation)
- ✅ Ruth-AI team validates they can integrate in ONE AFTERNOON

---

## Next Steps

After integration tests pass:

1. **Unit tests** - Add pytest unit tests for individual services
2. **Load tests** - Test with 50 concurrent consumers
3. **Failure tests** - Test crash recovery and error handling
4. **Documentation** - Complete OpenAPI spec and integration guide

---

**Created:** 2026-01-10
**Status:** Ready for execution
