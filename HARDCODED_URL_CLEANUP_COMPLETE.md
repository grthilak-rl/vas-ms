# Hardcoded URL Cleanup - Complete ✅

**Date:** 2026-01-10
**Status:** 100% Complete

## Summary

All hardcoded URLs have been successfully replaced with the centralized `API_URL` constant from `@/lib/api-v2`. This completes the final 5% of Phase 4.

---

## Files Updated

### 1. `/frontend/app/streams/page.tsx`
**Changes:** 4 instances replaced
- ✅ Import `API_URL` from `@/lib/api-v2`
- ✅ Line 122: Start stream endpoint - `${API_URL}/api/v1/devices/${deviceId}/start-stream`
- ✅ Line 157: Stop stream endpoint - `${API_URL}/api/v1/devices/${deviceId}/stop-stream`
- ✅ Line 240: HLS playlist URL - `${API_URL}/api/v1/recordings/devices/${deviceId}/playlist`

### 2. `/frontend/app/streams/[id]/page.tsx`
**Changes:** 2 instances replaced
- ✅ Import `API_URL` from `@/lib/api-v2`
- ✅ Line 87: WebSocket signaling URL - `` `${API_URL.replace('http', 'ws')}/ws/signaling` ``

### 3. `/frontend/components/players/DualModePlayer.tsx`
**Changes:** 3 instances replaced
- ✅ Import `API_URL` from `@/lib/api-v2`
- ✅ Line 49: Recording dates endpoint - `${API_URL}/api/v1/recordings/devices/${deviceId}/dates`
- ✅ Line 183: MediaSoup WebSocket URL - `` `${API_URL.replace('http', 'ws')}/ws/mediasoup` ``
- ✅ Line 190: HLS playlist URL - `${API_URL}/api/v1/recordings/devices/${deviceId}/playlist`

### 4. `/frontend/components/players/UnifiedPlayer.tsx`
**Changes:** 3 instances replaced
- ✅ Import `API_URL` from `@/lib/api-v2`
- ✅ Line 47: Recording dates endpoint - `${API_URL}/api/v1/recordings/devices/${deviceId}/dates`
- ✅ Line 188: MediaSoup WebSocket URL - `` `${API_URL.replace('http', 'ws')}/ws/mediasoup` ``
- ✅ Line 195: HLS playlist URL - `${API_URL}/api/v1/recordings/devices/${deviceId}/playlist`

### 5. `/frontend/components/players/HLSPlayer.tsx`
**Changes:** 1 instance replaced
- ✅ Import `API_URL` from `@/lib/api-v2`
- ✅ Line 53: Historical snapshot capture - `${API_URL}/api/v1/snapshots/devices/${deviceId}/capture/historical`

### 6. `/frontend/components/players/MediaSoupPlayer.tsx`
**Changes:** 1 instance replaced
- ✅ Import `API_URL` from `@/lib/api-v2`
- ✅ Line 16: Default MediaSoup URL - `` `${API_URL.replace('http', 'ws')}/ws/mediasoup` ``

### 7. `/frontend/contexts/AuthContext.tsx`
**Changes:** 3 instances replaced
- ✅ Import `API_URL` from `@/lib/api-v2`
- ✅ All 3 instances of `process.env.NEXT_PUBLIC_API_URL || 'http://10.30.250.245:8080'` replaced with `API_URL`

---

## Remaining Hardcoded URLs (Intentional)

The following 3 instances remain as centralized configuration defaults:

1. **`frontend/lib/api-v2.ts:8`**
   ```typescript
   const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://10.30.250.245:8080';
   ```
   ✅ **Status:** Correct - This is the centralized constant definition

2. **`frontend/lib/api.ts:1`**
   ```typescript
   const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://10.30.250.245:8080';
   ```
   ✅ **Status:** Correct - Legacy V1 API constant definition

3. **`frontend/next.config.ts:6`**
   ```typescript
   NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://10.30.250.245:8080',
   ```
   ✅ **Status:** Correct - Next.js environment variable configuration

---

## WebSocket URL Pattern

For WebSocket connections, the following pattern is used:

```typescript
`${API_URL.replace('http', 'ws')}/ws/mediasoup`
```

This dynamically converts:
- `http://10.30.250.245:8080` → `ws://10.30.250.245:8080`
- `https://api.example.com` → `wss://api.example.com`

---

## Benefits

1. **Single Source of Truth**
   - All URLs now use the centralized `API_URL` constant
   - Easy to change backend URL via environment variable

2. **Environment Flexibility**
   - Development: `NEXT_PUBLIC_API_URL=http://localhost:8080`
   - Production: `NEXT_PUBLIC_API_URL=https://api.production.com`
   - Default fallback: `http://10.30.250.245:8080`

3. **Type Safety**
   - All imports are typed and checked by TypeScript
   - No string duplication errors

4. **Maintainability**
   - Future URL changes only need to update `.env` file
   - No scattered hardcoded values across codebase

---

## Verification

```bash
# Check for hardcoded IPs in TypeScript files
grep -r "10\.30\.250\.245" frontend --include="*.tsx" --include="*.ts" | wc -l
# Result: 3 (all in centralized config files - correct!)
```

---

## Phase 4 Status

**Overall Completion: 100%** 🎉

### Completed Tasks:
1. ✅ Update Bookmarks Page (V2 API + filters)
2. ✅ Update Snapshots Page (V2 API + date filter)
3. ✅ Update Streams Page (stream discovery + V2 capture)
4. ✅ MediaSoupPlayer V2 Implementation (REST API signaling)
5. ✅ **Remove hardcoded URLs** ← Just completed!

### Next Steps:
- Proceed to **Phase 5: Testing & Validation**
- Backend team: Implement `GET /api/v2/streams/{stream_id}/router-capabilities` endpoint
- Full end-to-end testing with real cameras

---

## Document Version

**Version:** 1.0
**Last Updated:** 2026-01-10
**Author:** Claude Code Assistant
**Status:** Phase 4 - 100% Complete ✅
