"""Snapshot schemas for V2 API."""
from pydantic import BaseModel, Field, UUID4
from typing import List, Optional, Dict, Any
from datetime import datetime


class SnapshotCreate(BaseModel):
    """Request to create a snapshot."""
    source: str = Field(..., description="Source: 'live' or 'historical'", pattern="^(live|historical)$")
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Timestamp (required for historical, auto for live)"
    )
    created_by: Optional[str] = Field(default=None, description="Creator identifier", max_length=100)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Extended metadata")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source": "live",
                    "created_by": "ruth-ai",
                    "metadata": {"frame_analysis": "No anomalies detected"}
                },
                {
                    "source": "historical",
                    "timestamp": "2026-01-08T14:23:45Z",
                    "created_by": "operator-john"
                }
            ]
        }
    }


class SnapshotResponse(BaseModel):
    """Snapshot response."""
    id: UUID4
    stream_id: UUID4
    timestamp: datetime
    source: str
    created_by: Optional[str]
    format: str
    file_size: Optional[int]
    width: Optional[int]
    height: Optional[int]
    image_url: Optional[str] = None
    status: str = "processing"  # "processing" or "ready"
    metadata: Dict[str, Any]
    created_at: datetime


class SnapshotListResponse(BaseModel):
    """List of snapshots with pagination."""
    snapshots: List[SnapshotResponse]
    pagination: Dict[str, int]

    model_config = {
        "json_schema_extra": {
            "example": {
                "snapshots": [
                    {
                        "id": "eeeeeeee-0000-0000-0000-000000000001",
                        "stream_id": "aaaaaaaa-0000-0000-0000-000000000001",
                        "timestamp": "2026-01-09T12:00:00Z",
                        "source": "live",
                        "created_by": "ruth-ai",
                        "format": "jpg",
                        "file_size": 245678,
                        "width": 1920,
                        "height": 1080,
                        "image_url": "/v2/snapshots/eeeeeeee-0000-0000-0000-000000000001/image",
                        "metadata": {},
                        "created_at": "2026-01-09T12:00:00Z"
                    }
                ],
                "pagination": {"total": 100, "limit": 50, "offset": 0}
            }
        }
    }
