"""Stream schemas for V2 API."""
from pydantic import BaseModel, Field, UUID4
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class StreamStateEnum(str, Enum):
    """Stream state enum for API responses."""
    INITIALIZING = "initializing"
    READY = "ready"
    LIVE = "live"
    ERROR = "error"
    STOPPED = "stopped"
    CLOSED = "closed"


class StreamCreate(BaseModel):
    """Request to create a new stream."""
    name: str = Field(..., description="Stream name", max_length=255)
    camera_id: UUID4 = Field(..., description="Source camera UUID")
    access_policy: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Access control policy"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Front Door Camera Stream",
                "camera_id": "31f38047-59eb-4735-85d9-ae754156e6c5",
                "access_policy": {"public": False, "allowed_scopes": ["stream.consume"]},
                "metadata": {"location": "Building A, Floor 1"}
            }
        }
    }


class ProducerInfo(BaseModel):
    """Producer information."""
    id: UUID4
    mediasoup_id: str
    ssrc: int
    state: str
    created_at: datetime


class ConsumerInfo(BaseModel):
    """Consumer information."""
    id: UUID4
    client_id: str
    state: str
    connected_at: datetime


class StreamHealthResponse(BaseModel):
    """Stream health metrics."""
    status: str = Field(..., description="Health status: healthy, degraded, unhealthy")
    state: StreamStateEnum
    producer: Optional[Dict[str, Any]] = Field(default=None, description="Producer health metrics")
    consumers: Dict[str, Any] = Field(..., description="Consumer statistics")
    ffmpeg: Optional[Dict[str, Any]] = Field(default=None, description="FFmpeg process status")
    recording: Optional[Dict[str, Any]] = Field(default=None, description="Recording status")


class StreamResponse(BaseModel):
    """Stream details response."""
    id: UUID4
    name: str
    camera_id: UUID4
    state: StreamStateEnum
    codec_config: Dict[str, Any]
    access_policy: Dict[str, Any]
    metadata: Dict[str, Any]
    producer: Optional[ProducerInfo] = None
    consumers: Dict[str, Any] = Field(
        ...,
        description="Consumer statistics"
    )
    endpoints: Dict[str, str] = Field(
        ...,
        description="Available endpoints for this stream"
    )
    created_at: datetime
    uptime_seconds: Optional[int] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "aaaaaaaa-0000-0000-0000-000000000001",
                "name": "Front Door Camera",
                "camera_id": "31f38047-59eb-4735-85d9-ae754156e6c5",
                "state": "live",
                "codec_config": {"video": {"mimeType": "video/H264", "clockRate": 90000}},
                "access_policy": {"public": False},
                "metadata": {"location": "Building A"},
                "producer": {
                    "id": "bbbbbbbb-0000-0000-0000-000000000001",
                    "mediasoup_id": "producer-123",
                    "ssrc": 2622226488,
                    "state": "active",
                    "created_at": "2026-01-09T12:00:00Z"
                },
                "consumers": {"active": 3, "total_created": 10},
                "endpoints": {
                    "webrtc": "/v2/streams/aaaaaaaa-0000-0000-0000-000000000001/consume",
                    "hls": "/v2/streams/aaaaaaaa-0000-0000-0000-000000000001/hls",
                    "health": "/v2/streams/aaaaaaaa-0000-0000-0000-000000000001/health"
                },
                "created_at": "2026-01-09T12:00:00Z",
                "uptime_seconds": 3600
            }
        }
    }


class StreamListItem(BaseModel):
    """Stream list item (condensed)."""
    id: UUID4
    name: str
    camera_id: UUID4
    state: StreamStateEnum
    endpoints: Dict[str, str]
    created_at: datetime


class StreamListResponse(BaseModel):
    """List of streams with pagination."""
    streams: List[StreamListItem]
    pagination: Dict[str, int] = Field(
        ...,
        description="Pagination info"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "streams": [
                    {
                        "id": "aaaaaaaa-0000-0000-0000-000000000001",
                        "name": "Front Door",
                        "camera_id": "31f38047-59eb-4735-85d9-ae754156e6c5",
                        "state": "live",
                        "endpoints": {
                            "webrtc": "/v2/streams/aaaaaaaa-0000-0000-0000-000000000001/consume"
                        },
                        "created_at": "2026-01-09T12:00:00Z"
                    }
                ],
                "pagination": {
                    "total": 10,
                    "limit": 20,
                    "offset": 0
                }
            }
        }
    }
