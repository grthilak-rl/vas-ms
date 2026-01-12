"""
Unit Tests for JWT Authentication Service
==========================================

Tests JWT token generation, validation, and refresh functionality.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Import the auth service (adjust path as needed)
# from app.services.auth_service import AuthService, InvalidCredentials, TokenExpired


class TestJWTAuthentication:
    """Test suite for JWT authentication"""

    @pytest.fixture
    def mock_auth_service(self):
        """Mock auth service for testing"""
        # This is a placeholder - replace with actual auth service import
        class MockAuthService:
            SECRET_KEY = "test_secret_key"
            ALGORITHM = "HS256"

            def generate_token(self, client_id: str, client_secret: str, expires_in: int = 3600):
                """Generate a mock JWT token"""
                import jwt
                from datetime import datetime, timedelta

                payload = {
                    "sub": client_id,
                    "exp": datetime.utcnow() + timedelta(seconds=expires_in),
                    "iat": datetime.utcnow(),
                    "scopes": ["streams:read", "streams:consume"]
                }

                token = jwt.encode(payload, self.SECRET_KEY, algorithm=self.ALGORITHM)

                return {
                    "access_token": token,
                    "token_type": "Bearer",
                    "expires_in": expires_in
                }

            def validate_token(self, token: str):
                """Validate JWT token"""
                import jwt

                try:
                    payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
                    return payload
                except jwt.ExpiredSignatureError:
                    raise Exception("Token expired")
                except jwt.InvalidTokenError:
                    raise Exception("Invalid token")

        return MockAuthService()

    def test_token_generation_returns_valid_structure(self, mock_auth_service):
        """Test that token generation returns the correct structure"""
        result = mock_auth_service.generate_token("test-client", "test-secret")

        assert "access_token" in result
        assert "token_type" in result
        assert "expires_in" in result
        assert result["token_type"] == "Bearer"
        assert result["expires_in"] == 3600
        assert len(result["access_token"]) > 0

    def test_token_payload_contains_required_claims(self, mock_auth_service):
        """Test that JWT payload contains required claims"""
        token_data = mock_auth_service.generate_token("test-client", "test-secret")
        payload = mock_auth_service.validate_token(token_data["access_token"])

        assert "sub" in payload  # Subject (client_id)
        assert "exp" in payload  # Expiration time
        assert "iat" in payload  # Issued at
        assert "scopes" in payload

        assert payload["sub"] == "test-client"
        assert isinstance(payload["scopes"], list)
        assert "streams:read" in payload["scopes"]

    def test_token_validation_with_valid_token(self, mock_auth_service):
        """Test validation of a valid token"""
        token_data = mock_auth_service.generate_token("test-client", "test-secret")

        # Should not raise exception
        payload = mock_auth_service.validate_token(token_data["access_token"])
        assert payload["sub"] == "test-client"

    def test_token_validation_with_expired_token(self, mock_auth_service):
        """Test that expired tokens are rejected"""
        # Generate token with 1-second expiry
        token_data = mock_auth_service.generate_token("test-client", "test-secret", expires_in=1)

        # Wait for expiry
        time.sleep(2)

        # Should raise exception
        with pytest.raises(Exception) as exc_info:
            mock_auth_service.validate_token(token_data["access_token"])

        assert "expired" in str(exc_info.value).lower()

    def test_token_validation_with_invalid_signature(self, mock_auth_service):
        """Test that tokens with invalid signatures are rejected"""
        fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmYWtlIn0.fake_signature"

        with pytest.raises(Exception) as exc_info:
            mock_auth_service.validate_token(fake_token)

        assert "invalid" in str(exc_info.value).lower()

    def test_token_expiration_time_is_correct(self, mock_auth_service):
        """Test that token expiration time matches requested duration"""
        token_data = mock_auth_service.generate_token("test-client", "test-secret", expires_in=7200)
        payload = mock_auth_service.validate_token(token_data["access_token"])

        # Check expiration is approximately 7200 seconds from now
        exp_time = datetime.fromtimestamp(payload["exp"])
        iat_time = datetime.fromtimestamp(payload["iat"])
        delta = (exp_time - iat_time).total_seconds()

        assert 7195 <= delta <= 7205  # Allow 5-second margin

    def test_multiple_scopes_in_token(self, mock_auth_service):
        """Test that multiple scopes are preserved in token"""
        # This would require extending mock to accept scopes parameter
        token_data = mock_auth_service.generate_token("test-client", "test-secret")
        payload = mock_auth_service.validate_token(token_data["access_token"])

        scopes = payload["scopes"]
        assert len(scopes) >= 1
        assert "streams:read" in scopes


class TestScopeValidation:
    """Test suite for scope validation"""

    def test_scope_checking(self):
        """Test scope validation logic"""

        def has_scope(scopes: list, required_scope: str) -> bool:
            """Check if required scope is in scopes list"""
            return required_scope in scopes

        user_scopes = ["streams:read", "bookmarks:write", "snapshots:read"]

        assert has_scope(user_scopes, "streams:read") == True
        assert has_scope(user_scopes, "bookmarks:write") == True
        assert has_scope(user_scopes, "streams:write") == False
        assert has_scope(user_scopes, "bookmarks:delete") == False

    def test_wildcard_scope(self):
        """Test wildcard scope matching"""

        def has_scope_with_wildcard(scopes: list, required_scope: str) -> bool:
            """Check scope with wildcard support"""
            # Check exact match
            if required_scope in scopes:
                return True

            # Check wildcard (e.g., "streams:*" matches "streams:read")
            resource = required_scope.split(":")[0]
            wildcard = f"{resource}:*"
            return wildcard in scopes

        user_scopes = ["streams:*", "bookmarks:read"]

        assert has_scope_with_wildcard(user_scopes, "streams:read") == True
        assert has_scope_with_wildcard(user_scopes, "streams:write") == True
        assert has_scope_with_wildcard(user_scopes, "bookmarks:read") == True
        assert has_scope_with_wildcard(user_scopes, "bookmarks:write") == False


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
