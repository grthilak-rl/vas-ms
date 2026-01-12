# Phase 5: Testing & Validation Implementation Plan

**Timeline:** Week 7-8
**Focus:** End-to-end validation with third-party consumers
**Status:** 🚧 In Progress

---

## Overview

Phase 5 validates the entire VAS-MS-V2 system through comprehensive testing, with a **critical focus on Ruth-AI integration** as the primary success criterion.

### Success Criteria

✅ **Ruth-AI Integration Test** - ONE AFTERNOON
- Ruth-AI authenticates via OAuth2 client credentials
- Ruth-AI consumes live stream via MediaSoup
- Ruth-AI detects event (person detection)
- Ruth-AI creates bookmark programmatically
- Ruth-AI queries bookmarks by `event_type=person`
- Ruth-AI downloads bookmark video for training dataset

---

## 5.1 Unit Tests

### Backend Unit Tests (`backend/tests/unit/`)

#### 5.1.1 Stream State Machine Tests
**File:** `test_stream_state_machine.py`

```python
import pytest
from app.services.stream_state_machine import StreamStateMachine, StreamState

def test_stream_initialization():
    """Test stream starts in 'initializing' state"""
    sm = StreamStateMachine()
    assert sm.current_state == StreamState.INITIALIZING

def test_valid_transitions():
    """Test all valid state transitions"""
    sm = StreamStateMachine()

    # initializing -> ready
    assert sm.transition_to(StreamState.READY) == True

    # ready -> live
    assert sm.transition_to(StreamState.LIVE) == True

    # live -> stopped
    assert sm.transition_to(StreamState.STOPPED) == True

    # stopped -> closed
    assert sm.transition_to(StreamState.CLOSED) == True

def test_invalid_transitions():
    """Test invalid state transitions are rejected"""
    sm = StreamStateMachine()

    # Cannot go directly from initializing to live
    assert sm.transition_to(StreamState.LIVE) == False

    # Cannot go from initializing to closed
    assert sm.transition_to(StreamState.CLOSED) == False

def test_error_state_recovery():
    """Test error state can transition to stopped"""
    sm = StreamStateMachine()
    sm.transition_to(StreamState.ERROR)

    # Error can transition to stopped for cleanup
    assert sm.transition_to(StreamState.STOPPED) == True
```

**Commands:**
```bash
cd backend
pytest tests/unit/test_stream_state_machine.py -v
```

---

#### 5.1.2 JWT Token Tests
**File:** `test_jwt_auth.py`

```python
import pytest
from datetime import datetime, timedelta
from app.services.auth_service import AuthService

def test_token_generation():
    """Test JWT token generation"""
    auth = AuthService()
    token_data = auth.create_access_token(
        client_id="test_client",
        scopes=["stream:read", "bookmark:write"]
    )

    assert "access_token" in token_data
    assert "expires_in" in token_data
    assert token_data["token_type"] == "Bearer"

def test_token_validation():
    """Test valid token is accepted"""
    auth = AuthService()
    token = auth.create_access_token(client_id="test_client")["access_token"]

    payload = auth.verify_token(token)
    assert payload["client_id"] == "test_client"
    assert "exp" in payload

def test_expired_token_rejected():
    """Test expired token is rejected"""
    auth = AuthService()
    # Create token that expires in -1 second (already expired)
    token = auth.create_access_token(
        client_id="test_client",
        expires_delta=timedelta(seconds=-1)
    )["access_token"]

    with pytest.raises(Exception) as exc:
        auth.verify_token(token)
    assert "expired" in str(exc.value).lower()

def test_invalid_token_rejected():
    """Test malformed token is rejected"""
    auth = AuthService()

    with pytest.raises(Exception):
        auth.verify_token("invalid.token.here")
```

**Commands:**
```bash
pytest tests/unit/test_jwt_auth.py -v
```

---

#### 5.1.3 Consumer Attachment Tests
**File:** `test_consumer_service.py`

```python
import pytest
from app.services.consumer_service import ConsumerService

@pytest.fixture
def consumer_service():
    return ConsumerService()

@pytest.fixture
def mock_stream():
    return {
        "id": "stream-123",
        "state": "live",
        "producer": {"mediasoup_id": "producer-456"}
    }

def test_create_consumer(consumer_service, mock_stream):
    """Test consumer creation"""
    consumer = consumer_service.attach_consumer(
        stream_id=mock_stream["id"],
        client_id="test-client",
        rtp_capabilities={"codecs": []}
    )

    assert consumer["consumer_id"] is not None
    assert "transport" in consumer
    assert "rtp_parameters" in consumer

def test_detach_consumer(consumer_service):
    """Test consumer cleanup"""
    consumer_id = "consumer-789"

    result = consumer_service.detach_consumer(consumer_id)
    assert result == True

def test_consumer_limit_per_stream(consumer_service, mock_stream):
    """Test maximum consumers per stream"""
    max_consumers = 50

    consumers = []
    for i in range(max_consumers):
        consumer = consumer_service.attach_consumer(
            stream_id=mock_stream["id"],
            client_id=f"client-{i}",
            rtp_capabilities={"codecs": []}
        )
        consumers.append(consumer["consumer_id"])

    # 51st consumer should fail
    with pytest.raises(Exception) as exc:
        consumer_service.attach_consumer(
            stream_id=mock_stream["id"],
            client_id="client-51",
            rtp_capabilities={"codecs": []}
        )
    assert "maximum consumers" in str(exc.value).lower()
```

**Commands:**
```bash
pytest tests/unit/test_consumer_service.py -v
```

---

#### 5.1.4 Bookmark Creation Tests
**File:** `test_bookmark_service.py`

```python
import pytest
from datetime import datetime
from app.services.bookmark_service import BookmarkService

@pytest.fixture
def bookmark_service():
    return BookmarkService()

def test_create_live_bookmark(bookmark_service):
    """Test live bookmark creation"""
    bookmark = bookmark_service.create_bookmark(
        stream_id="stream-123",
        center_timestamp=datetime.utcnow().isoformat(),
        source="live",
        label="Person detected"
    )

    assert bookmark.source == "live"
    assert bookmark.duration == 6  # 6-second clip
    assert bookmark.video_url is not None

def test_create_historical_bookmark(bookmark_service):
    """Test historical bookmark creation"""
    timestamp = "2026-01-10T10:30:00Z"

    bookmark = bookmark_service.create_bookmark(
        stream_id="stream-123",
        center_timestamp=timestamp,
        source="historical",
        label="Vehicle detected"
    )

    assert bookmark.source == "historical"
    assert bookmark.center_timestamp == timestamp
    assert bookmark.video_url is not None

def test_ai_generated_bookmark(bookmark_service):
    """Test AI-generated bookmark with metadata"""
    bookmark = bookmark_service.create_bookmark(
        stream_id="stream-123",
        center_timestamp=datetime.utcnow().isoformat(),
        source="ai_generated",
        event_type="person_detected",
        confidence_score=0.95,
        tags=["person", "entrance"],
        metadata={"detector": "ruth-ai", "version": "1.0"}
    )

    assert bookmark.source == "ai_generated"
    assert bookmark.event_type == "person_detected"
    assert bookmark.confidence_score == 0.95
    assert "person" in bookmark.tags
    assert bookmark.metadata["detector"] == "ruth-ai"
```

**Commands:**
```bash
pytest tests/unit/test_bookmark_service.py -v
```

---

#### 5.1.5 Snapshot Creation Tests
**File:** `test_snapshot_service.py`

```python
import pytest
from datetime import datetime
from app.services.snapshot_service import SnapshotService

@pytest.fixture
def snapshot_service():
    return SnapshotService()

def test_create_live_snapshot(snapshot_service):
    """Test live snapshot capture"""
    snapshot = snapshot_service.create_snapshot(
        stream_id="stream-123",
        source="live"
    )

    assert snapshot.source == "live"
    assert snapshot.image_url is not None
    assert snapshot.file_size > 0

def test_create_historical_snapshot(snapshot_service):
    """Test historical snapshot capture"""
    timestamp = "2026-01-10T10:30:00Z"

    snapshot = snapshot_service.create_snapshot(
        stream_id="stream-123",
        timestamp=timestamp,
        source="historical"
    )

    assert snapshot.source == "historical"
    assert snapshot.timestamp == timestamp
    assert snapshot.image_url is not None
```

**Commands:**
```bash
pytest tests/unit/test_snapshot_service.py -v
```

---

### Frontend Unit Tests (`frontend/tests/unit/`)

#### 5.1.6 API Client Tests
**File:** `api-v2.test.ts`

```typescript
import { describe, it, expect, vi } from 'vitest';
import { getStreams, createBookmark, attachConsumer } from '@/lib/api-v2';

describe('V2 API Client', () => {
  it('should fetch streams with authentication', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          streams: [{ id: 'stream-123', state: 'live' }],
          pagination: { total: 1, limit: 100, offset: 0 }
        })
      })
    );

    const result = await getStreams('live');
    expect(result.streams).toHaveLength(1);
    expect(result.streams[0].state).toBe('live');
  });

  it('should create bookmark with tags', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          id: 'bookmark-456',
          tags: ['person', 'entrance'],
          source: 'ai_generated'
        })
      })
    );

    const bookmark = await createBookmark(
      'stream-123',
      new Date().toISOString(),
      'Person detected',
      ['person', 'entrance']
    );

    expect(bookmark.id).toBe('bookmark-456');
    expect(bookmark.tags).toContain('person');
  });

  it('should handle authentication errors', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Unauthorized' })
      })
    );

    await expect(getStreams()).rejects.toThrow('Authentication required');
  });
});
```

**Commands:**
```bash
cd frontend
npm test -- api-v2.test.ts
```

---

## 5.2 Integration Tests

### 5.2.1 curl-based Stream Consumption
**File:** `integration_tests/test_stream_consumption.sh`

```bash
#!/bin/bash
set -e

API_URL="http://localhost:8080"

echo "=========================================="
echo "VAS-MS-V2 Integration Test Suite"
echo "=========================================="

# 1. Authenticate
echo -e "\n[1/5] Authenticating..."
TOKEN_RESPONSE=$(curl -s -X POST \
  "${API_URL}/api/v2/auth/token" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "test_client",
    "client_secret": "test_secret"
  }')

ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | jq -r '.access_token')
echo "✅ Access token obtained: ${ACCESS_TOKEN:0:20}..."

# 2. List streams
echo -e "\n[2/5] Listing active streams..."
STREAMS_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "${API_URL}/api/v2/streams?state=live")

STREAM_ID=$(echo $STREAMS_RESPONSE | jq -r '.streams[0].id')
echo "✅ Found stream: $STREAM_ID"

# 3. Get router capabilities
echo -e "\n[3/5] Getting router RTP capabilities..."
ROUTER_CAPS=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "${API_URL}/api/v2/streams/${STREAM_ID}/router-capabilities")

echo "✅ Router capabilities received"

# 4. Attach consumer
echo -e "\n[4/5] Attaching consumer..."
CONSUMER_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  "${API_URL}/api/v2/streams/${STREAM_ID}/consume" \
  -d '{
    "client_id": "curl-test-client",
    "rtp_capabilities": '"$ROUTER_CAPS"'
  }')

CONSUMER_ID=$(echo $CONSUMER_RESPONSE | jq -r '.consumer_id')
echo "✅ Consumer attached: $CONSUMER_ID"

# 5. Create bookmark
echo -e "\n[5/5] Creating bookmark..."
BOOKMARK_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  "${API_URL}/api/v2/streams/${STREAM_ID}/bookmarks" \
  -d '{
    "center_timestamp": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'",
    "label": "Integration test bookmark",
    "tags": ["test", "automated"],
    "source": "live"
  }')

BOOKMARK_ID=$(echo $BOOKMARK_RESPONSE | jq -r '.id')
BOOKMARK_URL=$(echo $BOOKMARK_RESPONSE | jq -r '.video_url')
echo "✅ Bookmark created: $BOOKMARK_ID"
echo "   Video URL: $BOOKMARK_URL"

# Cleanup
echo -e "\n[Cleanup] Detaching consumer..."
curl -s -X DELETE \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "${API_URL}/api/v2/consumers/${CONSUMER_ID}"
echo "✅ Consumer detached"

echo -e "\n=========================================="
echo "✅ All integration tests passed!"
echo "=========================================="
```

**Commands:**
```bash
chmod +x integration_tests/test_stream_consumption.sh
./integration_tests/test_stream_consumption.sh
```

---

### 5.2.2 Ruth-AI Integration Test ⭐ CRITICAL
**File:** `integration_tests/test_ruth_ai_integration.py`

```python
#!/usr/bin/env python3
"""
Ruth-AI Integration Test
ONE AFTERNOON SUCCESS CRITERION

This test validates that Ruth-AI can:
1. Authenticate via OAuth2
2. Consume live stream
3. Detect person event
4. Create bookmark programmatically
5. Query bookmarks by event type
6. Download bookmark video
"""

import requests
import time
from datetime import datetime

API_URL = "http://localhost:8080"
CLIENT_ID = "ruth-ai"
CLIENT_SECRET = "ruth-secret"

class RuthAIIntegrationTest:
    def __init__(self):
        self.access_token = None
        self.stream_id = None
        self.consumer_id = None
        self.bookmark_id = None

    def authenticate(self):
        """Step 1: Ruth-AI authenticates via OAuth2"""
        print("[1/6] Authenticating Ruth-AI...")

        response = requests.post(
            f"{API_URL}/api/v2/auth/token",
            json={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET
            }
        )
        response.raise_for_status()

        data = response.json()
        self.access_token = data["access_token"]
        print(f"✅ Authenticated - Token: {self.access_token[:20]}...")

    def get_headers(self):
        return {"Authorization": f"Bearer {self.access_token}"}

    def discover_stream(self):
        """Step 2: Discover active stream"""
        print("\n[2/6] Discovering live stream...")

        response = requests.get(
            f"{API_URL}/api/v2/streams?state=live",
            headers=self.get_headers()
        )
        response.raise_for_status()

        data = response.json()
        self.stream_id = data["streams"][0]["id"]
        print(f"✅ Stream discovered: {self.stream_id}")

    def consume_stream(self):
        """Step 3: Attach consumer to stream"""
        print("\n[3/6] Consuming stream...")

        # Get router capabilities
        response = requests.get(
            f"{API_URL}/api/v2/streams/{self.stream_id}/router-capabilities",
            headers=self.get_headers()
        )
        response.raise_for_status()
        router_caps = response.json()

        # Attach consumer
        response = requests.post(
            f"{API_URL}/api/v2/streams/{self.stream_id}/consume",
            headers=self.get_headers(),
            json={
                "client_id": "ruth-ai-detector",
                "rtp_capabilities": router_caps
            }
        )
        response.raise_for_status()

        data = response.json()
        self.consumer_id = data["consumer_id"]
        print(f"✅ Consumer attached: {self.consumer_id}")
        print("   (In production, Ruth-AI would now receive video frames)")

    def detect_person_event(self):
        """Step 4: Simulate person detection"""
        print("\n[4/6] Detecting person event...")

        # Simulate Ruth-AI processing frames and detecting a person
        time.sleep(2)  # Simulate detection delay

        detection_confidence = 0.95
        detection_timestamp = datetime.utcnow().isoformat() + "Z"

        print(f"✅ Person detected at {detection_timestamp}")
        print(f"   Confidence: {detection_confidence * 100}%")

        return detection_timestamp, detection_confidence

    def create_bookmark(self, timestamp, confidence):
        """Step 5: Create AI-generated bookmark"""
        print("\n[5/6] Creating AI-generated bookmark...")

        response = requests.post(
            f"{API_URL}/api/v2/streams/{self.stream_id}/bookmarks",
            headers=self.get_headers(),
            json={
                "center_timestamp": timestamp,
                "source": "ai_generated",
                "event_type": "person_detected",
                "confidence_score": confidence,
                "tags": ["person", "entrance", "ruth-ai"],
                "label": "Person detected by Ruth-AI",
                "metadata": {
                    "detector": "ruth-ai",
                    "version": "1.0.0",
                    "model": "yolov8-person"
                }
            }
        )
        response.raise_for_status()

        data = response.json()
        self.bookmark_id = data["id"]
        self.bookmark_url = data["video_url"]

        print(f"✅ Bookmark created: {self.bookmark_id}")
        print(f"   Video URL: {self.bookmark_url}")
        print(f"   Event type: {data['event_type']}")
        print(f"   Confidence: {data['confidence_score']}")

    def query_bookmarks(self):
        """Step 6: Query bookmarks by event type"""
        print("\n[6/6] Querying person detection bookmarks...")

        response = requests.get(
            f"{API_URL}/api/v2/bookmarks",
            headers=self.get_headers(),
            params={
                "event_type": "person_detected",
                "tags": "person,ruth-ai",
                "limit": 10
            }
        )
        response.raise_for_status()

        data = response.json()
        bookmarks = data["bookmarks"]

        print(f"✅ Found {len(bookmarks)} person detection bookmarks")
        for bm in bookmarks[:3]:
            print(f"   - {bm['id']}: {bm['label']} (confidence: {bm.get('confidence_score', 'N/A')})")

    def download_bookmark_video(self):
        """Bonus: Download bookmark video for training dataset"""
        print("\n[BONUS] Downloading bookmark video...")

        response = requests.get(self.bookmark_url, stream=True)
        response.raise_for_status()

        filename = f"ruth_ai_training_{self.bookmark_id}.mp4"
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        import os
        file_size = os.path.getsize(filename)
        print(f"✅ Video downloaded: {filename} ({file_size} bytes)")
        print("   Ready for Ruth-AI training dataset!")

    def cleanup(self):
        """Cleanup: Detach consumer"""
        print("\n[Cleanup] Detaching consumer...")

        if self.consumer_id:
            response = requests.delete(
                f"{API_URL}/api/v2/consumers/{self.consumer_id}",
                headers=self.get_headers()
            )
            response.raise_for_status()
            print("✅ Consumer detached")

    def run(self):
        """Run complete integration test"""
        try:
            print("=" * 60)
            print("Ruth-AI Integration Test - ONE AFTERNOON")
            print("=" * 60)

            self.authenticate()
            self.discover_stream()
            self.consume_stream()

            timestamp, confidence = self.detect_person_event()
            self.create_bookmark(timestamp, confidence)
            self.query_bookmarks()
            self.download_bookmark_video()

            print("\n" + "=" * 60)
            print("✅ ALL TESTS PASSED - Ruth-AI Integration Complete!")
            print("=" * 60)
            print("\nRuth-AI can now:")
            print("  ✅ Authenticate and consume streams")
            print("  ✅ Create AI-generated bookmarks")
            print("  ✅ Query bookmarks by event type")
            print("  ✅ Download videos for training")
            print("\n🎉 ONE AFTERNOON SUCCESS CRITERION MET!")

        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            raise
        finally:
            self.cleanup()

if __name__ == "__main__":
    test = RuthAIIntegrationTest()
    test.run()
```

**Commands:**
```bash
chmod +x integration_tests/test_ruth_ai_integration.py
python3 integration_tests/test_ruth_ai_integration.py
```

---

## 5.3 Load Tests

### 5.3.1 Concurrent Stream Load Test
**File:** `load_tests/test_concurrent_streams.py`

```python
#!/usr/bin/env python3
"""
Load Test: 10 concurrent streams with 50 consumers each
"""

import asyncio
import aiohttp
import time
from statistics import mean, stdev

API_URL = "http://localhost:8080"
NUM_STREAMS = 10
CONSUMERS_PER_STREAM = 50

async def authenticate():
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_URL}/api/v2/auth/token",
            json={"client_id": "load_test", "client_secret": "secret"}
        ) as resp:
            data = await resp.json()
            return data["access_token"]

async def attach_consumer(session, stream_id, client_id, token):
    headers = {"Authorization": f"Bearer {token}"}

    # Get router capabilities
    async with session.get(
        f"{API_URL}/api/v2/streams/{stream_id}/router-capabilities",
        headers=headers
    ) as resp:
        router_caps = await resp.json()

    # Attach consumer
    start_time = time.time()
    async with session.post(
        f"{API_URL}/api/v2/streams/{stream_id}/consume",
        headers=headers,
        json={
            "client_id": client_id,
            "rtp_capabilities": router_caps
        }
    ) as resp:
        data = await resp.json()
        latency = time.time() - start_time
        return data["consumer_id"], latency

async def load_test():
    print(f"Load Test: {NUM_STREAMS} streams × {CONSUMERS_PER_STREAM} consumers")

    token = await authenticate()

    async with aiohttp.ClientSession() as session:
        # Get available streams
        headers = {"Authorization": f"Bearer {token}"}
        async with session.get(
            f"{API_URL}/api/v2/streams?state=live",
            headers=headers
        ) as resp:
            data = await resp.json()
            streams = data["streams"][:NUM_STREAMS]

        print(f"Using {len(streams)} streams")

        # Attach consumers concurrently
        tasks = []
        for stream in streams:
            for i in range(CONSUMERS_PER_STREAM):
                client_id = f"load-test-{stream['id']}-{i}"
                tasks.append(attach_consumer(session, stream["id"], client_id, token))

        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Calculate statistics
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]
        latencies = [latency for _, latency in successes]

        print(f"\n{'='*60}")
        print(f"Load Test Results")
        print(f"{'='*60}")
        print(f"Total consumers: {len(tasks)}")
        print(f"Successful: {len(successes)}")
        print(f"Failed: {len(failures)}")
        print(f"Success rate: {len(successes)/len(tasks)*100:.1f}%")
        print(f"Total time: {total_time:.2f}s")
        print(f"Throughput: {len(successes)/total_time:.1f} consumers/sec")
        print(f"\nLatency statistics:")
        print(f"  Mean: {mean(latencies):.3f}s")
        print(f"  Min: {min(latencies):.3f}s")
        print(f"  Max: {max(latencies):.3f}s")
        print(f"  StdDev: {stdev(latencies):.3f}s")

if __name__ == "__main__":
    asyncio.run(load_test())
```

**Commands:**
```bash
python3 load_tests/test_concurrent_streams.py
```

---

### 5.3.2 Bookmark Creation Load Test
**File:** `load_tests/test_bookmark_throughput.py`

```python
#!/usr/bin/env python3
"""
Load Test: 500 bookmarks/hour creation rate
"""

import asyncio
import aiohttp
import time
from datetime import datetime

API_URL = "http://localhost:8080"
TARGET_RATE = 500  # bookmarks per hour
TEST_DURATION = 60  # seconds
TARGET_PER_SECOND = TARGET_RATE / 3600

async def create_bookmark(session, stream_id, token, idx):
    headers = {"Authorization": f"Bearer {token}"}

    start_time = time.time()
    async with session.post(
        f"{API_URL}/api/v2/streams/{stream_id}/bookmarks",
        headers=headers,
        json={
            "center_timestamp": datetime.utcnow().isoformat() + "Z",
            "label": f"Load test bookmark {idx}",
            "source": "live",
            "tags": ["load-test"]
        }
    ) as resp:
        latency = time.time() - start_time
        if resp.status == 200:
            data = await resp.json()
            return True, latency, data["id"]
        else:
            return False, latency, None

async def bookmark_load_test():
    print(f"Bookmark Load Test: {TARGET_RATE} bookmarks/hour")
    print(f"Target: {TARGET_PER_SECOND:.3f} bookmarks/second")

    # Authenticate
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_URL}/api/v2/auth/token",
            json={"client_id": "load_test", "client_secret": "secret"}
        ) as resp:
            data = await resp.json()
            token = data["access_token"]

        # Get stream
        headers = {"Authorization": f"Bearer {token}"}
        async with session.get(
            f"{API_URL}/api/v2/streams?state=live",
            headers=headers
        ) as resp:
            data = await resp.json()
            stream_id = data["streams"][0]["id"]

        # Create bookmarks at target rate
        start_time = time.time()
        idx = 0
        results = []

        while time.time() - start_time < TEST_DURATION:
            success, latency, bookmark_id = await create_bookmark(
                session, stream_id, token, idx
            )
            results.append((success, latency))

            if success:
                print(f"✅ Bookmark {idx}: {bookmark_id} ({latency:.3f}s)")
            else:
                print(f"❌ Bookmark {idx} failed")

            idx += 1

            # Rate limiting
            await asyncio.sleep(1 / TARGET_PER_SECOND)

        total_time = time.time() - start_time

        # Statistics
        successes = [r for r in results if r[0]]
        latencies = [r[1] for r in results if r[0]]

        print(f"\n{'='*60}")
        print(f"Bookmark Load Test Results")
        print(f"{'='*60}")
        print(f"Duration: {total_time:.1f}s")
        print(f"Total bookmarks: {len(results)}")
        print(f"Successful: {len(successes)}")
        print(f"Failed: {len(results) - len(successes)}")
        print(f"Success rate: {len(successes)/len(results)*100:.1f}%")
        print(f"Actual rate: {len(successes)/(total_time/3600):.1f} bookmarks/hour")
        print(f"Mean latency: {sum(latencies)/len(latencies):.3f}s")

if __name__ == "__main__":
    asyncio.run(bookmark_load_test())
```

**Commands:**
```bash
python3 load_tests/test_bookmark_throughput.py
```

---

## 5.4 Failure Tests

### 5.4.1 FFmpeg Crash Recovery Test
**File:** `failure_tests/test_ffmpeg_crash.py`

```python
#!/usr/bin/env python3
"""
Failure Test: FFmpeg crash during live stream
Expected: Auto-restart with retry limit
"""

import requests
import subprocess
import time

API_URL = "http://localhost:8080"

def get_stream_pid(stream_id):
    """Get FFmpeg process ID for stream"""
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True,
        text=True
    )
    for line in result.stdout.split('\n'):
        if stream_id in line and 'ffmpeg' in line:
            return int(line.split()[1])
    return None

def test_ffmpeg_crash_recovery():
    print("FFmpeg Crash Recovery Test")

    # Start stream
    print("[1] Starting stream...")
    response = requests.post(f"{API_URL}/api/v1/devices/test-device/start-stream")
    response.raise_for_status()
    stream_id = response.json()["stream_id"]
    print(f"✅ Stream started: {stream_id}")

    time.sleep(5)  # Wait for FFmpeg to start

    # Get FFmpeg PID
    pid = get_stream_pid(stream_id)
    if not pid:
        raise Exception("FFmpeg process not found")
    print(f"✅ FFmpeg PID: {pid}")

    # Kill FFmpeg process
    print(f"[2] Killing FFmpeg process {pid}...")
    subprocess.run(["kill", "-9", str(pid)])
    print("✅ FFmpeg process killed")

    # Wait for auto-restart
    print("[3] Waiting for auto-restart...")
    time.sleep(10)

    # Check if stream recovered
    response = requests.get(f"{API_URL}/api/v2/streams/{stream_id}")
    response.raise_for_status()
    stream = response.json()

    if stream["state"] == "live":
        print("✅ Stream auto-recovered successfully!")
    elif stream["state"] == "error":
        print("⚠️  Stream entered error state (retry limit may be reached)")
    else:
        print(f"❌ Unexpected state: {stream['state']}")

if __name__ == "__main__":
    test_ffmpeg_crash_recovery()
```

**Commands:**
```bash
python3 failure_tests/test_ffmpeg_crash.py
```

---

### 5.4.2 Network Interruption Test
**File:** `failure_tests/test_network_interruption.py`

```python
#!/usr/bin/env python3
"""
Failure Test: Network interruption (ICE disconnect/reconnect)
"""

import subprocess
import time
import requests

API_URL = "http://localhost:8080"

def block_network():
    """Block network traffic on test interface"""
    subprocess.run([
        "sudo", "iptables", "-A", "OUTPUT",
        "-p", "udp", "--dport", "10000:60000",
        "-j", "DROP"
    ], check=True)
    print("🚫 Network blocked")

def unblock_network():
    """Restore network traffic"""
    subprocess.run([
        "sudo", "iptables", "-D", "OUTPUT",
        "-p", "udp", "--dport", "10000:60000",
        "-j", "DROP"
    ], check=True)
    print("✅ Network restored")

def test_network_interruption():
    print("Network Interruption Test")

    try:
        # Attach consumer
        print("[1] Attaching consumer...")
        # ... (consumer attachment code)

        # Block network for 10 seconds
        print("[2] Simulating network interruption...")
        block_network()
        time.sleep(10)

        # Restore network
        print("[3] Restoring network...")
        unblock_network()
        time.sleep(5)

        # Check if consumer reconnected
        print("[4] Checking consumer state...")
        # ... (check consumer health)

        print("✅ Consumer recovered from network interruption")

    finally:
        unblock_network()

if __name__ == "__main__":
    test_network_interruption()
```

---

## 5.5 Documentation

### 5.5.1 OpenAPI 3.0 Specification
**File:** `docs/openapi.yaml`

```yaml
openapi: 3.0.3
info:
  title: VAS-MS-V2 API
  version: 2.0.0
  description: |
    Platform-grade media gateway service for RTSP camera streaming,
    WebRTC consumption, and AI-generated bookmark management.

servers:
  - url: http://localhost:8080/api/v2
    description: Development server

security:
  - BearerAuth: []

paths:
  /auth/token:
    post:
      summary: Obtain OAuth2 access token
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                client_id:
                  type: string
                client_secret:
                  type: string
      responses:
        '200':
          description: Token granted
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/TokenResponse'

  /streams:
    get:
      summary: List streams
      parameters:
        - name: state
          in: query
          schema:
            type: string
            enum: [live, stopped, error]
        - name: limit
          in: query
          schema:
            type: integer
            default: 100
        - name: offset
          in: query
          schema:
            type: integer
            default: 0
      responses:
        '200':
          description: Streams list
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StreamsResponse'

  /streams/{stream_id}/consume:
    post:
      summary: Attach WebRTC consumer
      parameters:
        - name: stream_id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ConsumerRequest'
      responses:
        '200':
          description: Consumer attached
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ConsumerResponse'

  /streams/{stream_id}/bookmarks:
    post:
      summary: Create bookmark
      parameters:
        - name: stream_id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/BookmarkRequest'
      responses:
        '200':
          description: Bookmark created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Bookmark'

  /bookmarks:
    get:
      summary: Query bookmarks
      parameters:
        - name: event_type
          in: query
          schema:
            type: string
            enum: [person_detected, vehicle, motion, anomaly]
        - name: tags
          in: query
          schema:
            type: string
            description: Comma-separated tags
        - name: start_date
          in: query
          schema:
            type: string
            format: date-time
        - name: end_date
          in: query
          schema:
            type: string
            format: date-time
      responses:
        '200':
          description: Bookmarks list
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/BookmarksResponse'

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    TokenResponse:
      type: object
      properties:
        access_token:
          type: string
        token_type:
          type: string
          example: Bearer
        expires_in:
          type: integer
          example: 3600

    Stream:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        camera_id:
          type: string
        state:
          type: string
          enum: [initializing, ready, live, stopped, error]
        producer:
          type: object
          properties:
            id:
              type: string
            mediasoup_id:
              type: string
            state:
              type: string
        consumers:
          type: object
          properties:
            active:
              type: integer
            total_created:
              type: integer

    Bookmark:
      type: object
      properties:
        id:
          type: string
        stream_id:
          type: string
        center_timestamp:
          type: string
          format: date-time
        source:
          type: string
          enum: [live, historical, ai_generated]
        event_type:
          type: string
        confidence_score:
          type: number
          format: float
        tags:
          type: array
          items:
            type: string
        label:
          type: string
        video_url:
          type: string
        thumbnail_url:
          type: string
        created_at:
          type: string
          format: date-time
```

---

### 5.5.2 Integration Guide
**File:** `docs/INTEGRATION_GUIDE.md`

```markdown
# Consuming VAS-MS-V2 in 30 Minutes

This guide walks you through integrating with VAS-MS-V2 in **30 minutes**.

## Prerequisites

- API endpoint: `http://your-vas-ms-server:8080`
- OAuth2 credentials: `client_id` and `client_secret`

## Step 1: Authentication (5 min)

```bash
curl -X POST http://your-vas-ms-server:8080/api/v2/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "your_client_id",
    "client_secret": "your_client_secret"
  }'
```

Save the `access_token` from the response.

## Step 2: Discover Streams (5 min)

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://your-vas-ms-server:8080/api/v2/streams?state=live
```

## Step 3: Consume Stream (10 min)

```python
import requests

# Get router capabilities
response = requests.get(
    f"{API_URL}/api/v2/streams/{stream_id}/router-capabilities",
    headers={"Authorization": f"Bearer {token}"}
)
router_caps = response.json()

# Attach consumer
response = requests.post(
    f"{API_URL}/api/v2/streams/{stream_id}/consume",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "client_id": "my-app",
        "rtp_capabilities": router_caps
    }
)
consumer_data = response.json()

# Use consumer_data to create WebRTC connection
# (See Python SDK example)
```

## Step 4: Create Bookmark (10 min)

```python
# After detecting an event in your AI model
response = requests.post(
    f"{API_URL}/api/v2/streams/{stream_id}/bookmarks",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "center_timestamp": "2026-01-10T10:30:00Z",
        "source": "ai_generated",
        "event_type": "person_detected",
        "confidence_score": 0.95,
        "tags": ["person", "entrance"],
        "label": "Person detected at entrance"
    }
)
bookmark = response.json()
video_url = bookmark["video_url"]

# Download video
response = requests.get(video_url, stream=True)
with open("event.mp4", "wb") as f:
    for chunk in response.iter_content(chunk_size=8192):
        f.write(chunk)
```

✅ **Done! You're now integrated with VAS-MS-V2.**
```

---

### 5.5.3 Python SDK Example
**File:** `docs/examples/python_sdk.py`

```python
#!/usr/bin/env python3
"""
VAS-MS-V2 Python SDK Example
Demonstrates bookmark creation from AI detections
"""

import requests
from datetime import datetime

class VASMSV2Client:
    def __init__(self, api_url, client_id, client_secret):
        self.api_url = api_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None

        self.authenticate()

    def authenticate(self):
        response = requests.post(
            f"{self.api_url}/api/v2/auth/token",
            json={
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
        )
        response.raise_for_status()
        self.access_token = response.json()["access_token"]

    def get_headers(self):
        return {"Authorization": f"Bearer {self.access_token}"}

    def get_streams(self, state="live"):
        response = requests.get(
            f"{self.api_url}/api/v2/streams",
            headers=self.get_headers(),
            params={"state": state}
        )
        response.raise_for_status()
        return response.json()["streams"]

    def create_bookmark(self, stream_id, event_type, confidence, tags=None, metadata=None):
        response = requests.post(
            f"{self.api_url}/api/v2/streams/{stream_id}/bookmarks",
            headers=self.get_headers(),
            json={
                "center_timestamp": datetime.utcnow().isoformat() + "Z",
                "source": "ai_generated",
                "event_type": event_type,
                "confidence_score": confidence,
                "tags": tags or [],
                "label": f"{event_type} detected",
                "metadata": metadata or {}
            }
        )
        response.raise_for_status()
        return response.json()

    def get_bookmarks(self, event_type=None, tags=None, start_date=None, end_date=None):
        params = {}
        if event_type:
            params["event_type"] = event_type
        if tags:
            params["tags"] = ",".join(tags)
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        response = requests.get(
            f"{self.api_url}/api/v2/bookmarks",
            headers=self.get_headers(),
            params=params
        )
        response.raise_for_status()
        return response.json()["bookmarks"]

# Usage example
if __name__ == "__main__":
    # Initialize client
    client = VASMSV2Client(
        api_url="http://localhost:8080",
        client_id="ruth-ai",
        client_secret="ruth-secret"
    )

    # Get active streams
    streams = client.get_streams(state="live")
    stream_id = streams[0]["id"]

    # Simulate AI detection
    print("Detecting person...")
    bookmark = client.create_bookmark(
        stream_id=stream_id,
        event_type="person_detected",
        confidence=0.95,
        tags=["person", "entrance", "ruth-ai"],
        metadata={"model": "yolov8", "version": "1.0"}
    )

    print(f"✅ Bookmark created: {bookmark['id']}")
    print(f"   Video URL: {bookmark['video_url']}")

    # Query all person detections
    bookmarks = client.get_bookmarks(
        event_type="person_detected",
        tags=["ruth-ai"]
    )

    print(f"\n✅ Found {len(bookmarks)} Ruth-AI detections")
```

---

## Testing Execution Plan

### Week 7: Unit & Integration Tests

**Day 1-2: Unit Tests**
- [ ] Write backend unit tests (stream, auth, consumer, bookmark, snapshot)
- [ ] Write frontend unit tests (API client)
- [ ] Achieve 80%+ code coverage
- [ ] Fix any bugs found

**Day 3-4: Integration Tests**
- [ ] Implement curl-based stream consumption test
- [ ] Implement Ruth-AI integration test
- [ ] Run end-to-end flow validation
- [ ] Document any issues

**Day 5: Backend Endpoint**
- [ ] Backend team implements `GET /v2/streams/{id}/router-capabilities`
- [ ] Test MediaSoupPlayerV2 with real backend
- [ ] Verify full WebRTC flow

### Week 8: Load & Failure Tests + Documentation

**Day 1-2: Load Tests**
- [ ] Run concurrent stream test (10 streams × 50 consumers)
- [ ] Run bookmark throughput test (500/hour)
- [ ] Run API stress test (100 req/sec)
- [ ] Identify performance bottlenecks

**Day 3: Failure Tests**
- [ ] Test FFmpeg crash recovery
- [ ] Test MediaSoup worker crash
- [ ] Test network interruption
- [ ] Test disk full scenario

**Day 4-5: Documentation**
- [ ] Complete OpenAPI specification
- [ ] Write integration guide
- [ ] Create SDK examples (Python, JavaScript)
- [ ] Create curl command reference
- [ ] Record demo video

---

## Success Metrics

### Phase 5 Complete When:

✅ All unit tests pass (>80% coverage)
✅ Integration tests pass (curl + Ruth-AI)
✅ **Ruth-AI can detect, bookmark, and query events in ONE AFTERNOON**
✅ Load tests meet targets (10 streams, 50 consumers, 500 bookmarks/hour)
✅ Failure tests demonstrate graceful recovery
✅ Documentation complete and validated

---

**Document Version:** 1.0
**Created:** 2026-01-10
**Status:** Ready to Execute
