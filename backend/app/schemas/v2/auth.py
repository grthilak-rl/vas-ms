"""Authentication schemas for V2 API."""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class TokenRequest(BaseModel):
    """Request for JWT access token."""
    client_id: str = Field(..., description="Client identifier")
    client_secret: str = Field(..., description="Client secret")
    scopes: Optional[List[str]] = Field(default=None, description="Requested scopes (optional)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "client_id": "ruth-ai",
                "client_secret": "secret_key_here",
                "scopes": ["stream.read", "stream.consume", "bookmark.create"]
            }
        }
    }


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Expiration time in seconds")
    refresh_token: str = Field(..., description="Refresh token for obtaining new access tokens")
    scopes: List[str] = Field(..., description="Granted scopes")

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "refresh_token_here",
                "scopes": ["stream.read", "stream.consume"]
            }
        }
    }


class RefreshTokenRequest(BaseModel):
    """Request to refresh access token."""
    refresh_token: str = Field(..., description="Refresh token")


class ClientCreateRequest(BaseModel):
    """Request to create a new API client."""
    client_id: str = Field(..., description="Unique client identifier")
    scopes: List[str] = Field(..., description="Allowed scopes for this client")
    expires_at: Optional[datetime] = Field(default=None, description="Optional expiration datetime")

    model_config = {
        "json_schema_extra": {
            "example": {
                "client_id": "ruth-ai-prod",
                "scopes": ["stream.read", "stream.consume", "bookmark.create", "snapshot.create"],
                "expires_at": None
            }
        }
    }


class ClientCreateResponse(BaseModel):
    """Response after creating API client."""
    client_id: str
    client_secret: str = Field(..., description="Client secret (shown only once!)")
    scopes: List[str]
    created_at: Optional[str] = None  # ISO format string

    model_config = {
        "json_schema_extra": {
            "example": {
                "client_id": "ruth-ai-prod",
                "client_secret": "generated_secret_SAVE_THIS",
                "scopes": ["stream.read", "stream.consume"],
                "created_at": "2026-01-09T12:00:00Z"
            }
        }
    }
