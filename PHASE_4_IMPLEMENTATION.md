# Phase 4: UI Refactoring - Implementation Guide

## Overview
Phase 4 migrates the frontend from V1 API to V2 API while maintaining backward compatibility with device management.

## Architecture Decisions

### Hybrid API Approach
- **V1 API (Keep):** Device CRUD operations (`/api/v1/devices`)
- **V2 API (New):** Streams, Consumers, Bookmarks, Snapshots
- **Reason:** V2 has no device management API - devices are still managed via V1

### Key Concept: Device vs Stream
- **V1 Model:** Device = Camera source
- **V2 Model:** Stream = Active media pipeline (has `camera_id` reference to V1 Device)
- **Mapping:** Each V1 Device can have multiple V2 Streams, but typically 1:1

## Implementation Status

### ✅ Completed

#### 1. JWT Authentication System
**Files Created:**
- `frontend/lib/auth.ts` - Token management (storage, refresh, expiry)
- `frontend/contexts/AuthContext.tsx` - React context for auth state
- `frontend/components/auth/LoginForm.tsx` - Login UI component
- `frontend/components/auth/AuthGuard.tsx` - Route protection wrapper

**Features:**
- localStorage-based token persistence
- Automatic token refresh (checks every minute)
- 5-minute pre-expiry refresh
- Client credentials storage
- Bearer token injection

#### 2. V2 API Client
**File Created:**
- `frontend/lib/api-v2.ts` - Complete V2 API wrapper

**Endpoints Implemented:**
- `GET /v2/streams` - List all streams
- `GET /v2/streams/{id}` - Get stream details
- `POST /v2/streams/{id}/consume` - Attach WebRTC consumer
- `POST /v2/consumers/{id}/connect` - Complete DTLS handshake
- `DELETE /v2/consumers/{id}` - Detach consumer
- `GET /v2/bookmarks` - List bookmarks with filtering
- `POST /v2/streams/{id}/bookmarks` - Create bookmark
- `PUT /v2/bookmarks/{id}` - Update bookmark
- `DELETE /v2/bookmarks/{id}` - Delete bookmark
- `GET /v2/snapshots` - List snapshots
- `POST /v2/streams/{id}/snapshots` - Create snapshot
- `DELETE /v2/snapshots/{id}` - Delete snapshot
- `GET /v2/health` - System health
- `GET /v2/health/streams` - All streams health

**Features:**
- Automatic JWT Bearer token injection
- Timeout handling (10s default, 30s for captures)
- 401 auth error handling
- Abort controller for cancellation

#### 3. App Integration
**Files Modified:**
- `frontend/app/layout.tsx` - Wrapped with AuthProvider + AuthGuard

**Features:**
- Global authentication state
- Auto-login on page load if credentials exist
- Login screen when not authenticated

### 🚧 In Progress

#### 4. Streams Page Migration
**Current Status:** Analyzing complexity

**Challenges:**
1. **Device Management:** Still needs V1 `/api/v1/devices` for device list
2. **Stream Control:** Need to map V1 devices to V2 streams
3. **Snapshot/Bookmark Capture:** Must use V2 stream-based APIs
4. **Player Connection:** Needs V2 consumer attachment flow

**Migration Strategy:**
```typescript
// OLD (V1):
POST /api/v1/devices/{deviceId}/start-stream
POST /api/v1/snapshots/devices/{deviceId}/capture/live
POST /api/v1/bookmarks/devices/{deviceId}/capture/live

// NEW (V2):
GET /api/v2/streams?camera_id={deviceId}  // Find stream for device
POST /api/v2/streams/{streamId}/snapshots
POST /api/v2/streams/{streamId}/bookmarks
```

**Implementation Plan:**
1. Add stream discovery logic (map device → stream)
2. Update snapshot capture to use stream_id
3. Update bookmark capture to use stream_id
4. Maintain historical timestamp calculation logic
5. Keep grid layout and UI unchanged

### 📋 Pending

#### 5. MediaSoupPlayer V2 Integration
**Current Implementation:** Direct WebSocket to `ws://backend:8080/ws/mediasoup`

**Target Implementation:**
```typescript
// POST /v2/streams/{streamId}/consume
{
  "client_id": "frontend-instance-123",
  "rtp_capabilities": {...}
}

// Returns:
{
  "consumer_id": "uuid",
  "transport": {
    "id": "...",
    "ice_parameters": {...},
    "ice_candidates": [...],
    "dtls_parameters": {...}
  },
  "rtp_parameters": {...}
}
```

**Changes Required:**
- Remove direct MediaSoup WebSocket connection
- Use REST API for consumer attachment
- Create transport using returned parameters
- Connect via DTLS using `/v2/consumers/{id}/connect`

**Files to Modify:**
- `frontend/components/players/MediaSoupPlayer.tsx`
- `frontend/components/players/UnifiedPlayer.tsx`
- `frontend/components/players/DualModePlayer.tsx`

#### 6. Bookmarks Page Enhancement
**Current:** Basic list/delete functionality with V1 API

**Target V2 Features:**
- Filter by `event_type` (motion, person_detected, vehicle, etc.)
- Filter by `tags` (multiple tag support)
- Filter by date range
- Visual indicator for `source: 'ai_generated'`
- Display `confidence_score` for AI bookmarks
- Show tags as chips

**UI Mockup:**
```
┌──────────────────────────────────────────┐
│ Filters:                                 │
│ [Event Type ▼] [Tags ▼] [Date Range ▼]   │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│ 📹 Front Door - 2026-01-10 14:30:15      │
│ [AI Generated] 🤖 Confidence: 95%        │
│ Tags: [person] [motion]                  │
│ Duration: 6.0s                           │
└──────────────────────────────────────────┘
```

#### 7. Snapshots Page Enhancement
**Current:** Basic list/delete functionality with V1 API

**Target V2 Features:**
- Use `stream_id` instead of `device_id`
- Filter by date range
- Display metadata if available

#### 8. Remove Hardcoded URLs
**Current:** 22 instances of `10.30.250.245:8080` hardcoded

**Target:** Centralize to `lib/api-v2.ts` and use environment variable

**Files to Update:**
- Remove inline `${process.env.NEXT_PUBLIC_API_URL || '...'}`
- Import `API_URL` from `lib/api-v2.ts`

## Migration Checklist

### Frontend API Calls
- [x] JWT authentication system
- [x] V2 API client with auto-auth
- [ ] Streams page → V2 streams API
- [ ] Bookmarks page → V2 bookmarks API
- [ ] Snapshots page → V2 snapshots API
- [ ] Dashboard → V2 health API

### WebRTC Signaling
- [ ] Remove MediaSoup WebSocket connection
- [ ] Implement V2 consumer attachment flow
- [ ] Update transport creation
- [ ] Update DTLS connect flow

### UI Enhancements
- [ ] Bookmark filtering (event_type, tags, date)
- [ ] AI-generated bookmark indicators
- [ ] Confidence score display
- [ ] Tag chips UI

### Code Quality
- [ ] Remove all hardcoded API URLs
- [ ] Add TypeScript types for V2 schemas
- [ ] Error boundary for auth failures
- [ ] Loading states for async operations

## Testing Plan

### Authentication
- [ ] Login with valid credentials
- [ ] Login with invalid credentials
- [ ] Token auto-refresh
- [ ] Token expiry handling
- [ ] Logout and re-login

### Streams
- [ ] List streams
- [ ] Start stream (V1 compatibility)
- [ ] Stop stream (V1 compatibility)
- [ ] WebRTC connection with V2 consumer API
- [ ] Snapshot capture (live + historical)
- [ ] Bookmark capture (live + historical)

### Bookmarks
- [ ] List bookmarks
- [ ] Filter by event_type
- [ ] Filter by tags
- [ ] Filter by date range
- [ ] Create bookmark
- [ ] Update bookmark label/tags
- [ ] Delete bookmark
- [ ] AI-generated indicator visible

### Snapshots
- [ ] List snapshots
- [ ] Filter by date range
- [ ] Create snapshot (live + historical)
- [ ] Delete snapshot

### Error Handling
- [ ] 401 Unauthorized → redirect to login
- [ ] Network timeout → error message
- [ ] Invalid stream ID → error message
- [ ] Capture failure → error message

## Known Issues & Limitations

1. **Hybrid API Approach:** Frontend uses both V1 (devices) and V2 (streams) APIs
2. **Device-Stream Mapping:** Assumes 1:1 mapping between device and active stream
3. **No V2 Device Management:** Device CRUD still uses V1 API
4. **HLS Playlist Parsing:** Historical timestamp calculation still uses V1 endpoint

## Next Steps

1. **Complete Streams Page Migration**
   - Map devices to streams
   - Update snapshot/bookmark capture
   - Test live + historical modes

2. **Implement V2 Consumer Attachment**
   - Refactor MediaSoupPlayer
   - Remove WebSocket connection
   - Use REST API for signaling

3. **Enhance Bookmarks UI**
   - Add filtering controls
   - Implement AI indicator
   - Add tag management

4. **Testing & Validation**
   - End-to-end testing
   - Load testing
   - Error scenario testing

## Files Modified Summary

### Created (8 files)
- `frontend/lib/auth.ts`
- `frontend/lib/api-v2.ts`
- `frontend/contexts/AuthContext.tsx`
- `frontend/components/auth/LoginForm.tsx`
- `frontend/components/auth/AuthGuard.tsx`

### Modified (1 file)
- `frontend/app/layout.tsx`

### To Modify (7 files)
- `frontend/app/streams/page.tsx`
- `frontend/app/bookmarks/page.tsx`
- `frontend/app/snapshots/page.tsx`
- `frontend/components/players/MediaSoupPlayer.tsx`
- `frontend/components/players/UnifiedPlayer.tsx`
- `frontend/components/players/DualModePlayer.tsx`
- `frontend/next.config.ts`
