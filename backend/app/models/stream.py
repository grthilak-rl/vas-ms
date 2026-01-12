"""Stream model for active video streams."""
from sqlalchemy import Column, String, ForeignKey, JSON, Enum as SQLEnum, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base
import uuid
import enum


class StreamState(str, enum.Enum):
    """Stream state enum.

    State machine:
    - INITIALIZING: Stream record created, resources being allocated
    - READY: SSRC captured, producer created, ready to start FFmpeg
    - LIVE: FFmpeg running, RTP packets flowing, consumers can attach
    - ERROR: FFmpeg crashed, RTP timeout, or other failure
    - STOPPED: Manually stopped by user/system
    - CLOSED: Cleanup complete, stream archived
    """
    INITIALIZING = "initializing"
    READY = "ready"
    LIVE = "live"
    ERROR = "error"
    STOPPED = "stopped"
    CLOSED = "closed"


class Stream(Base):
    """
    Represents a video stream from a camera.

    Streams are the first-class abstraction in VAS-MS-V2. Each stream
    corresponds to one camera feed being converted from RTSP to WebRTC.

    Streams are persistent and independent of consumer presence.
    Multiple consumers can attach to one stream concurrently.
    """

    __tablename__ = "streams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Source camera (renamed from device_id for clarity)
    camera_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Basic info
    name = Column(String(255), nullable=False, index=True)

    # State (using enum for validation)
    state = Column(
        SQLEnum(StreamState, name="stream_state", create_type=True),
        nullable=False,
        default=StreamState.INITIALIZING,
        index=True
    )

    # Codec configuration
    codec_config = Column(JSON, nullable=False, default={})

    # Access control
    access_policy = Column(JSON, nullable=False, default={})

    # Extended metadata
    stream_metadata = Column("metadata", JSON, nullable=False, default={})

    # Timestamps
    created_at = Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at = Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now()
    )

    # Relationships
    camera = relationship("Device", backref="streams")
    producers = relationship(
        "Producer",
        back_populates="stream",
        cascade="all, delete-orphan"
    )
    consumers = relationship(
        "Consumer",
        back_populates="stream",
        cascade="all, delete-orphan"
    )
    state_transitions = relationship(
        "StreamStateTransition",
        back_populates="stream",
        cascade="all, delete-orphan",
        order_by="StreamStateTransition.created_at"
    )
    bookmarks = relationship(
        "Bookmark",
        back_populates="stream",
        cascade="all, delete-orphan"
    )
    snapshots = relationship(
        "Snapshot",
        back_populates="stream",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Stream {self.name} ({self.state.value})>"


