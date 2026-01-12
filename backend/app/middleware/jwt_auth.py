"""JWT authentication middleware for V2 API."""
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Optional
from app.services.auth_service import auth_service
from loguru import logger

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict:
    """
    Extract and verify JWT token from Authorization header.

    Returns the decoded token payload containing client_id and scopes.

    Raises:
        HTTPException: 401 if token is invalid or expired
    """
    token = credentials.credentials

    try:
        payload = auth_service.verify_token(token)
        # Normalize: JWT uses 'sub' but code expects 'client_id'
        if 'sub' in payload and 'client_id' not in payload:
            payload['client_id'] = payload['sub']
        return payload
    except ValueError as e:
        logger.warning(f"Token verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_scope(required_scope: str):
    """
    Dependency factory to check if the authenticated client has required scope.

    Usage:
        @router.get("/streams", dependencies=[Depends(require_scope("streams:read"))])
        async def list_streams():
            ...

    Args:
        required_scope: The scope required to access the endpoint (e.g., "streams:read")

    Returns:
        A dependency function that validates scope

    Raises:
        HTTPException: 403 if client lacks required scope
    """
    def scope_checker(current_user: Dict = Depends(get_current_user)) -> Dict:
        if not auth_service.has_scope(current_user, required_scope):
            logger.warning(
                f"Client {current_user.get('client_id')} lacks required scope: {required_scope}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required scope: {required_scope}"
            )
        return current_user

    return scope_checker


def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[Dict]:
    """
    Optional authentication - returns user payload if token provided, None otherwise.

    Useful for endpoints that change behavior based on authentication but don't require it.

    Returns:
        Dict with token payload if authenticated, None otherwise
    """
    if credentials is None:
        return None

    try:
        payload = auth_service.verify_token(credentials.credentials)
        return payload
    except ValueError:
        return None
