"""Stream state transition audit log."""
from sqlalchemy import Column, String, ForeignKey, Text, JSON, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base
import uuid


class StreamStateTransition(Base):
    """
    Audit log for stream state transitions.

    Tracks all state changes for streams, including the reason for
    the transition and any associated metadata. This is critical for
    debugging, compliance, and understanding stream lifecycle.

    Example transitions:
    - None → initializing (stream creation)
    - initializing → ready (SSRC captured, producer created)
    - ready → live (FFmpeg started, RTP flowing)
    - live → error (FFmpeg crashed)
    - error → live (auto-restart succeeded)
    - live → stopped (manual stop)
    """

    __tablename__ = "stream_state_transitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stream_id = Column(
        UUID(as_uuid=True),
        ForeignKey("streams.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # State transition
    from_state = Column(String(20), nullable=True)  # Null for initial creation
    to_state = Column(String(20), nullable=False, index=True)

    # Context
    reason = Column(Text, nullable=True)  # Human-readable reason
    transition_metadata = Column("metadata", JSON, nullable=True, default={})  # Additional context

    # Timestamp
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True
    )

    # Relationships
    stream = relationship("Stream", back_populates="state_transitions")

    def __repr__(self):
        return f"<StreamStateTransition {self.from_state} → {self.to_state} at {self.created_at}>"
