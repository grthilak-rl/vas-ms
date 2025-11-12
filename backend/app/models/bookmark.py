"""Bookmark model for saved video clips."""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Bookmark(BaseModel):
    """Represents a bookmark (±5 seconds around a timestamp)."""
    
    __tablename__ = "bookmarks"
    
    stream_id = Column(UUID(as_uuid=True), ForeignKey("streams.id"), nullable=False)
    name = Column(String(255), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    clip_url = Column(String(512), nullable=True)
    clip_duration = Column(Integer, default=10)  # ±5 seconds = 10 seconds total
    thumbnail_path = Column(String(512), nullable=True)
    
    # Relationships
    stream = relationship("Stream", backref="bookmarks")
    
    def __repr__(self):
        return f"<Bookmark {self.name} at {self.timestamp}>"



