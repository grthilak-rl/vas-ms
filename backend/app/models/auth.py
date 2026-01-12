"""Authentication models for JWT tokens."""
from sqlalchemy import Column, String, DateTime, Boolean, ARRAY, func
from sqlalchemy.dialects.postgresql import UUID
from database import Base
import uuid


class JWTToken(Base):
    """
    Represents a JWT access token for API authentication.

    Tokens are used for machine-to-machine authentication (e.g., Ruth-AI).
    Each token has scopes that define what operations are allowed.
    """

    __tablename__ = "jwt_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Client identification
    client_id = Column(String(255), nullable=False, unique=True, index=True)
    client_secret_hash = Column(String(255), nullable=False)  # Hashed secret

    # Token scopes (permissions)
    scopes = Column(ARRAY(String), nullable=False, default=[])  # ["stream.read", "stream.consume", "bookmark.create"]

    # Status
    is_active = Column(Boolean, default=True, index=True)

    # Expiry
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Null = never expires

    # Usage tracking
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<JWTToken {self.client_id} scopes={self.scopes}>"


class RefreshToken(Base):
    """
    Represents a refresh token for obtaining new access tokens.

    Refresh tokens are long-lived (days/weeks) while access tokens
    are short-lived (hours). This allows token rotation without
    requiring client_secret on every request.
    """

    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)

    # Associated client
    client_id = Column(String(255), nullable=False, index=True)

    # Status
    is_revoked = Column(Boolean, default=False, index=True)

    # Expiry
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    used_at = Column(DateTime(timezone=True), nullable=True)  # Last time used to refresh

    def __repr__(self):
        return f"<RefreshToken {self.id} client={self.client_id}>"
