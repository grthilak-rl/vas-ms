# Phase 4: Remaining Implementation Tasks

## What's Been Completed ✅

### 1. Authentication Infrastructure (100%)
- ✅ JWT token management with auto-refresh
- ✅ React authentication context
- ✅ Login UI component
- ✅ Route protection wrapper
- ✅ Bearer token injection for all API calls

### 2. V2 API Client (100%)
- ✅ Complete TypeScript wrapper for all V2 endpoints
- ✅ Automatic JWT authentication
- ✅ Error handling and timeouts
- ✅ Type-safe interfaces for all schemas

### 3. App Integration (100%)
- ✅ Global auth provider in layout
- ✅ Auto-login on page load
- ✅ Login screen when not authenticated

**Progress: ~40% of Phase 4 Complete**

---

## What Needs to Be Done 📋

### Task 1: Update Bookmarks Page (PRIORITY: HIGH)

**File:** `frontend/app/bookmarks/page.tsx`

**Estimated Time:** 2-3 hours

#### Changes Required:

1. **Replace V1 API calls with V2:**
   ```typescript
   // OLD:
   import { getBookmarks, deleteBookmark, updateBookmark } from '@/lib/api';

   // NEW:
   import { getBookmarks, deleteBookmark, updateBookmark } from '@/lib/api-v2';
   ```

2. **Add Filtering Controls:**
   ```tsx
   // Add state variables
   const [eventType, setEventType] = useState<string>('all');
   const [selectedTags, setSelectedTags] = useState<string[]>([]);
   const [dateRange, setDateRange] = useState({ start: '', end: '' });

   // Update loadBookmarks function
   const loadBookmarks = async () => {
     const data = await getBookmarks(
       selectedDevice === 'all' ? undefined : selectedDevice,
       eventType === 'all' ? undefined : eventType,
       selectedTags.length > 0 ? selectedTags : undefined,
       dateRange.start || undefined,
       dateRange.end || undefined
     );
     setBookmarks(data.bookmarks); // V2 returns { bookmarks: [], pagination: {} }
   };
   ```

3. **Add Event Type Filter Dropdown:**
   ```tsx
   <select
     value={eventType}
     onChange={(e) => setEventType(e.target.value)}
     className="px-4 py-2 border border-gray-300 rounded-lg"
   >
     <option value="all">All Events</option>
     <option value="motion">Motion Detected</option>
     <option value="person_detected">Person Detected</option>
     <option value="vehicle">Vehicle</option>
     <option value="anomaly">Anomaly</option>
     <option value="manual">Manual</option>
   </select>
   ```

4. **Add Tags Filter (Multi-Select):**
   ```tsx
   // Use a library like react-select or build custom multi-select
   <div className="flex gap-2 flex-wrap">
     {availableTags.map(tag => (
       <button
         key={tag}
         onClick={() => {
           if (selectedTags.includes(tag)) {
             setSelectedTags(selectedTags.filter(t => t !== tag));
           } else {
             setSelectedTags([...selectedTags, tag]);
           }
         }}
         className={selectedTags.includes(tag) ? 'bg-blue-600 text-white' : 'bg-gray-200'}
       >
         {tag}
       </button>
     ))}
   </div>
   ```

5. **Add Date Range Filter:**
   ```tsx
   <input
     type="date"
     value={dateRange.start}
     onChange={(e) => setDateRange({ ...dateRange, start: e.target.value })}
   />
   <input
     type="date"
     value={dateRange.end}
     onChange={(e) => setDateRange({ ...dateRange, end: e.target.value })}
   />
   ```

6. **Add AI-Generated Indicator in Bookmark Card:**
   ```tsx
   {/* Replace existing source badge */}
   <div className="absolute top-2 left-2 flex gap-2">
     {bookmark.source === 'ai_generated' ? (
       <span className="px-2 py-1 rounded-md text-xs font-medium shadow-lg bg-purple-600 text-white flex items-center gap-1">
         🤖 AI Generated
       </span>
     ) : (
       <span className={`px-2 py-1 rounded-md text-xs font-medium shadow-lg ${
         bookmark.source === 'live' ? 'bg-red-600 text-white' : 'bg-blue-600 text-white'
       }`}>
         {bookmark.source === 'live' ? '🔴 Live' : '📼 Historical'}
       </span>
     )}
   </div>
   ```

7. **Display Confidence Score (if AI-generated):**
   ```tsx
   {bookmark.source === 'ai_generated' && bookmark.confidence_score && (
     <div className="text-xs text-gray-600">
       Confidence: {Math.round(bookmark.confidence_score * 100)}%
     </div>
   )}
   ```

8. **Display Tags as Chips:**
   ```tsx
   {bookmark.tags && bookmark.tags.length > 0 && (
     <div className="flex gap-1 flex-wrap mt-2">
       {bookmark.tags.map(tag => (
         <span key={tag} className="px-2 py-0.5 bg-blue-100 text-blue-800 text-xs rounded-full">
           {tag}
         </span>
       ))}
     </div>
   )}
   ```

9. **Update Bookmark Type Interface:**
   ```typescript
   // V2 Bookmark interface includes:
   interface V2Bookmark {
     id: string;
     stream_id: string;  // Changed from device_id
     source: 'live' | 'historical' | 'ai_generated';  // Added ai_generated
     event_type?: string;  // NEW
     confidence_score?: number;  // NEW (0.0-1.0)
     tags?: string[];  // NEW
     metadata?: Record<string, any>;  // NEW
     // ... rest of fields
   }
   ```

#### Testing Checklist:
- [ ] Bookmarks load from V2 API
- [ ] Filter by device works
- [ ] Filter by event_type works
- [ ] Filter by tags works (multiple selection)
- [ ] Filter by date range works
- [ ] AI-generated bookmarks show 🤖 indicator
- [ ] Confidence score displays correctly
- [ ] Tags show as chips
- [ ] Delete bookmark works
- [ ] Update bookmark label works

---

### Task 2: Update Snapshots Page (PRIORITY: MEDIUM)

**File:** `frontend/app/snapshots/page.tsx`

**Estimated Time:** 1 hour

#### Changes Required:

1. **Replace V1 API calls with V2:**
   ```typescript
   import { getSnapshots, deleteSnapshot } from '@/lib/api-v2';
   ```

2. **Update loadSnapshots function:**
   ```typescript
   const loadSnapshots = async () => {
     const data = await getSnapshots(
       selectedDevice === 'all' ? undefined : selectedDevice,
       dateRange.start || undefined,
       dateRange.end || undefined,
       100,
       0
     );
     setSnapshots(data.snapshots); // V2 returns { snapshots: [], pagination: {} }
   };
   ```

3. **Add Date Range Filter** (same as bookmarks)

4. **Update Snapshot Interface:**
   ```typescript
   interface V2Snapshot {
     id: string;
     stream_id: string;  // Changed from device_id
     timestamp: string;
     source: 'live' | 'historical';
     file_size: number;
     image_url: string;
     thumbnail_url?: string;
     metadata?: Record<string, any>;  // NEW
     created_at: string;
   }
   ```

#### Testing Checklist:
- [ ] Snapshots load from V2 API
- [ ] Filter by device works
- [ ] Filter by date range works
- [ ] Delete snapshot works
- [ ] Image displays correctly

---

### Task 3: Update Streams Page Snapshot/Bookmark Capture (PRIORITY: HIGH)

**File:** `frontend/app/streams/page.tsx`

**Estimated Time:** 2-3 hours

#### Problem:
Current implementation uses device_id for captures:
```typescript
POST /api/v1/snapshots/devices/{deviceId}/capture/live
POST /api/v1/bookmarks/devices/{deviceId}/capture/historical
```

V2 requires stream_id:
```typescript
POST /api/v2/streams/{streamId}/snapshots
POST /api/v2/streams/{streamId}/bookmarks
```

#### Solution: Add Stream Discovery Logic

1. **Add state for device-to-stream mapping:**
   ```typescript
   const [deviceStreamMap, setDeviceStreamMap] = useState<Record<string, string>>({});
   ```

2. **Create stream discovery function:**
   ```typescript
   import { getStreams } from '@/lib/api-v2';

   const discoverStreams = async () => {
     try {
       const { streams } = await getStreams('live'); // Only get active streams

       // Map camera_id (device_id) to stream_id
       const mapping: Record<string, string> = {};
       streams.forEach(stream => {
         mapping[stream.camera_id] = stream.id;
       });

       setDeviceStreamMap(mapping);
       console.log('📡 Stream discovery:', mapping);
     } catch (err) {
       console.error('Failed to discover streams:', err);
     }
   };
   ```

3. **Call discovery when devices load:**
   ```typescript
   const loadDevices = async () => {
     const data = await getDevices();
     setDevices(data);

     // Discover V2 streams for snapshot/bookmark capture
     await discoverStreams();
   };
   ```

4. **Update handleCaptureSnapshot to use stream_id:**
   ```typescript
   import { createSnapshot } from '@/lib/api-v2';

   const handleCaptureSnapshot = async (deviceId: string) => {
     try {
       setCapturingSnapshot(prev => ({ ...prev, [deviceId]: true }));

       const streamId = deviceStreamMap[deviceId];
       if (!streamId) {
         throw new Error('No active stream found for this device');
       }

       const mode = playerModes[deviceId] || 'live';
       let timestamp: string | undefined;

       if (mode === 'historical') {
         const playerRef = playerRefs.current[deviceId];
         const videoElement = playerRef?.getVideoElement();
         if (!videoElement) throw new Error('Video element not available');

         const currentTime = videoElement.currentTime || 0;
         timestamp = await getTimestampFromHLSPosition(deviceId, currentTime);
       }

       // V2 API call
       const snapshot = await createSnapshot(streamId, timestamp);
       console.log('✅ Snapshot captured:', snapshot.id);

       setSnapshotSuccess(prev => ({ ...prev, [deviceId]: true }));
       setTimeout(() => {
         setSnapshotSuccess(prev => ({ ...prev, [deviceId]: false }));
       }, 2000);

     } catch (err: any) {
       console.error('❌ Failed to capture snapshot:', err);
       alert('Failed to capture snapshot: ' + err.message);
     } finally {
       setCapturingSnapshot(prev => ({ ...prev, [deviceId]: false }));
     }
   };
   ```

5. **Update handleCaptureBookmark to use stream_id:**
   ```typescript
   import { createBookmark } from '@/lib/api-v2';

   const handleCaptureBookmark = async (deviceId: string) => {
     try {
       setCapturingBookmark(prev => ({ ...prev, [deviceId]: true }));

       const streamId = deviceStreamMap[deviceId];
       if (!streamId) {
         throw new Error('No active stream found for this device');
       }

       const mode = playerModes[deviceId] || 'live';
       let centerTimestamp: string;

       if (mode === 'live') {
         // For live mode, use current time
         centerTimestamp = new Date().toISOString();
       } else {
         // Historical mode - get timestamp from HLS playlist
         const playerRef = playerRefs.current[deviceId];
         const videoElement = playerRef?.getVideoElement();
         if (!videoElement) throw new Error('Video element not available');

         const currentTime = videoElement.currentTime || 0;
         centerTimestamp = await getTimestampFromHLSPosition(deviceId, currentTime);
       }

       console.log('📍 Bookmark Request:', {
         streamId,
         centerTimestamp,
         mode
       });

       // V2 API call
       const bookmark = await createBookmark(streamId, centerTimestamp);
       console.log('✅ Bookmark captured:', bookmark.id);

       setBookmarkSuccess(prev => ({ ...prev, [deviceId]: true }));
       setTimeout(() => {
         setBookmarkSuccess(prev => ({ ...prev, [deviceId]: false }));
       }, 2000);

     } catch (err: any) {
       console.error('❌ Failed to capture bookmark:', err);
       alert('Failed to capture bookmark: ' + err.message);
     } finally {
       setCapturingBookmark(prev => ({ ...prev, [deviceId]: false }));
     }
   };
   ```

6. **Add imports at top:**
   ```typescript
   import { getStreams, createSnapshot, createBookmark } from '@/lib/api-v2';
   ```

#### Testing Checklist:
- [ ] Stream discovery works on page load
- [ ] Snapshot capture (live) works with V2 API
- [ ] Snapshot capture (historical) works with timestamp
- [ ] Bookmark capture (live) works with V2 API
- [ ] Bookmark capture (historical) works with timestamp
- [ ] Error handling for missing stream_id
- [ ] Console logs show correct stream_id mapping

---

### Task 4: MediaSoupPlayer V2 Consumer Attachment (PRIORITY: CRITICAL)

**Files:**
- `frontend/components/players/MediaSoupPlayer.tsx`
- `frontend/components/players/UnifiedPlayer.tsx`
- `frontend/components/players/DualModePlayer.tsx`

**Estimated Time:** 4-6 hours

**Complexity:** **VERY HIGH** - Core WebRTC signaling rewrite

#### Current Architecture (V1):
```
Frontend → WebSocket (ws://backend:8080/ws/mediasoup) → Backend Proxy → MediaSoup
```

#### Target Architecture (V2):
```
Frontend → REST API (POST /v2/streams/{id}/consume) → Backend → MediaSoup
```

#### Changes Required in MediaSoupPlayer.tsx:

1. **Remove WebSocket connection:**
   ```typescript
   // DELETE these lines (around line 15):
   const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://10.30.250.245:8080/ws/mediasoup';
   const wsRef = useRef<WebSocket | null>(null);

   // DELETE all WebSocket event handlers:
   wsRef.current.onopen = ...
   wsRef.current.onmessage = ...
   wsRef.current.onerror = ...
   wsRef.current.onclose = ...
   ```

2. **Add V2 API imports:**
   ```typescript
   import { attachConsumer, connectConsumer, detachConsumer } from '@/lib/api-v2';
   ```

3. **Add state for stream_id and consumer_id:**
   ```typescript
   const [streamId, setStreamId] = useState<string | null>(null);
   const [consumerId, setConsumerId] = useState<string | null>(null);
   ```

4. **Add stream discovery on mount:**
   ```typescript
   useEffect(() => {
     if (!shouldConnect) return;

     discoverAndConnect();
   }, [shouldConnect, deviceId]);

   const discoverAndConnect = async () => {
     try {
       // Find stream for this device
       const { streams } = await getStreams(undefined, 100, 0);
       const stream = streams.find(s => s.camera_id === deviceId && s.state === 'live');

       if (!stream) {
         throw new Error('No active stream found for device');
       }

       setStreamId(stream.id);
       await connectToStream(stream.id);
     } catch (err) {
       console.error('Stream discovery failed:', err);
       setError(err.message);
     }
   };
   ```

5. **Rewrite connectToStream function:**
   ```typescript
   const connectToStream = async (streamId: string) => {
     try {
       console.log('🔗 Connecting to stream:', streamId);

       // Step 1: Load MediaSoup device capabilities
       if (!deviceRef.current) {
         deviceRef.current = new Device();
       }

       const routerRtpCapabilities = await fetchRouterCapabilities();
       await deviceRef.current.load({ routerRtpCapabilities });

       // Step 2: Attach consumer via REST API
       const response = await attachConsumer(streamId, {
         client_id: `frontend-${Date.now()}`,
         rtp_capabilities: deviceRef.current.rtpCapabilities
       });

       console.log('📦 Consumer attached:', response.consumer_id);
       setConsumerId(response.consumer_id);

       // Step 3: Create WebRTC transport
       const transport = deviceRef.current.createRecvTransport({
         id: response.transport.id,
         iceParameters: response.transport.ice_parameters,
         iceCandidates: response.transport.ice_candidates,
         dtlsParameters: response.transport.dtls_parameters,
       });

       transportRef.current = transport;

       // Step 4: Handle DTLS connect
       transport.on('connect', async ({ dtlsParameters }, callback, errback) => {
         try {
           await connectConsumer(response.consumer_id, dtlsParameters);
           callback();
         } catch (err) {
           errback(err);
         }
       });

       // Step 5: Create consumer
       const consumer = await transport.consume({
         id: response.consumer_id,
         producerId: 'not-used', // Backend handles this
         kind: 'video',
         rtpParameters: response.rtp_parameters,
       });

       consumerRef.current = consumer;

       // Step 6: Attach video track
       const stream = new MediaStream([consumer.track]);
       if (videoRef.current) {
         videoRef.current.srcObject = stream;
       }

       console.log('✅ MediaSoup connection established');
       setConnected(true);

     } catch (err) {
       console.error('❌ Connection failed:', err);
       setError(err.message);
     }
   };
   ```

6. **Add router capabilities fetch:**
   ```typescript
   const fetchRouterCapabilities = async () => {
     // This might need a new V2 endpoint: GET /v2/streams/{id}/router-capabilities
     // Or hardcode common capabilities if backend doesn't expose this
     return {
       codecs: [
         {
           kind: 'video',
           mimeType: 'video/H264',
           clockRate: 90000,
           parameters: {}
         }
       ],
       headerExtensions: []
     };
   };
   ```

7. **Update disconnect/cleanup:**
   ```typescript
   const disconnect = async () => {
     try {
       if (consumerId) {
         await detachConsumer(consumerId);
       }

       consumerRef.current?.close();
       transportRef.current?.close();

       setConnected(false);
       setConsumerId(null);
       setStreamId(null);
     } catch (err) {
       console.error('Disconnect error:', err);
     }
   };
   ```

#### **IMPORTANT:** Router Capabilities Endpoint

You may need to add a new V2 backend endpoint:

```python
# backend/app/api/v2/streams.py

@router.get("/{stream_id}/router-capabilities")
async def get_router_capabilities(stream_id: UUID):
    """Get MediaSoup router RTP capabilities for client device initialization."""
    return {
        "codecs": [
            {
                "kind": "video",
                "mimeType": "video/H264",
                "clockRate": 90000,
                "parameters": {
                    "packetization-mode": 1,
                    "profile-level-id": "42e01f"
                }
            }
        ],
        "headerExtensions": []
    }
```

#### Testing Checklist:
- [ ] Stream discovery finds correct stream_id
- [ ] Consumer attachment succeeds
- [ ] Transport creation works
- [ ] DTLS handshake completes
- [ ] Video track plays correctly
- [ ] Consumer detachment on disconnect
- [ ] Error handling for missing stream
- [ ] Multiple players can connect simultaneously

---

### Task 5: Remove Hardcoded URLs (PRIORITY: LOW)

**Affected Files:** 22 instances

**Estimated Time:** 1 hour

#### Strategy:

1. **Find all hardcoded URLs:**
   ```bash
   grep -r "10.30.250.245:8080" frontend/
   ```

2. **Replace with centralized import:**
   ```typescript
   // OLD:
   const url = `${process.env.NEXT_PUBLIC_API_URL || 'http://10.30.250.245:8080'}/api/...`;

   // NEW:
   import { API_URL } from '@/lib/api-v2';
   const url = `${API_URL}/api/...`;
   ```

3. **Update next.config.ts default:**
   ```typescript
   env: {
     NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080',
   }
   ```

#### Testing Checklist:
- [ ] All API calls work with centralized URL
- [ ] Environment variable override works
- [ ] No hardcoded IPs remaining

---

## Testing Plan

### Authentication Tests
```bash
# 1. Login with valid credentials
# 2. Login with invalid credentials → should show error
# 3. Logout → should redirect to login
# 4. Token refresh → wait 5 minutes, check network tab
# 5. Token expiry → manually expire token in localStorage
```

### Bookmarks Tests
```bash
# 1. List bookmarks → should use V2 API
# 2. Filter by event_type → check network request
# 3. Filter by tags (multiple) → check query params
# 4. Filter by date range → check start_date/end_date
# 5. AI bookmark indicator → find ai_generated bookmark
# 6. Confidence score → verify displays correctly
# 7. Tags display → verify chips render
# 8. Delete bookmark → should use V2 API
# 9. Update label → should use V2 API
```

### Snapshots Tests
```bash
# 1. List snapshots → should use V2 API
# 2. Filter by date range → check query params
# 3. Delete snapshot → should use V2 API
```

### Streams Tests
```bash
# 1. Stream discovery → check console logs
# 2. Snapshot capture (live) → verify uses stream_id
# 3. Snapshot capture (historical) → verify timestamp sent
# 4. Bookmark capture (live) → verify uses stream_id
# 5. Bookmark capture (historical) → verify timestamp
# 6. Error handling → test with no active stream
```

### WebRTC Tests
```bash
# 1. Player connection → verify uses REST API (not WebSocket)
# 2. Video playback → verify track plays
# 3. Multiple streams → test 2x2 grid
# 4. Disconnect → verify consumer detached
# 5. Reconnect → verify works after disconnect
```

---

## Common Pitfalls & Solutions

### Issue 1: "No active stream found"
**Cause:** Device has no corresponding V2 stream
**Solution:** Ensure V1 device has started a stream first

### Issue 2: "Authentication required"
**Cause:** JWT token expired or invalid
**Solution:** Check token in localStorage, verify backend auth works

### Issue 3: "Router capabilities not found"
**Cause:** Missing V2 endpoint for router capabilities
**Solution:** Add endpoint or hardcode capabilities

### Issue 4: CORS errors
**Cause:** Backend not allowing frontend origin
**Solution:** Check backend CORS settings in `main.py`

### Issue 5: WebSocket still trying to connect
**Cause:** Old WebSocket code not fully removed
**Solution:** Search for `ws://` and `WebSocket` references

---

## Quick Reference

### V2 API Endpoints
```
Auth:
POST   /v2/auth/token                  - Get JWT tokens
POST   /v2/auth/clients                - Create client

Streams:
GET    /v2/streams                     - List streams
GET    /v2/streams/{id}                - Get stream details
POST   /v2/streams/{id}/consume        - Attach consumer
GET    /v2/streams/{id}/health         - Stream health

Consumers:
POST   /v2/consumers/{id}/connect      - DTLS connect
DELETE /v2/consumers/{id}              - Detach consumer

Bookmarks:
GET    /v2/bookmarks                   - List bookmarks
POST   /v2/streams/{id}/bookmarks      - Create bookmark
PUT    /v2/bookmarks/{id}              - Update bookmark
DELETE /v2/bookmarks/{id}              - Delete bookmark

Snapshots:
GET    /v2/snapshots                   - List snapshots
POST   /v2/streams/{id}/snapshots      - Create snapshot
DELETE /v2/snapshots/{id}              - Delete snapshot

Health:
GET    /v2/health                      - System health
GET    /v2/health/streams              - All streams health
```

### Important Files
```
frontend/lib/auth.ts                  - Token management
frontend/lib/api-v2.ts                - V2 API client
frontend/contexts/AuthContext.tsx     - Auth context
frontend/components/auth/LoginForm.tsx - Login UI
frontend/app/bookmarks/page.tsx       - Bookmarks page
frontend/app/snapshots/page.tsx       - Snapshots page
frontend/app/streams/page.tsx         - Streams page
frontend/components/players/MediaSoupPlayer.tsx - WebRTC player
```

---

## Getting Started

1. **Test Authentication:**
   ```bash
   # Start backend
   cd backend && python main.py

   # Start frontend
   cd frontend && npm run dev

   # Navigate to http://localhost:3000
   # Should see login screen
   ```

2. **Create Test Client:**
   ```bash
   curl -X POST http://localhost:8080/api/v2/auth/clients \
     -H "Content-Type: application/json" \
     -d '{
       "client_id": "frontend-test",
       "scopes": ["streams:read", "streams:consume", "bookmarks:write", "snapshots:write"]
     }'
   ```

3. **Login with Credentials:**
   - Use client_id and client_secret from step 2
   - Should redirect to dashboard

4. **Continue with Task 1 (Bookmarks)**

---

## Questions or Issues?

If you encounter issues:

1. Check browser console for errors
2. Check network tab for failed requests
3. Check backend logs for auth errors
4. Verify JWT token in localStorage
5. Test V2 API endpoints directly with curl

Good luck! 🚀
