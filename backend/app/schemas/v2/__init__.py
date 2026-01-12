"""V2 API Pydantic schemas."""
from app.schemas.v2.auth import (
    TokenRequest,
    TokenResponse,
    ClientCreateRequest,
    ClientCreateResponse
)
from app.schemas.v2.stream import (
    StreamCreate,
    StreamResponse,
    StreamListResponse,
    StreamHealthResponse,
    ProducerInfo,
    ConsumerInfo
)
from app.schemas.v2.consumer import (
    ConsumerAttachRequest,
    ConsumerAttachResponse,
    ConsumerConnectRequest,
    ICECandidateRequest
)
from app.schemas.v2.bookmark import (
    BookmarkCreate,
    BookmarkResponse,
    BookmarkListResponse
)
from app.schemas.v2.snapshot import (
    SnapshotCreate,
    SnapshotResponse,
    SnapshotListResponse
)

__all__ = [
    # Auth
    "TokenRequest",
    "TokenResponse",
    "ClientCreateRequest",
    "ClientCreateResponse",
    # Streams
    "StreamCreate",
    "StreamResponse",
    "StreamListResponse",
    "StreamHealthResponse",
    "ProducerInfo",
    "ConsumerInfo",
    # Consumers
    "ConsumerAttachRequest",
    "ConsumerAttachResponse",
    "ConsumerConnectRequest",
    "ICECandidateRequest",
    # Bookmarks
    "BookmarkCreate",
    "BookmarkResponse",
    "BookmarkListResponse",
    # Snapshots
    "SnapshotCreate",
    "SnapshotResponse",
    "SnapshotListResponse",
]
