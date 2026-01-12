# Phase 3 Implementation Guide

## Overview

Phase 3 adds comprehensive **observability and operational capabilities** to VAS-MS-V2 while maintaining the **BLACK BOX PRINCIPLE** - wrapping existing stable components without modification.

---

## What Was Built

### 1. Wrapper Services (Black Box Wrappers)

These services provide lifecycle management and monitoring WITHOUT modifying the underlying data plane:

#### StreamIngestionService
- **Location**: `backend/app/services/stream_ingestion_service.py`
- **Purpose**: Wraps FFmpeg RTSP→RTP/HLS pipeline
- **Features**:
  - Start/stop/restart ingestion
  - Health monitoring (CPU, memory, uptime)
  - Process status tracking
  - State machine integration

#### ProducerService
- **Location**: `backend/app/services/producer_service.py`
- **Purpose**: Wraps MediaSoupClient for producer management
- **Features**:
  - Create/close producers
  - Database persistence
  - Stats tracking
  - State transitions

#### ConsumerService
- **Location**: `backend/app/services/consumer_service.py`
- **Purpose**: Manages consumer sessions
- **Features**:
  - Heartbeat tracking (60s timeout)
  - Automatic stale consumer cleanup
  - Session statistics
  - Force close capability

#### RecordingManagementService
- **Location**: `backend/app/services/recording_management_service.py`
- **Purpose**: Manages HLS recordings
- **Features**:
  - Disk usage monitoring
  - Automatic retention policy (7-day default)
  - Per-stream and global cleanup
  - Segment tracking

---

### 2. Health Monitoring API

**Location**: `backend/app/api/v2/health.py`

**Endpoints**:

```
GET  /v2/health/system                          # Overall system health
GET  /v2/health/streams/{stream_id}             # Stream-specific health
GET  /v2/health/ingestion                       # All FFmpeg processes
GET  /v2/health/producers                       # All MediaSoup producers
GET  /v2/health/consumers                       # All active consumers
GET  /v2/health/consumers/{consumer_id}         # Consumer session stats
POST /v2/health/consumers/{consumer_id}/heartbeat  # Record heartbeat
GET  /v2/health/recordings                      # All recordings stats
GET  /v2/health/recordings/{stream_id}          # Stream recording stats
POST /v2/health/recordings/{stream_id}/cleanup  # Clean stream recordings
POST /v2/health/recordings/cleanup              # Clean all recordings
```

---

### 3. Prometheus Metrics Export

**Location**: `backend/app/metrics/prometheus.py`

**Endpoint**: `GET /v2/metrics` (Prometheus scrape target)

**Metrics Exported**:

```
# Streams
vas_streams_total{state}
vas_stream_uptime_seconds{stream_id, stream_name}

# Producers
vas_producers_total{state}
vas_producer_uptime_seconds{producer_id, stream_id}

# Consumers
vas_consumers_total{state}
vas_consumer_session_duration_seconds{consumer_id, stream_id, client_id}
vas_active_consumers{stream_id}

# FFmpeg
vas_ffmpeg_process_cpu_percent{stream_id}
vas_ffmpeg_process_memory_mb{stream_id}
vas_ffmpeg_processes_healthy

# API
vas_api_request_duration_seconds{endpoint, method, status_code}
vas_api_requests_total{endpoint, method, status_code}
```

---

## Quick Start Examples

### Check System Health

```bash
curl http://localhost:8080/v2/health/system
```

**Response**:
```json
{
  "status": "healthy",
  "components": {
    "database": "healthy",
    "ffmpeg": {
      "status": "healthy",
      "active_processes": 5
    },
    "mediasoup": {
      "status": "healthy",
      "active_producers": 5
    }
  },
  "streams": {
    "total": 10,
    "by_state": {
      "live": 5,
      "stopped": 3,
      "error": 0
    }
  },
  "consumers": {
    "active": 8
  }
}
```

---

### Check Stream Health

```bash
curl http://localhost:8080/v2/health/streams/{stream_id}
```

**Response**:
```json
{
  "stream_id": "abc-123",
  "name": "Front Door Camera",
  "state": "live",
  "ffmpeg": {
    "is_healthy": true,
    "status": "running",
    "pid": 12345,
    "cpu_percent": 15.3,
    "memory_mb": 245.6,
    "uptime_seconds": 3600
  },
  "producer": {
    "producer_id": "prod-456",
    "state": "active",
    "ssrc": 2622226488,
    "uptime_seconds": 3550
  },
  "consumers": {
    "total_consumers": 2,
    "active_consumers": 2
  }
}
```

---

### Consumer Heartbeat

```python
import requests
import asyncio

async def maintain_heartbeat(consumer_id: str, access_token: str):
    """Send heartbeat every 30 seconds to prevent timeout."""
    headers = {"Authorization": f"Bearer {access_token}"}

    while True:
        try:
            response = requests.post(
                f"http://vas-ms:8080/v2/health/consumers/{consumer_id}/heartbeat",
                headers=headers
            )
            print(f"Heartbeat: {response.status_code}")
        except Exception as e:
            print(f"Error: {e}")

        await asyncio.sleep(30)  # Send every 30s (timeout is 60s)
```

---

### Recording Cleanup

```bash
# Clean recordings older than 7 days for a specific stream
curl -X POST \
  "http://localhost:8080/v2/health/recordings/{stream_id}/cleanup?retention_days=7" \
  -H "Authorization: Bearer $TOKEN"

# Clean all streams
curl -X POST \
  "http://localhost:8080/v2/health/recordings/cleanup?retention_days=7" \
  -H "Authorization: Bearer $TOKEN"
```

**Response**:
```json
{
  "stream_id": "abc-123",
  "retention_days": 7,
  "deleted_count": 450,
  "deleted_size_mb": 2340.5,
  "deleted_size_gb": 2.28,
  "cutoff_time": "2026-01-02T10:30:00Z"
}
```

---

### Prometheus Metrics

```bash
curl http://localhost:8080/v2/metrics
```

**Response** (Prometheus text format):
```
# HELP vas_streams_total Total number of streams by state
# TYPE vas_streams_total gauge
vas_streams_total{state="live"} 5.0
vas_streams_total{state="stopped"} 3.0
vas_streams_total{state="error"} 0.0

# HELP vas_ffmpeg_process_cpu_percent FFmpeg process CPU usage percentage
# TYPE vas_ffmpeg_process_cpu_percent gauge
vas_ffmpeg_process_cpu_percent{stream_id="abc-123"} 15.3

# HELP vas_active_consumers Number of active consumers per stream
# TYPE vas_active_consumers gauge
vas_active_consumers{stream_id="abc-123"} 2.0
```

---

## Prometheus Configuration

**prometheus.yml**:
```yaml
scrape_configs:
  - job_name: 'vas-ms-v2'
    scrape_interval: 15s
    static_configs:
      - targets: ['vas-ms:8080']
    metrics_path: '/v2/metrics'
```

**Alerting Rules**:
```yaml
groups:
  - name: vas_alerts
    rules:
      - alert: StreamDown
        expr: vas_streams_total{state="error"} > 0
        for: 5m
        annotations:
          summary: "Streams in error state detected"

      - alert: HighFFmpegCPU
        expr: vas_ffmpeg_process_cpu_percent > 80
        for: 10m
        annotations:
          summary: "FFmpeg process using >80% CPU"

      - alert: NoActiveConsumers
        expr: sum(vas_active_consumers) == 0
        for: 15m
        annotations:
          summary: "No active consumers for 15 minutes"
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     OBSERVABILITY LAYER                     │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐        │
│  │   Health    │  │ Prometheus  │  │  Recording   │        │
│  │ Monitoring  │  │   Metrics   │  │  Management  │        │
│  │     API     │  │   Export    │  │    API       │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘        │
└─────────┼─────────────────┼─────────────────┼───────────────┘
          │                 │                 │
┌─────────▼─────────────────▼─────────────────▼───────────────┐
│                    WRAPPER SERVICES                         │
│                  (BLACK BOX WRAPPERS)                       │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐     │
│  │   Stream     │  │   Producer   │  │   Consumer    │     │
│  │  Ingestion   │  │   Service    │  │   Service     │     │
│  │   Service    │  │              │  │               │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬────────┘     │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          │ DOES NOT MODIFY  │ DOES NOT MODIFY  │
          │     (wraps)      │     (wraps)      │
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼─────────────┐
│              DATA PLANE (BLACK BOX - STABLE)                │
│                                                             │
│     FFmpeg Pipeline     MediaSoup SFU     Consumer WebRTC  │
│     RTSP → RTP/HLS     Producer/Router    Transport        │
└─────────────────────────────────────────────────────────────┘
```

---

## BLACK BOX Principle Verification

✅ **FFmpeg Commands**: UNCHANGED (wrapped by StreamIngestionService)
✅ **MediaSoup Configurations**: UNCHANGED (wrapped by ProducerService)
✅ **SSRC Capture Logic**: UNCHANGED (used as-is)
✅ **Codec Parameters**: UNCHANGED (used as-is)

**All wrapper services provide:**
- Lifecycle management (start/stop/restart)
- Health monitoring (CPU, memory, uptime)
- Database persistence
- State machine integration

**WITHOUT modifying the underlying data plane.**

---

## Dependencies

Add to `requirements.txt`:
```
prometheus-client==0.19.0
psutil==5.9.8
```

Install:
```bash
pip install -r requirements.txt
```

---

## Testing

```bash
# System health
curl http://localhost:8080/v2/health/system

# Stream health
curl http://localhost:8080/v2/health/streams/{stream_id}

# Prometheus metrics
curl http://localhost:8080/v2/metrics

# Recordings stats
curl http://localhost:8080/v2/health/recordings

# Consumer heartbeat
curl -X POST \
  http://localhost:8080/v2/health/consumers/{consumer_id}/heartbeat \
  -H "Authorization: Bearer $TOKEN"
```

---

## Operational Tasks

### Monitor System Health
```bash
watch -n 5 curl -s http://localhost:8080/v2/health/system | jq
```

### Clean Old Recordings
```bash
# Manual cleanup (run weekly)
curl -X POST \
  "http://localhost:8080/v2/health/recordings/cleanup?retention_days=7" \
  -H "Authorization: Bearer $TOKEN"

# Automatic cleanup runs hourly in background
```

### Track Consumer Sessions
```bash
# List all active consumers
curl http://localhost:8080/v2/health/consumers

# Check specific consumer
curl http://localhost:8080/v2/health/consumers/{consumer_id}
```

---

## Summary

Phase 3 provides:

✅ **Comprehensive observability** via health monitoring and Prometheus metrics
✅ **Operational excellence** via recording management and cleanup
✅ **Session management** via consumer heartbeats and automatic cleanup
✅ **BLACK BOX compliance** - data plane remains untouched

The system is now **production-ready** with full monitoring, alerting, and operational capabilities for third-party integration.

For detailed documentation, see [PHASE_3_COMPLETE.md](PHASE_3_COMPLETE.md).
