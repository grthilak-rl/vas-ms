"""Producer model for MediaSoup producers."""
from sqlalchemy import Column, String, ForeignKey, BigInteger, JSON, Enum as SQLEnum, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base
import uuid
import enum


class ProducerState(str, enum.Enum):
    """Producer state enum."""
    CREATING = "creating"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class Producer(Base):
    """
    Represents a MediaSoup producer for a stream.

    Producers are the data plane components that receive RTP from FFmpeg
    and distribute to consumers via MediaSoup SFU.

    Lifecycle: creating → active → (paused) → closed
    """

    __tablename__ = "producers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stream_id = Column(
        UUID(as_uuid=True),
        ForeignKey("streams.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # MediaSoup identifiers
    mediasoup_producer_id = Column(String(255), unique=True, nullable=False, index=True)
    mediasoup_transport_id = Column(String(255), nullable=False)
    mediasoup_router_id = Column(String(255), nullable=False)

    # RTP parameters
    ssrc = Column(BigInteger, nullable=False)  # Synchronization Source identifier
    rtp_parameters = Column(JSON, nullable=False)  # Full RTP capabilities

    # State
    state = Column(
        SQLEnum(ProducerState, name="producer_state", create_type=True),
        nullable=False,
        default=ProducerState.CREATING,
        index=True
    )

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
    stream = relationship("Stream", back_populates="producers")

    def __repr__(self):
        return f"<Producer {self.id} stream={self.stream_id} state={self.state.value}>"
