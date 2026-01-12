# MediaSoup V2 Backend Requirements

## Overview

The new `MediaSoupPlayerV2.tsx` component uses **REST API** instead of WebSocket for MediaSoup consumer attachment. This document outlines the backend changes required to support this new approach.

## Current State

✅ **Already Implemented:**
- `POST /api/v2/streams/{stream_id}/consume` - Attach consumer to stream
- `DELETE /api/v2/consumers/{consumer_id}` - Detach consumer
- `GET /api/v2/streams/{stream_id}` - Get stream details

## Required Backend Changes

### 1. Add Router Capabilities Endpoint (CRITICAL)

**Endpoint:** `GET /api/v2/streams/{stream_id}/router-capabilities`

**Purpose:** Returns the MediaSoup router's RTP capabilities needed to initialize the MediaSoup device on the client side.

**Response Example:**
```json
{
  "rtp_capabilities": {
    "codecs": [
      {
        "kind": "video",
        "mimeType": "video/VP8",
        "clockRate": 90000,
        "preferredPayloadType": 96
      }
    ],
    "headerExtensions": [...],
    "fecMechanisms": []
  }
}
```

**Implementation Location:**
- File: `backend/app/api/v2/streams.py`
- Add new router to existing `router` object

**Sample Implementation:**
```python
@router.get("/{stream_id}/router-capabilities")
async def get_router_capabilities(
    stream_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get MediaSoup router RTP capabilities for stream"""
    # Get stream from database
    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")

    # Get router from mediasoup_manager
    # Assuming you have access to the router instance
    router = mediasoup_manager.get_router_for_stream(stream_id)

    return {
        "rtp_capabilities": router.rtpCapabilities
    }
```

### 2. Verify Consumer Attachment Endpoint

**Endpoint:** `POST /api/v2/streams/{stream_id}/consume`

**Current Implementation Status:** ✅ Already exists (confirmed in Phase 3)

**Expected Request:**
```json
{
  "client_id": "web-1234567890-abc123",
  "rtp_capabilities": {
    "codecs": [...],
    "headerExtensions": [...]
  }
}
```

**Expected Response:**
```json
{
  "consumer_id": "uuid-of-consumer",
  "transport": {
    "id": "transport-uuid",
    "ice_parameters": {...},
    "ice_candidates": [...],
    "dtls_parameters": {...}
  },
  "rtp_parameters": {...}
}
```

**Verification:** Ensure this endpoint:
1. Creates a new WebRTC transport for the consumer
2. Creates a consumer for the video producer
3. Returns all necessary parameters for client-side consumer creation

### 3. Consumer Detachment Endpoint

**Endpoint:** `DELETE /api/v2/consumers/{consumer_id}`

**Current Implementation Status:** ✅ Already exists (confirmed in Phase 3)

**Expected Behavior:**
1. Close the consumer
2. Close the associated transport
3. Clean up any resources

## Frontend Integration Flow

The V2 MediaSoupPlayer follows this flow:

```
1. GET /api/v2/streams/{stream_id}
   → Verify stream exists and is live

2. GET /api/v2/streams/{stream_id}/router-capabilities
   → Get router RTP capabilities
   → Load MediaSoup device

3. POST /api/v2/streams/{stream_id}/consume
   → Create consumer with client RTP capabilities
   → Receive transport and consumer parameters

4. Client-side WebRTC connection
   → Create recv transport
   → Create consumer
   → Attach to video element

5. On cleanup: DELETE /api/v2/consumers/{consumer_id}
   → Clean up resources
```

## Key Differences from V1 WebSocket Approach

| Aspect | V1 (WebSocket) | V2 (REST API) |
|--------|----------------|---------------|
| **Communication** | WebSocket bidirectional | HTTP REST unidirectional |
| **Router Caps** | `getRouterRtpCapabilities` message | `GET /router-capabilities` |
| **Transport** | `createWebRtcTransport` message | Included in `POST /consume` response |
| **Consumer** | `consume` message | `POST /consume` endpoint |
| **DTLS Connect** | `connectWebRtcTransport` message | Automatic (params in response) |
| **Cleanup** | WebSocket close | `DELETE /consumers/{id}` |

## Testing Checklist

Once backend endpoints are implemented, test:

- [ ] Router capabilities endpoint returns valid RTP capabilities
- [ ] Consumer attachment creates transport and consumer correctly
- [ ] DTLS handshake completes without additional signaling
- [ ] Video plays in browser
- [ ] Consumer detachment cleans up resources
- [ ] Multiple consumers can attach to the same stream
- [ ] Error handling for missing/stopped streams

## Migration Strategy

**Recommended Approach:**
1. ✅ Keep V1 WebSocket implementation (backwards compatible)
2. ✅ Add new V2 REST endpoints alongside V1
3. ✅ Frontend uses V2 when available, falls back to V1 if needed
4. ❌ Remove V1 WebSocket after full V2 deployment and testing

## Files Modified

**Frontend:**
- `frontend/components/players/MediaSoupPlayerV2.tsx` - New V2 player
- `frontend/lib/api-v2.ts` - Added router capabilities function

**Backend (Required):**
- `backend/app/api/v2/streams.py` - Add router capabilities endpoint
- `backend/app/api/v2/consumers.py` - Verify consume/detach endpoints

## Questions?

If you have questions about the V2 MediaSoup implementation, check:
1. MediaSoup documentation: https://mediasoup.org/documentation/
2. Phase 4 implementation guide: `PHASE_4_IMPLEMENTATION.md`
3. V2 API architectural proposal: `VAS-MS-V2_ARCHITECTURAL_PROPOSAL.md`
