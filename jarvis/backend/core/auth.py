"""
Authentication middleware for JARVIS API.
Validates the per-launch control token on all requests.
"""

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional


class ControlTokenSecurity:
    """Security scheme for control token validation."""
    
    def __init__(self, token: str):
        """Initialize with the expected control token.
        
        Args:
            token: The per-launch control token to validate against
        """
        self.expected_token = token
        self.scheme = HTTPBearer(auto_error=False)
    
    async def __call__(self, request: Request) -> bool:
        """Validate the control token from request header.
        
        Args:
            request: FastAPI request object
            
        Returns:
            True if token is valid
            
        Raises:
            HTTPException: If token is missing or invalid
        """
        # Check for X-Control-Token header
        token = request.headers.get("X-Control-Token")
        
        if not token:
            # Also check Authorization header as fallback
            credentials: Optional[HTTPAuthorizationCredentials] = await self.scheme(request)
            if credentials:
                token = credentials.credentials
        
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token"
            )
        
        if token != self.expected_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        return True


def create_auth_dependency(token: str) -> ControlTokenSecurity:
    """Create an authentication dependency for FastAPI routes.
    
    Args:
        token: The per-launch control token
        
    Returns:
        ControlTokenSecurity instance
    """
    return ControlTokenSecurity(token)
