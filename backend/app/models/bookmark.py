"""Bookmark model for saved video clips (6-second captures)."""
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from database import Base
import uuid


class Bookmark(Base):
    """
    Represents a temporal annotation on a stream - a 6-second video clip
    marking an event of interest.

    Use cases:
    - AI event detection (person detected, anomaly detected)
    - Manual user annotations
    - Training dataset generation
    - Incident review

    Bookmarks are stream-scoped (not device-scoped) to support multiple
    streams per camera and clean cascade deletion.
    """

    __tablename__ = "bookmarks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Stream association (CHANGED from device_id)
    stream_id = Column(
        UUID(as_uuid=True),
        ForeignKey("streams.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Temporal bounds
    center_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    start_timestamp = Column(DateTime(timezone=True), nullable=False)   # center - 3s
    end_timestamp = Column(DateTime(timezone=True), nullable=False)     # center + 3s

    # File paths
    video_file_path = Column(String(512), nullable=False)
    thumbnail_path = Column(String(512), nullable=True)

    # Metadata (machine-readable)
    label = Column(String(255), nullable=True)           # "Person detected"
    source = Column(String(20), nullable=False)          # 'live' | 'historical'
    created_by = Column(String(100), nullable=True, index=True)  # "ruth-ai" | "manual" | "operator-john"
    confidence = Column(Float, nullable=True)            # AI confidence (0.0-1.0)
    event_type = Column(String(50), nullable=True, index=True)   # "person" | "vehicle" | "anomaly"
    tags = Column(ARRAY(String), nullable=True, default=[])      # ["security", "urgent"]

    # Technical metadata
    duration = Column(Integer, default=6)
    video_format = Column(String(10), default="mp4")
    file_size = Column(Integer, nullable=True)

    # Extended metadata (flexible JSON for AI bounding boxes, etc.)
    extra_metadata = Column("metadata", JSONB, nullable=True, default={})

    # Optional: user_id for future auth
    user_id = Column(UUID(as_uuid=True), nullable=True)

    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    stream = relationship("Stream", back_populates="bookmarks")

    def __repr__(self):
        return f"<Bookmark {self.label or 'Unlabeled'} at {self.center_timestamp}>"
