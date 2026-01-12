VAS-MS-V2 ARCHITECTURAL PROPOSAL
EXECUTIVE SUMMARY
VAS-MS-V2 transforms VAS from a tightly-coupled UI-driven streaming app into a platform-grade media gateway service that third-party applications can consume reliably via standard APIs.

Core Principle: WebRTC is a transport mechanism, not an application architecture.

1. ARCHITECTURAL VISION
1.1 Textual Architecture Diagram

┌─────────────────────────────────────────────────────────────────────┐
│                       THIRD-PARTY CONSUMERS                         │
│  (Ruth-AI, Analytics, Recorders, Mobile Apps, Browser UI)           │
└────────────┬───────────────────────────────┬────────────────────────┘
             │                               │
             │ REST API + WebRTC Signaling   │ JWT Auth
             │                               │
┌────────────▼───────────────────────────────▼────────────────────────┐
│                         VAS-MS-V2 API LAYER                         │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                   PUBLIC API SURFACE                          │  │
│  │                                                               │  │
│  │  POST   /v2/auth/token                 Get JWT                │  │
│  │  GET    /v2/streams                    List streams           │  │
│  │  POST   /v2/streams                    Create stream          │  │
│  │  GET    /v2/streams/{id}               Stream details         │  │
│  │  DELETE /v2/streams/{id}               Stop stream            │  │
│  │                                                               │  │
│  │  POST   /v2/streams/{id}/consume       Attach consumer        │  │
│  │  POST   /v2/streams/{id}/offer         WebRTC SDP offer       │  │
│  │  POST   /v2/streams/{id}/answer        WebRTC SDP answer      │  │
│  │  POST   /v2/streams/{id}/ice           ICE candidate          │  │
│  │                                                               │  │
│  │  GET    /v2/streams/{id}/hls           HLS playlist URL       │  │
│  │  GET    /v2/streams/{id}/snapshot      Capture frame          │  │
│  │  GET    /v2/streams/{id}/health        Stream health          │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                AUTHENTICATION & AUTHORIZATION                 │  │
│  │  - JWT-based auth (Bearer token)                              │  │
│  │  - Stream-scoped permissions                                  │  │
│  │  - Token expiry + refresh                                     │  │
│  │  - Rate limiting per client                                   │  │
│  └───────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                    CONTROL PLANE (State Management)                 │
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │
│  │ Stream Manager  │  │  Lifecycle FSM  │  │  Access Control │      │
│  │ (CRUD + State)  │  │  (State Machine)│  │  (Permissions)  │      │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘      │
│           │                    │                    │               │
│           └────────────────────┼────────────────────┘               │
│                                │                                    │
│  ┌─────────────────────────────▼──────────────────────────────────┐ │
│  │                      STREAM ABSTRACTION                        │ │
│  │                                                                │ │
│  │  Stream {                                                      │ │
│  │    id: UUID                                                    │ │
│  │    name: String                                                │ │
│  │    camera_id: UUID (FK → Camera)                               │ │
│  │    producer_id: UUID (FK → Producer)                           │ │
│  │    state: enum (initializing|ready|live|error|stopped)         │ │
│  │    codec_config: JSON                                          │ │
│  │    access_policy: JSON {scopes: [read, snapshot, ...]}         │ │
│  │    metadata: JSON                                              │ │
│  │    created_at, updated_at                                      │ │
│  │  }                                                             │ │
│  │                                                                │ │
│  │  Producer {                                                    │ │
│  │    id: UUID                                                    │ │
│  │    stream_id: UUID (FK → Stream)                               │ │
│  │    mediasoup_producer_id: String                               │ │
│  │    mediasoup_transport_id: String                              │ │
│  │    ssrc: Integer                                               │ │
│  │    rtp_parameters: JSON                                        │ │
│  │    state: enum (creating|active|paused|closed)                 │ │
│  │  }                                                             │ │
│  │                                                                │ │
│  │  Consumer {                                                    │ │
│  │    id: UUID                                                    │ │
│  │    stream_id: UUID (FK → Stream)                               │ │
│  │    client_id: String                                           │ │
│  │    mediasoup_consumer_id: String                               │ │
│  │    mediasoup_transport_id: String                              │ │
│  │    created_at, last_seen_at                                    │ │
│  │  }                                                             │ │
│  └────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│              DATA PLANE (BLACK BOX - DO NOT MODIFY)                 │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                   RTSP INGESTION PIPELINE                       ││
│  │                                                                 ││
│  │   Camera (RTSP) → FFmpeg → RTP → MediaSoup Producer             ││
│  │                       │                                         ││
│  │                       └──→ HLS → /recordings/hot/               ││
│  │                                                                 ││
│  │   - FFmpeg commands: STABLE (do not touch)                      ││
│  │   - SSRC capture: STABLE (do not touch)                         ││
│  │   - Codec config: STABLE (do not touch)                         ││
│  │   - MediaSoup router: STABLE (do not touch)                     ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                   MEDIASOUP SFU (Node.js)                       ││
│  │                                                                 ││
│  │   PlainRTP Transport ← FFmpeg                                   ││
│  │   WebRTC Transports → Consumers (N:1)                           ││
│  │                                                                 ││
│  │   - Worker configuration: STABLE                                ││
│  │   - Router codec capabilities: STABLE                           ││
│  │   - Transport settings: STABLE                                  ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        AUXILIARY SERVICES                           │
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │
│  │   Recording     │  │    Snapshot     │  │    Metrics      │      │
│  │   Service       │  │    Service      │  │    Service      │      │
│  │                 │  │                 │  │                 │      │
│  │ HLS Segments    │  │ JPEG Capture    │  │ Prometheus      │      │
│  │ 7-day retention │  │ Live/Historical │  │ Stream health   │      │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
2. PUBLIC API CONTRACT
2.1 Authentication
POST /v2/auth/token
Purpose: Obtain JWT access token

Request:


{
  "client_id": "ruth-ai-backend",
  "client_secret": "secret_key",
  "scopes": ["stream.read", "stream.consume", "snapshot.create"]
}
Response:


{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "refresh_token_here",
  "scopes": ["stream.read", "stream.consume", "snapshot.create"]
}
Token Payload:


{
  "sub": "ruth-ai-backend",
  "scopes": ["stream.read", "stream.consume"],
  "exp": 1704859200,
  "iat": 1704855600
}
2.2 Stream Management
GET /v2/streams
Purpose: List all available streams

Headers:


Authorization: Bearer <jwt_token>
Query Parameters:

state: Filter by state (live, ready, error)
camera_id: Filter by camera
limit, offset: Pagination
Response:


{
  "streams": [
    {
      "id": "stream-uuid-1",
      "name": "Front Door Camera",
      "camera_id": "camera-uuid-1",
      "state": "live",
      "codec": {
        "video": {
          "mimeType": "video/H264",
          "clockRate": 90000,
          "profile": "baseline"
        }
      },
      "endpoints": {
        "webrtc": "/v2/streams/stream-uuid-1/consume",
        "hls": "/v2/streams/stream-uuid-1/hls",
        "snapshot": "/v2/streams/stream-uuid-1/snapshot"
      },
      "created_at": "2026-01-08T10:00:00Z",
      "uptime_seconds": 3600
    }
  ],
  "pagination": {
    "total": 10,
    "limit": 20,
    "offset": 0
  }
}
GET /v2/streams/{stream_id}
Purpose: Get detailed stream information

Response:


{
  "id": "stream-uuid-1",
  "name": "Front Door Camera",
  "camera_id": "camera-uuid-1",
  "state": "live",
  "producer": {
    "id": "producer-uuid-1",
    "mediasoup_id": "ms-producer-abc123",
    "ssrc": 2622226488,
    "state": "active"
  },
  "codec_config": {
    "video": {
      "mimeType": "video/H264",
      "payloadType": 96,
      "clockRate": 90000,
      "parameters": {
        "packetization-mode": 1,
        "profile-level-id": "42e01f"
      }
    }
  },
  "consumers": {
    "active": 3,
    "list": [
      {
        "id": "consumer-uuid-1",
        "client_id": "ruth-ai-backend",
        "connected_at": "2026-01-08T10:30:00Z"
      }
    ]
  },
  "health": {
    "status": "healthy",
    "rtp_packets_received": 108000,
    "rtp_bytes_received": 54000000,
    "last_packet_at": "2026-01-08T11:00:00Z"
  },
  "access_policy": {
    "public": false,
    "allowed_scopes": ["stream.consume", "snapshot.create"]
  },
  "metadata": {
    "location": "Building A, Floor 1",
    "camera_model": "Hikvision DS-2CD2143G0-I"
  }
}
POST /v2/streams
Purpose: Create a new stream from a camera

Request:


{
  "name": "Parking Lot Camera",
  "camera_id": "camera-uuid-2",
  "access_policy": {
    "public": false,
    "allowed_scopes": ["stream.consume", "snapshot.create"]
  },
  "metadata": {
    "location": "Parking Lot B"
  }
}
Response:


{
  "id": "stream-uuid-2",
  "name": "Parking Lot Camera",
  "state": "initializing",
  "camera_id": "camera-uuid-2",
  "created_at": "2026-01-08T11:00:00Z"
}
State Transition:


initializing → ready → live
DELETE /v2/streams/{stream_id}
Purpose: Stop and delete a stream

Response:


{
  "id": "stream-uuid-2",
  "state": "stopped",
  "stopped_at": "2026-01-08T11:30:00Z"
}
2.3 WebRTC Consumer Attachment (THE CRITICAL API)
POST /v2/streams/{stream_id}/consume
Purpose: Attach a WebRTC consumer to a stream

Request:


{
  "client_id": "ruth-ai-backend-instance-1",
  "rtp_capabilities": {
    "codecs": [
      {
        "mimeType": "video/H264",
        "kind": "video",
        "clockRate": 90000,
        "preferredPayloadType": 96,
        "parameters": {
          "packetization-mode": 1,
          "profile-level-id": "42e01f"
        }
      }
    ],
    "headerExtensions": [...]
  }
}
Response:


{
  "consumer_id": "consumer-uuid-1",
  "transport": {
    "id": "transport-uuid-1",
    "ice_parameters": {
      "usernameFragment": "abc123",
      "password": "def456"
    },
    "ice_candidates": [
      {
        "foundation": "udpcandidate",
        "priority": 1076302079,
        "ip": "10.30.250.245",
        "port": 40123,
        "type": "host",
        "protocol": "udp"
      }
    ],
    "dtls_parameters": {
      "role": "auto",
      "fingerprints": [
        {
          "algorithm": "sha-256",
          "value": "A1:B2:C3:..."
        }
      ]
    }
  },
  "rtp_parameters": {
    "codecs": [...],
    "encodings": [{"ssrc": 2622226488}],
    "headerExtensions": [...]
  }
}
Client Flow (Headless):


// 1. Get RTP capabilities from client
const rtpCapabilities = myWebRTCClient.getRtpCapabilities();

// 2. Request consumption
const response = await fetch('/v2/streams/stream-uuid-1/consume', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer <jwt>',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    client_id: 'my-client',
    rtp_capabilities: rtpCapabilities
  })
});

const {consumer_id, transport, rtp_parameters} = await response.json();

// 3. Create local transport with ICE/DTLS params
const recvTransport = myWebRTCClient.createRecvTransport(transport);

// 4. Connect transport (send DTLS answer back)
await fetch(`/v2/streams/stream-uuid-1/connect`, {
  method: 'POST',
  body: JSON.stringify({
    consumer_id,
    dtls_parameters: recvTransport.localParameters
  })
});

// 5. Create consumer and receive track
const consumer = await recvTransport.consume({
  id: consumer_id,
  ...rtp_parameters
});

// 6. Use the track
consumer.track // MediaStreamTrack with video
POST /v2/streams/{stream_id}/connect
Purpose: Complete WebRTC transport connection (DTLS answer)

Request:


{
  "consumer_id": "consumer-uuid-1",
  "dtls_parameters": {
    "role": "client",
    "fingerprints": [
      {
        "algorithm": "sha-256",
        "value": "X1:Y2:Z3:..."
      }
    ]
  }
}
Response:


{
  "status": "connected"
}
POST /v2/streams/{stream_id}/ice
Purpose: Send ICE candidate (trickle ICE support)

Request:


{
  "consumer_id": "consumer-uuid-1",
  "candidate": {
    "foundation": "candidate1",
    "priority": 2130706431,
    "ip": "192.168.1.100",
    "port": 50123,
    "type": "host",
    "protocol": "udp"
  }
}
Response:


{
  "status": "accepted"
}
2.4 Alternative Transport Endpoints
GET /v2/streams/{stream_id}/hls
Purpose: Get HLS playlist URL for historical/live playback

Response:


{
  "hls_url": "http://10.30.250.245:8080/recordings/hot/stream-uuid-1/stream.m3u8",
  "live": true,
  "dvr_window_seconds": 604800
}
GET /v2/streams/{stream_id}/snapshot
Purpose: Capture a snapshot from the live stream

Response:


HTTP 200 OK
Content-Type: image/jpeg
Content-Length: 123456

<JPEG binary data>
GET /v2/streams/{stream_id}/health
Purpose: Get stream health metrics

Response:


{
  "status": "healthy",
  "state": "live",
  "producer": {
    "state": "active",
    "rtp_packets_received": 108000,
    "rtp_bytes_received": 54000000,
    "rtp_packet_loss": 0.01,
    "last_packet_at": "2026-01-08T11:00:00Z"
  },
  "consumers": {
    "active": 3,
    "total_created": 10
  },
  "ffmpeg": {
    "status": "running",
    "pid": 12345,
    "uptime_seconds": 3600
  },
  "recording": {
    "enabled": true,
    "disk_usage_bytes": 12000000000,
    "segment_count": 2800
  }
}
3. PRODUCER LIFECYCLE RULES (STATE MACHINE)
3.1 Stream State Machine

┌─────────────┐
│   CREATE    │  POST /v2/streams
│   REQUEST   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ INITIALIZING│  - Create DB record
│             │  - Allocate resources
└──────┬──────┘  - Start FFmpeg SSRC capture
       │
       │ SSRC captured
       ▼
┌─────────────┐
│    READY    │  - Create MediaSoup transport
│             │  - Create MediaSoup producer
└──────┬──────┘  - Start FFmpeg dual-output
       │
       │ RTP packets flowing
       ▼
┌─────────────┐
│    LIVE     │  - Producer receiving RTP
│             │  - Consumers can attach
│             │  - Recording active
└──────┬──────┘  - Health monitoring
       │
       │ Error detected OR stop requested
       ▼
┌─────────────┐
│    ERROR    │  - FFmpeg crashed
│   /STOPPED  │  - RTP timeout
│             │  - Network error
└──────┬──────┘  - Manual stop
       │
       │ Cleanup
       ▼
┌─────────────┐
│   CLOSED    │  - FFmpeg terminated
│             │  - Producer closed
│             │  - Consumers disconnected
└─────────────┘  - DB record archived
3.2 Lifecycle Rules (STRICT)
Producers are Camera-Bound and Persistent

One producer per camera/stream
Producers do NOT depend on consumer presence
Producers remain active as long as stream is in live state
Consumers are Ephemeral

Consumers can attach/detach at any time
Producer does not close when last consumer disconnects
Multiple consumers can attach to one producer concurrently
State Transitions are Audited


CREATE TABLE stream_state_transitions (
  id UUID PRIMARY KEY,
  stream_id UUID REFERENCES streams(id),
  from_state VARCHAR(20),
  to_state VARCHAR(20),
  reason TEXT,
  created_at TIMESTAMP
);
Error Recovery

If FFmpeg crashes: transition to error state, attempt restart (3 retries)
If RTP timeout (>10 seconds): transition to error, alert operators
If producer closes unexpectedly: cleanup and transition to stopped
Idempotency

POST /v2/streams with duplicate camera_id returns existing stream
DELETE /v2/streams/{id} is idempotent (returns success if already stopped)
4. MIGRATION STRATEGY (VAS-MS-V1 → V2)
4.1 Backwards Compatibility Approach
Strategy: Dual API versioning during transition period


/api/v1/*  → Legacy endpoints (maintain for 6 months)
/api/v2/*  → New architecture
4.2 Migration Phases
Phase 1: Core Infrastructure (Week 1-2)
 Create Stream, Producer, Consumer models with proper FKs
 Implement JWT authentication service
 Build stream state machine with transitions table
 Refactor RTSPPipeline to use Stream abstraction
 Add producer/consumer lifecycle tracking
Phase 2: Public API Implementation (Week 3-4)
 Implement /v2/auth/token endpoint
 Implement /v2/streams CRUD endpoints
 Implement /v2/streams/{id}/consume (WebRTC attachment)
 Implement /v2/streams/{id}/connect (DTLS answer)
 Implement /v2/streams/{id}/ice (ICE candidates)
 Implement /v2/streams/{id}/hls proxy
 Implement /v2/streams/{id}/snapshot proxy
Phase 3: Data Plane Wrapping (Week 5)
 Wrap existing FFmpeg commands in StreamIngestionService
 Wrap MediaSoup client in ProducerService
 Add health monitoring and metrics
 Add consumer session management
Phase 4: UI Refactoring (Week 6)
 Update frontend to use /v2/streams API
 Remove direct MediaSoup WebSocket connection
 Use new consumer attachment flow
 Add JWT token management
Phase 5: Testing & Validation (Week 7-8)
 End-to-end test: curl-based stream consumption
 Load test: multiple concurrent consumers
 Failure test: FFmpeg crash recovery
 Integration test: Ruth-AI consumption
 Documentation and SDK examples
Phase 6: Deprecation (Month 3+)
 Mark /api/v1/* as deprecated
 Migrate all internal clients to V2
 Remove legacy endpoints after grace period
4.3 Database Migration
New Tables

-- Streams (refactored)
CREATE TABLE streams (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
  producer_id UUID REFERENCES producers(id) ON DELETE SET NULL,
  state VARCHAR(20) NOT NULL DEFAULT 'initializing',
    -- States: initializing, ready, live, error, stopped, closed
  codec_config JSONB NOT NULL DEFAULT '{}',
  access_policy JSONB NOT NULL DEFAULT '{}',
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  
  CONSTRAINT valid_state CHECK (state IN (
    'initializing', 'ready', 'live', 'error', 'stopped', 'closed'
  ))
);

CREATE INDEX idx_streams_camera_id ON streams(camera_id);
CREATE INDEX idx_streams_state ON streams(state);

-- Producers (new)
CREATE TABLE producers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  stream_id UUID NOT NULL REFERENCES streams(id) ON DELETE CASCADE,
  mediasoup_producer_id VARCHAR(255) UNIQUE NOT NULL,
  mediasoup_transport_id VARCHAR(255) NOT NULL,
  ssrc BIGINT NOT NULL,
  rtp_parameters JSONB NOT NULL,
  state VARCHAR(20) NOT NULL DEFAULT 'creating',
    -- States: creating, active, paused, closed
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  
  CONSTRAINT valid_producer_state CHECK (state IN (
    'creating', 'active', 'paused', 'closed'
  ))
);

CREATE INDEX idx_producers_stream_id ON producers(stream_id);
CREATE INDEX idx_producers_mediasoup_id ON producers(mediasoup_producer_id);

-- Consumers (new)
CREATE TABLE consumers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  stream_id UUID NOT NULL REFERENCES streams(id) ON DELETE CASCADE,
  client_id VARCHAR(255) NOT NULL,
  mediasoup_consumer_id VARCHAR(255) UNIQUE NOT NULL,
  mediasoup_transport_id VARCHAR(255) NOT NULL,
  state VARCHAR(20) NOT NULL DEFAULT 'connecting',
    -- States: connecting, connected, paused, closed
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
  closed_at TIMESTAMP,
  
  CONSTRAINT valid_consumer_state CHECK (state IN (
    'connecting', 'connected', 'paused', 'closed'
  ))
);

CREATE INDEX idx_consumers_stream_id ON consumers(stream_id);
CREATE INDEX idx_consumers_client_id ON consumers(client_id);

-- State Transitions (audit log)
CREATE TABLE stream_state_transitions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  stream_id UUID NOT NULL REFERENCES streams(id) ON DELETE CASCADE,
  from_state VARCHAR(20),
  to_state VARCHAR(20) NOT NULL,
  reason TEXT,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_transitions_stream_id ON stream_state_transitions(stream_id);
CREATE INDEX idx_transitions_created_at ON stream_state_transitions(created_at);

-- Rename devices → cameras (clarity)
ALTER TABLE devices RENAME TO cameras;

-- Update foreign keys
ALTER TABLE snapshots RENAME COLUMN device_id TO camera_id;
ALTER TABLE bookmarks RENAME COLUMN device_id TO camera_id;
5. ANTI-PATTERNS (MUST NOT REINTRODUCE)
❌ Anti-Pattern 1: UI-Dependent Stream Lifecycle

# BAD: Stream stops when user navigates away
@websocket.on_disconnect
async def handle_disconnect(websocket):
    await stop_stream(websocket.stream_id)  # ❌ WRONG
Correct:


# GOOD: Streams persist independent of UI
# Consumers close on disconnect, producers remain active
@websocket.on_disconnect
async def handle_disconnect(websocket):
    await close_consumer(websocket.consumer_id)  # ✅ CORRECT
❌ Anti-Pattern 2: Hidden Signaling

# BAD: Signaling logic embedded in frontend component
class MediaSoupPlayer:
    async def connect(self):
        # Direct WebSocket to MediaSoup ❌
        ws = await websocket.connect("ws://mediasoup:3001")
Correct:


# GOOD: Explicit API-driven signaling
response = await api.post(f"/v2/streams/{stream_id}/consume", {
    "rtp_capabilities": device.rtpCapabilities
})
transport_params = response.json()
❌ Anti-Pattern 3: Single Consumer Assumption

# BAD: Only one consumer per stream
class Stream:
    consumer_id: Optional[UUID]  # ❌ Assumes 1:1
Correct:


# GOOD: N consumers per stream
class Stream:
    consumers: List[Consumer]  # ✅ One-to-many
❌ Anti-Pattern 4: String-Based Relationships

# BAD: Loose coupling
class Stream(Base):
    producer_id = Column(String)  # ❌ No FK constraint
Correct:


# GOOD: Proper foreign keys
class Stream(Base):
    producer_id = Column(UUID, ForeignKey('producers.id'))  # ✅
    producer = relationship("Producer", back_populates="stream")
❌ Anti-Pattern 5: Tight Coupling to MediaSoup Internals

# BAD: Frontend imports mediasoup-client directly
import * as mediasoup from 'mediasoup-client';
Correct:


# GOOD: Abstract behind VAS API
class VASClient:
    async def consume_stream(self, stream_id):
        # Handles all MediaSoup complexity internally
6. SUCCESS CRITERION VALIDATION
Test Case: Third-Party Integration in One Afternoon
Scenario: Ruth-AI engineer integrates VAS-MS-V2

Steps:

Read API documentation (30 minutes)
Obtain JWT token via /v2/auth/token (5 minutes)
List available streams via /v2/streams (5 minutes)
Attach consumer via /v2/streams/{id}/consume (20 minutes)
Implement WebRTC transport connection (40 minutes)
Receive and process video track (20 minutes)
Add reconnection logic (20 minutes)
Test with multiple streams (20 minutes)
Total: ~3 hours (within ONE AFTERNOON requirement)

Requirements Met:

✅ Authentication clear and documented
✅ Stream discovery via API
✅ WebRTC attachment explicit
✅ Reconnection supported
✅ No UI interaction required
✅ No VAS source code reading required
7. IMPLEMENTATION ROADMAP
7.1 File Structure (Proposed)

backend/
├── app/
│   ├── api/
│   │   └── v2/
│   │       ├── auth.py              # JWT authentication
│   │       ├── streams.py           # Stream CRUD + consumption
│   │       ├── cameras.py           # Camera management
│   │       └── health.py            # Health checks
│   ├── models/
│   │   ├── stream.py                # Stream, Producer, Consumer
│   │   ├── camera.py                # Camera (renamed from Device)
│   │   ├── auth.py                  # JWT tokens, API keys
│   │   └── audit.py                 # State transitions
│   ├── services/
│   │   ├── stream_manager.py        # Stream lifecycle FSM
│   │   ├── producer_service.py      # Producer creation/cleanup
│   │   ├── consumer_service.py      # Consumer attachment
│   │   ├── auth_service.py          # JWT generation/validation
│   │   ├── rtsp_pipeline.py         # EXISTING (wrap only)
│   │   └── mediasoup_client.py      # EXISTING (wrap only)
│   ├── schemas/
│   │   └── v2/
│   │       ├── stream.py            # Pydantic schemas
│   │       ├── consumer.py
│   │       └── auth.py
│   └── middleware/
│       └── jwt_auth.py              # JWT validation middleware
7.2 Key Service Interfaces
StreamManager (Control Plane)

class StreamManager:
    async def create_stream(
        self, 
        camera_id: UUID, 
        name: str,
        access_policy: dict,
        metadata: dict
    ) -> Stream:
        """
        Create a new stream from a camera.
        
        State: initializing → ready → live
        """
        
    async def start_stream(self, stream_id: UUID) -> Stream:
        """
        Transition stream from ready → live.
        
        Steps:
        1. Capture SSRC (via RTSPPipeline)
        2. Create MediaSoup producer (via ProducerService)
        3. Start FFmpeg dual-output (via RTSPPipeline)
        4. Transition to 'live' state
        """
        
    async def stop_stream(self, stream_id: UUID) -> Stream:
        """
        Transition stream to stopped state.
        
        Steps:
        1. Close all consumers
        2. Stop FFmpeg
        3. Close producer
        4. Transition to 'stopped' state
        """
        
    async def get_stream(self, stream_id: UUID) -> Stream:
        """Get stream with eager-loaded relationships."""
        
    async def list_streams(
        self, 
        state: Optional[str] = None,
        camera_id: Optional[UUID] = None
    ) -> List[Stream]:
        """List streams with filters."""
ConsumerService (Control Plane)

class ConsumerService:
    async def attach_consumer(
        self,
        stream_id: UUID,
        client_id: str,
        rtp_capabilities: dict
    ) -> ConsumerInfo:
        """
        Attach a WebRTC consumer to a stream.
        
        Returns transport parameters and RTP parameters.
        """
        
    async def connect_consumer_transport(
        self,
        consumer_id: UUID,
        dtls_parameters: dict
    ):
        """Complete DTLS handshake."""
        
    async def add_ice_candidate(
        self,
        consumer_id: UUID,
        candidate: dict
    ):
        """Add ICE candidate (trickle ICE)."""
        
    async def close_consumer(self, consumer_id: UUID):
        """Cleanup consumer resources."""
ProducerService (Data Plane Wrapper)

class ProducerService:
    async def create_producer(
        self,
        stream_id: UUID,
        rtsp_url: str
    ) -> Producer:
        """
        Create MediaSoup producer for stream.
        
        Wraps:
        - RTSPPipeline.capture_ssrc_with_temp_ffmpeg()
        - MediaSoupClient.create_plain_rtp_transport()
        - MediaSoupClient.create_producer()
        
        Returns Producer model.
        """
        
    async def close_producer(self, producer_id: UUID):
        """
        Close producer and cleanup transport.
        
        Wraps:
        - MediaSoupClient.close_producer()
        """
8. QUALITY ASSURANCE
8.1 Testing Requirements
Unit Tests
Stream state machine transitions
JWT token generation/validation
Consumer attachment flow
Producer lifecycle
Integration Tests
End-to-end stream creation → consumption
Multiple consumers per stream
Consumer disconnect/reconnect
FFmpeg crash recovery
Load Tests
10 concurrent streams
50 concurrent consumers
100 requests/second to API
Failure Tests
FFmpeg crash during live stream
Network interruption
MediaSoup worker crash
Database connection loss
8.2 Monitoring & Observability
Metrics (Prometheus)

vas_streams_total{state="live|error|stopped"}
vas_producers_total{state="active|closed"}
vas_consumers_total{state="connected|closed"}
vas_stream_uptime_seconds{stream_id}
vas_rtp_packets_received_total{stream_id}
vas_rtp_packet_loss_ratio{stream_id}
vas_consumer_attach_duration_seconds
vas_api_request_duration_seconds{endpoint, method}
Health Checks

GET /v2/health
{
  "status": "healthy",
  "components": {
    "database": "healthy",
    "redis": "healthy",
    "mediasoup": "healthy",
    "ffmpeg": "healthy"
  },
  "streams": {
    "live": 10,
    "error": 0
  }
}
9. DOCUMENTATION DELIVERABLES
9.1 API Documentation (OpenAPI 3.0)
Complete endpoint specifications
Request/response schemas
Authentication flow
Error codes
9.2 Integration Guide
"Consuming VAS-MS-V2 in 30 Minutes"
curl examples
Python SDK example
JavaScript SDK example
Common pitfalls
9.3 Architecture Document
System architecture diagram
State machine diagrams
Sequence diagrams
Failure scenarios
10. FINAL ARCHITECTURE REVIEW
Design Principles Validated
✅ Control Plane ≠ Data Plane

Control: Stream CRUD, consumer attachment, signaling
Data: RTSP ingestion, FFmpeg, MediaSoup (black box)
✅ Producers are Camera-Bound and Persistent

One producer per stream
Independent of consumer presence
✅ VAS is Consumer-Agnostic

No UI-specific logic
Standard WebRTC APIs
✅ WebRTC is a Transport

Explicit signaling via REST
No hidden state
✅ Machine-First Authentication

JWT tokens
Stream-scoped permissions
✅ User-Friendly

curl-consumable
Predictable errors
No hidden state
✅ Boring and Predictable

State machines with transitions
Explicit error handling
Auditable
11. APPROVAL GATE
Before proceeding to implementation, confirm:

Architecture is clear and unambiguous ✅
Public API contract is complete ✅
Producer lifecycle rules are explicit ✅
Migration strategy is defined ✅
Anti-patterns are documented ✅
Success criterion is testable ✅
Black box components identified ✅
Third-party consumability validated ✅
READY FOR IMPLEMENTATION
This architecture transforms VAS-MS from a tightly-coupled UI application into a platform-grade media gateway service that Ruth-AI and other third-party applications can consume reliably.

Next Step: Approval to begin Phase 1 implementation (Core Infrastructure).

Do you approve this architecture? Any clarifications or changes required before I begin implementation?

UPDATED SECTION: BOOKMARKS & SNAPSHOTS AS MEDIA ANNOTATIONS
Critical Insight: Bookmarks Are Event Markers
Bookmarks represent temporal annotations on streams - they mark "events of interest" that third-party applications (like Ruth-AI) need to:

Create programmatically (e.g., "AI detected a person")
Retrieve for review
Export for training datasets
Search and filter
This is NOT just a UI convenience - it's a core platform capability.

Updated Architecture: Media Annotations Layer

┌─────────────────────────────────────────────────────────────────────┐
│                    VAS-MS-V2 ARCHITECTURE (UPDATED)                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                       PUBLIC API SURFACE                            │
│                                                                     │
│  STREAM MANAGEMENT                                                  │
│  ├─ POST   /v2/streams                                              │
│  ├─ GET    /v2/streams/{id}/consume                                 │
│  └─ ...                                                             │
│                                                                     │
│  MEDIA ANNOTATIONS (NEW)                                            │
│  ├─ POST   /v2/streams/{id}/bookmarks      Create bookmark          │
│  ├─ GET    /v2/streams/{id}/bookmarks      List bookmarks           │
│  ├─ GET    /v2/bookmarks/{id}              Get bookmark             │
│  ├─ GET    /v2/bookmarks/{id}/video        Download 6s clip         │
│  ├─ GET    /v2/bookmarks/{id}/thumbnail    Get thumbnail            │
│  ├─ PUT    /v2/bookmarks/{id}              Update metadata          │
│  ├─ DELETE /v2/bookmarks/{id}              Delete bookmark          │
│  │                                                                  │
│  ├─ POST   /v2/streams/{id}/snapshots      Create snapshot          │
│  ├─ GET    /v2/streams/{id}/snapshots      List snapshots           │
│  ├─ GET    /v2/snapshots/{id}              Get snapshot             │
│  └─ GET    /v2/snapshots/{id}/image        Download image           │
└─────────────────────────────────────────────────────────────────────┘
Updated Data Models
Bookmark Model (Enhanced)

class Bookmark(Base):
    """
    Represents a temporal annotation on a stream - a 6-second video clip
    marking an event of interest.
    
    Use cases:
    - AI event detection (person detected, anomaly detected)
    - Manual user annotations
    - Training dataset generation
    - Incident review
    """
    __tablename__ = "bookmarks"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    stream_id = Column(UUID, ForeignKey('streams.id'), nullable=False)  # ✅ Changed
    
    # Temporal bounds
    center_timestamp = Column(DateTime(timezone=True), nullable=False)
    start_timestamp = Column(DateTime(timezone=True), nullable=False)   # center - 3s
    end_timestamp = Column(DateTime(timezone=True), nullable=False)     # center + 3s
    
    # Files
    video_file_path = Column(String(512), nullable=False)
    thumbnail_path = Column(String(512), nullable=True)
    
    # Metadata (machine-readable)
    label = Column(String(255), nullable=True)           # "Person detected"
    source = Column(String(20), nullable=False)          # 'live' | 'historical'
    created_by = Column(String(100), nullable=True)      # "ruth-ai" | "manual"
    confidence = Column(Float, nullable=True)            # AI confidence (0.0-1.0)
    event_type = Column(String(50), nullable=True)       # "person" | "vehicle" | "anomaly"
    tags = Column(JSONB, default=[])                     # ["security", "urgent"]
    
    # Technical metadata
    duration = Column(Integer, default=6)
    video_format = Column(String(10), default="mp4")
    file_size = Column(Integer, nullable=True)
    
    # Extended metadata (flexible)
    metadata = Column(JSONB, default={})                 # AI bounding boxes, etc.
    
    # Relationships
    stream = relationship("Stream", back_populates="bookmarks")
    
    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
Snapshot Model (Enhanced)

class Snapshot(Base):
    """
    Represents a single-frame capture from a stream.
    
    Use cases:
    - Thumbnail generation
    - Quick visual verification
    - Lower bandwidth than bookmarks
    """
    __tablename__ = "snapshots"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    stream_id = Column(UUID, ForeignKey('streams.id'), nullable=False)  # ✅ Changed
    
    # Temporal
    timestamp = Column(DateTime(timezone=True), nullable=False)
    
    # Files
    file_path = Column(String(512), nullable=False)
    
    # Metadata
    source = Column(String(20), nullable=False)          # 'live' | 'historical'
    created_by = Column(String(100), nullable=True)      # "ruth-ai" | "manual"
    format = Column(String(10), default="jpg")
    file_size = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    
    # Extended metadata
    metadata = Column(JSONB, default={})
    
    # Relationships
    stream = relationship("Stream", back_populates="snapshots")
    
    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
Stream Model (Updated)

class Stream(Base):
    __tablename__ = "streams"
    
    # ... existing fields ...
    
    # Relationships (NEW)
    bookmarks = relationship("Bookmark", back_populates="stream", cascade="all, delete-orphan")
    snapshots = relationship("Snapshot", back_populates="stream", cascade="all, delete-orphan")
Updated Public API: Media Annotations
Bookmarks API
POST /v2/streams/{stream_id}/bookmarks
Purpose: Create a bookmark from current live stream or historical timestamp

Request (Live):


{
  "source": "live",
  "label": "Person detected at front door",
  "created_by": "ruth-ai",
  "event_type": "person",
  "confidence": 0.95,
  "tags": ["security", "person-detection"],
  "metadata": {
    "bounding_box": {"x": 100, "y": 200, "w": 50, "h": 100},
    "ai_model": "yolov8",
    "detection_id": "det-12345"
  }
}
Request (Historical):


{
  "source": "historical",
  "center_timestamp": "2026-01-08T14:23:45Z",
  "label": "Review incident",
  "created_by": "operator-john",
  "event_type": "incident",
  "tags": ["review"]
}
Response:


{
  "id": "bookmark-uuid-1",
  "stream_id": "stream-uuid-1",
  "center_timestamp": "2026-01-08T14:23:45Z",
  "start_timestamp": "2026-01-08T14:23:42Z",
  "end_timestamp": "2026-01-08T14:23:48Z",
  "label": "Person detected at front door",
  "source": "live",
  "created_by": "ruth-ai",
  "event_type": "person",
  "confidence": 0.95,
  "tags": ["security", "person-detection"],
  "duration": 6,
  "video_format": "mp4",
  "file_size": 1248576,
  "video_url": "/v2/bookmarks/bookmark-uuid-1/video",
  "thumbnail_url": "/v2/bookmarks/bookmark-uuid-1/thumbnail",
  "metadata": {
    "bounding_box": {"x": 100, "y": 200, "w": 50, "h": 100},
    "ai_model": "yolov8",
    "detection_id": "det-12345"
  },
  "created_at": "2026-01-08T14:23:45Z"
}
GET /v2/streams/{stream_id}/bookmarks
Purpose: List bookmarks for a stream with filtering

Query Parameters:

event_type: Filter by event type (person, vehicle, anomaly)
created_by: Filter by creator (ruth-ai, manual)
tags: Filter by tags (comma-separated)
start_time: Filter by time range start (ISO 8601)
end_time: Filter by time range end
limit, offset: Pagination
Response:


{
  "bookmarks": [
    {
      "id": "bookmark-uuid-1",
      "center_timestamp": "2026-01-08T14:23:45Z",
      "label": "Person detected",
      "event_type": "person",
      "confidence": 0.95,
      "tags": ["security"],
      "video_url": "/v2/bookmarks/bookmark-uuid-1/video",
      "thumbnail_url": "/v2/bookmarks/bookmark-uuid-1/thumbnail"
    }
  ],
  "pagination": {
    "total": 50,
    "limit": 20,
    "offset": 0
  }
}
GET /v2/bookmarks/{bookmark_id}/video
Purpose: Download the 6-second video clip

Response:


HTTP 200 OK
Content-Type: video/mp4
Content-Length: 1248576
Content-Disposition: attachment; filename="bookmark_2026-01-08_14-23-45.mp4"

<MP4 binary data>
Snapshots API
POST /v2/streams/{stream_id}/snapshots
Purpose: Capture a single frame from stream

Request (Live):


{
  "source": "live",
  "created_by": "ruth-ai",
  "metadata": {
    "frame_analysis": "No anomalies detected"
  }
}
Request (Historical):


{
  "source": "historical",
  "timestamp": "2026-01-08T14:23:45Z",
  "created_by": "operator-john"
}
Response:


{
  "id": "snapshot-uuid-1",
  "stream_id": "stream-uuid-1",
  "timestamp": "2026-01-08T14:23:45Z",
  "source": "live",
  "created_by": "ruth-ai",
  "format": "jpg",
  "file_size": 245678,
  "width": 1920,
  "height": 1080,
  "image_url": "/v2/snapshots/snapshot-uuid-1/image",
  "metadata": {
    "frame_analysis": "No anomalies detected"
  },
  "created_at": "2026-01-08T14:23:45Z"
}
Use Case: Ruth-AI Integration
Scenario: AI Event Detection

# Ruth-AI detects a person in the video stream
class RuthAIVideoAnalyzer:
    async def on_person_detected(self, stream_id: str, detection: Detection):
        """Called when AI detects a person."""
        
        # Create bookmark immediately (captures last 6 seconds)
        response = await vas_client.create_bookmark(
            stream_id=stream_id,
            data={
                "source": "live",
                "label": f"Person detected: {detection.label}",
                "created_by": "ruth-ai",
                "event_type": "person",
                "confidence": detection.confidence,
                "tags": ["ai-detection", "person", "security"],
                "metadata": {
                    "bounding_box": detection.bbox.to_dict(),
                    "ai_model": "yolov8-person-detection-v2",
                    "detection_id": detection.id,
                    "pose": detection.pose
                }
            }
        )
        
        bookmark_id = response["id"]
        
        # Later: Download for training dataset
        video_data = await vas_client.download_bookmark_video(bookmark_id)
        await training_dataset.add_sample(video_data, detection.label)
Architecture Benefits
1. Stream-Scoped Annotations
Bookmarks/snapshots are tied to streams, not devices
Allows multiple streams per camera with separate annotations
Clean cascade deletion: delete stream → delete all bookmarks
2. Machine-First Design
created_by field tracks automation vs manual
confidence field for AI-generated bookmarks
event_type for programmatic filtering
metadata JSON field for extensibility
3. Third-Party Consumability
Ruth-AI can create bookmarks via API
Search/filter bookmarks by event type, tags, time range
Download video clips for training datasets
No UI dependency
4. Temporal Indexing
Bookmarks serve as temporal index into recordings
"Show me all person detections on stream X between 2-4 PM"
Export bookmarks as training data: GET /v2/streams/{id}/bookmarks?event_type=person&start_time=...
Updated Database Migration

-- Update bookmarks table
ALTER TABLE bookmarks 
  DROP COLUMN device_id,
  ADD COLUMN stream_id UUID NOT NULL REFERENCES streams(id) ON DELETE CASCADE,
  ADD COLUMN created_by VARCHAR(100),
  ADD COLUMN confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
  ADD COLUMN event_type VARCHAR(50),
  ADD COLUMN tags JSONB DEFAULT '[]',
  ADD COLUMN metadata JSONB DEFAULT '{}';

CREATE INDEX idx_bookmarks_stream_id ON bookmarks(stream_id);
CREATE INDEX idx_bookmarks_event_type ON bookmarks(event_type);
CREATE INDEX idx_bookmarks_created_by ON bookmarks(created_by);
CREATE INDEX idx_bookmarks_center_timestamp ON bookmarks(center_timestamp);
CREATE INDEX idx_bookmarks_tags ON bookmarks USING GIN(tags);

-- Update snapshots table
ALTER TABLE snapshots
  DROP COLUMN device_id,
  ADD COLUMN stream_id UUID NOT NULL REFERENCES streams(id) ON DELETE CASCADE,
  ADD COLUMN created_by VARCHAR(100),
  ADD COLUMN width INTEGER,
  ADD COLUMN height INTEGER,
  ADD COLUMN metadata JSONB DEFAULT '{}';

CREATE INDEX idx_snapshots_stream_id ON snapshots(stream_id);
CREATE INDEX idx_snapshots_timestamp ON snapshots(timestamp);
CREATE INDEX idx_snapshots_created_by ON snapshots(created_by);
Anti-Pattern to Avoid
❌ Device-Scoped Annotations (Current)

# BAD: Tied to device, not stream
POST /v1/devices/{device_id}/capture/live
Problem: If you have multiple streams per camera (different resolutions, different consumers), annotations are ambiguous.

✅ Stream-Scoped Annotations (V2)

# GOOD: Tied to stream
POST /v2/streams/{stream_id}/bookmarks
Benefit: Clear which stream the bookmark came from, supports multi-stream scenarios.

Implementation Priority
Phase 2.5: Media Annotations (NEW)
After Core Streams API, Before UI Refactoring

 Migrate Bookmark model: device_id → stream_id
 Migrate Snapshot model: device_id → stream_id
 Add created_by, event_type, confidence, tags fields
 Implement POST /v2/streams/{id}/bookmarks endpoint
 Implement GET /v2/streams/{id}/bookmarks with filtering
 Implement POST /v2/streams/{id}/snapshots endpoint
 Add search/filter capabilities (by event_type, tags, time range)
 Update BookmarkService to accept stream_id instead of device_id
 Add validation: ensure stream is in 'live' state for live bookmarks
 Add retention policy: auto-delete bookmarks older than X days (configurable)
Updated Success Criterion
Extended Test Case: Ruth-AI Event Detection

Ruth-AI authenticates via /v2/auth/token ✅
Ruth-AI subscribes to stream via /v2/streams/{id}/consume ✅
Ruth-AI detects person in video frame
Ruth-AI creates bookmark via /v2/streams/{id}/bookmarks ⭐ NEW
Ruth-AI queries bookmarks via /v2/streams/{id}/bookmarks?event_type=person
Ruth-AI downloads video clips for training dataset
Ruth-AI creates snapshots for thumbnails
Time to complete: ONE AFTERNOON (including bookmark integration)

Summary
By elevating bookmarks and snapshots to first-class stream annotations, VAS-MS-V2 becomes a true media intelligence platform that:

✅ Supports AI-driven event detection (Ruth-AI use case)
✅ Enables programmatic annotation creation
✅ Provides temporal indexing into recordings
✅ Exports training datasets
✅ Maintains clean separation: streams own annotations
This is NOT just a UI feature - it's a core platform capability for third-party consumption.

Does this updated architecture properly address the bookmarking feature? Any other critical features I should consider?


REVISED PHASED APPROACH FOR VAS-MS-V2
Key Changes from Original Plan
Original Issue: Media annotations (bookmarks/snapshots) were mentioned only as "proxy" endpoints in Phase 2, treating them as afterthoughts.

Updated Strategy: Elevate media annotations to first-class citizens with proper stream-scoped data modeling and API design. This is critical because:

Ruth-AI needs bookmarks for event detection - core use case
Training dataset generation depends on programmatic bookmark creation
Stream-scoped annotations are cleaner than device-scoped (current V1)
UPDATED MIGRATION PHASES
Phase 1: Core Infrastructure (Week 1-2)
Focus: Foundation - Database models, state machines, authentication

Deliverables:

 Create Stream, Producer, Consumer models with proper foreign keys
 NEW: Migrate Bookmark model: device_id → stream_id, add created_by, event_type, confidence, tags, metadata
 NEW: Migrate Snapshot model: device_id → stream_id, add created_by, metadata
 Create StreamStateTransition audit table
 Implement JWT authentication service (token generation, validation, refresh)
 Build stream state machine (FSM) with transition validation
 Refactor RTSPPipeline to use Stream abstraction instead of Device
 Add producer/consumer lifecycle tracking in database
Database Migrations:


-- New tables: streams, producers, consumers, stream_state_transitions
-- Updated tables: bookmarks (device_id→stream_id + new fields), snapshots (device_id→stream_id)
-- Indexes: stream_id, event_type, tags (GIN), timestamps
Why This Changes: We're doing the bookmark/snapshot migration upfront in Phase 1 instead of deferring it. This prevents having to migrate twice (once for device→camera rename, again for device→stream).

Phase 2: Public API Implementation (Week 3-4)
Focus: REST API endpoints for streams and WebRTC consumption

Deliverables:

 Implement POST /v2/auth/token (JWT authentication)
 Implement GET /v2/streams (list streams with filtering)
 Implement POST /v2/streams (create stream from camera)
 Implement GET /v2/streams/{id} (stream details with health)
 Implement DELETE /v2/streams/{id} (stop stream)
 Implement POST /v2/streams/{id}/consume (WebRTC consumer attachment) ⭐ CRITICAL
 Implement POST /v2/streams/{id}/connect (DTLS answer)
 Implement POST /v2/streams/{id}/ice (ICE candidate handling)
 Implement GET /v2/streams/{id}/hls (HLS playlist proxy)
 Implement GET /v2/streams/{id}/health (stream health metrics)
NOT in this phase: Bookmark/snapshot endpoints (moved to Phase 2.5)

Phase 2.5: Media Annotations API (Week 4.5) ⭐ NEW PHASE
Focus: Bookmarks and snapshots as first-class stream annotations

Deliverables:

 Implement POST /v2/streams/{id}/bookmarks (create bookmark - live or historical)
 Implement GET /v2/streams/{id}/bookmarks (list bookmarks with filtering by event_type, tags, created_by, time range)
 Implement GET /v2/bookmarks/{id} (get bookmark details)
 Implement GET /v2/bookmarks/{id}/video (download 6-second clip)
 Implement GET /v2/bookmarks/{id}/thumbnail (get thumbnail image)
 Implement PUT /v2/bookmarks/{id} (update label/metadata)
 Implement DELETE /v2/bookmarks/{id} (delete bookmark and files)
 Implement POST /v2/streams/{id}/snapshots (create snapshot - live or historical)
 Implement GET /v2/streams/{id}/snapshots (list snapshots)
 Implement GET /v2/snapshots/{id} (get snapshot details)
 Implement GET /v2/snapshots/{id}/image (download image)
 Implement DELETE /v2/snapshots/{id} (delete snapshot)
Service Updates:

 Update BookmarkService.capture_from_live_stream() to accept stream_id instead of device_id
 Update BookmarkService.capture_from_historical() to use stream_id
 Update SnapshotService similarly
 Add validation: ensure stream is in live state for live captures
 Add retention policy background task (configurable auto-delete)
Why This Is Critical:

Ruth-AI integration depends on programmatic bookmark creation
This must be ready before Ruth-AI starts testing (Phase 5)
Adding it after Phase 6 would break the success criterion

Phase 3: Data Plane Wrapping (Week 5)
Focus: Wrap existing stable components without modifying them

Deliverables:

 Create StreamIngestionService that wraps existing FFmpeg commands
 Create ProducerService that wraps MediaSoupClient
 Create ConsumerService for consumer lifecycle management
 Add health monitoring (FFmpeg process health, RTP packet stats)
 Add Prometheus metrics export
 Implement consumer session management (heartbeat, timeout, cleanup)
 Add recording management (7-day retention, disk usage monitoring)
Black Box Principle:

✅ Do NOT modify FFmpeg commands
✅ Do NOT modify MediaSoup codec configurations
✅ Do NOT modify SSRC capture logic
✅ Only wrap and orchestrate

Phase 4: UI Refactoring (Week 6)
Focus: Update frontend to use V2 API exclusively

Deliverables:

 Update frontend to call GET /v2/streams instead of GET /v1/devices
 Remove direct MediaSoup WebSocket connection (ws://mediasoup:3001)
 Use new consumer attachment flow (POST /v2/streams/{id}/consume)
 Implement JWT token management (storage, refresh, expiry handling)
 Update bookmark UI to use POST /v2/streams/{id}/bookmarks
 Update snapshot UI to use POST /v2/streams/{id}/snapshots
 Add bookmark filtering UI (by event_type, tags, time range)
 Add visual indicators for AI-generated bookmarks vs manual bookmarks
UI Components Updated:

MediaSoupPlayer → Use V2 signaling API
BookmarkCapture → Use V2 bookmark API
SnapshotCapture → Use V2 snapshot API
StreamList → Use V2 streams API

Phase 5: Testing & Validation (Week 7-8)
Focus: End-to-end validation with third-party consumers

Deliverables:

5.1 Unit Tests
 Stream state machine transitions
 JWT token generation/validation/refresh
 Consumer attachment flow
 Bookmark creation (live & historical)
 Snapshot creation (live & historical)
5.2 Integration Tests
 curl-based stream consumption (no UI required)


# Authenticate
curl -X POST /v2/auth/token -d '{"client_id":"test","client_secret":"secret"}'

# List streams
curl -H "Authorization: Bearer <token>" /v2/streams

# Attach consumer
curl -X POST -H "Authorization: Bearer <token>" \
  /v2/streams/{id}/consume -d '{"client_id":"test","rtp_capabilities":{...}}'

# Create bookmark
curl -X POST -H "Authorization: Bearer <token>" \
  /v2/streams/{id}/bookmarks -d '{"source":"live","label":"Test event"}'
 Ruth-AI integration test ⭐ CRITICAL SUCCESS CRITERION

Ruth-AI authenticates
Ruth-AI consumes stream
Ruth-AI detects event (person detection)
Ruth-AI creates bookmark programmatically
Ruth-AI queries bookmarks by event_type=person
Ruth-AI downloads bookmark video for training dataset
Total time: ONE AFTERNOON
5.3 Load Tests
 10 concurrent streams
 50 concurrent consumers
 100 requests/second to API
 500 bookmark creations/hour
5.4 Failure Tests
 FFmpeg crash during live stream (auto-restart with retry limit)
 MediaSoup worker crash
 Network interruption (ICE disconnect/reconnect)
 Database connection loss (graceful degradation)
 Disk full during bookmark capture
5.5 Documentation
 OpenAPI 3.0 specification
 Integration guide: "Consuming VAS-MS-V2 in 30 Minutes"
 Python SDK example (with bookmark creation)
 JavaScript SDK example
 curl command reference

Phase 6: Deprecation & Migration (Month 3+)
Focus: Sunset V1 API

Deliverables:

 Mark /api/v1/* endpoints as deprecated (add Deprecation header)
 Send migration notices to existing API consumers
 Migrate internal tools to V2 API
 Monitor V1 usage (log requests, track consumers)
 After 3 months grace period: remove V1 endpoints
 Clean up legacy code (devices → cameras, old bookmark/snapshot routes)
Migration Support:

Provide migration script for existing bookmarks/snapshots (device_id → stream_id mapping)
Offer compatibility layer for 3-month transition period
What Changed (Summary)
Aspect	Original Plan	Updated Plan
Bookmarks/Snapshots	"Proxy endpoints" in Phase 2	Full migration in Phase 1, API in Phase 2.5
Data Model	Not specified	Stream-scoped with AI metadata fields
Ruth-AI Integration	Generic "integration test"	Explicit bookmark creation requirement
Timeline	6 phases, ~8 weeks	6 phases + Phase 2.5, ~8.5 weeks
Success Criterion	Stream consumption only	Stream consumption + bookmark creation
Critical Path Dependencies

Phase 1 (Models) 
    ↓
Phase 2 (Streams API) 
    ↓
Phase 2.5 (Annotations API) ⭐ MUST complete before Phase 5
    ↓
Phase 3 (Wrapping)
    ↓
Phase 4 (UI)
    ↓
Phase 5 (Ruth-AI Integration Test) ← Requires Phase 2.5 complete
    ↓
Phase 6 (Deprecation)
Why Phase 2.5 Is Critical:

Ruth-AI integration test (Phase 5) requires bookmark API to validate the success criterion
Without Phase 2.5, we can only test stream consumption, not the full platform capability
Delaying to Phase 6 would mean re-testing everything
Timeline Impact
Original	Updated	Change
8 weeks	8.5 weeks	+0.5 weeks
Justification: Adding 0.5 weeks is negligible compared to the risk of:

Building the wrong abstraction (device-scoped vs stream-scoped)
Failing the Ruth-AI integration test
Having to refactor bookmarks/snapshots later
Answer to Your Question
Yes, this changes the phased approach, but minimally:

Phase 1 now includes bookmark/snapshot migration (not just mentioned)
Phase 2.5 is NEW - dedicated to media annotations API
Phase 5 now validates bookmark creation as part of success criterion
Timeline extends by 0.5 weeks (8 weeks → 8.5 weeks)
The change is justified because:

Bookmarks are core platform capability, not a UI feature
Ruth-AI integration depends on programmatic bookmark creation
Doing it upfront prevents double-migration and technical debt
Recommendation: Proceed with the updated phased approach. The 0.5-week investment de-risks the entire V2 migration.