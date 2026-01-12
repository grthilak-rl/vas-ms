"""Snapshot model for single frame captures."""
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from database import Base
import uuid


class Snapshot(Base):
    """
    Represents a single-frame capture from a stream.

    Use cases:
    - Thumbnail generation
    - Quick visual verification
    - Lower bandwidth than bookmarks
    - Frame-level AI analysis

    Snapshots are stream-scoped (not device-scoped) to support multiple
    streams per camera and clean cascade deletion.
    """

    __tablename__ = "snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Stream association (CHANGED from device_id)
    stream_id = Column(
        UUID(as_uuid=True),
        ForeignKey("streams.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Temporal
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # File
    file_path = Column(String(512), nullable=False)

    # Metadata
    source = Column(String(20), nullable=False)          # 'live' | 'historical'
    created_by = Column(String(100), nullable=True, index=True)  # "ruth-ai" | "manual"
    format = Column(String(10), default="jpg")
    file_size = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    # Extended metadata (flexible JSON)
    extra_metadata = Column("metadata", JSONB, nullable=True, default={})

    # Optional: user_id for future auth
    user_id = Column(UUID(as_uuid=True), nullable=True)

    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    stream = relationship("Stream", back_populates="snapshots")

    def __repr__(self):
        return f"<Snapshot {self.id} from stream {self.stream_id} at {self.timestamp}>"



