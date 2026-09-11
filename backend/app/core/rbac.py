from enum import Enum
from typing import Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from app.core.security import decode_token

security_bearer = HTTPBearer(auto_error=False)


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    DEVELOPER = "DEVELOPER"
    VIEWER = "VIEWER"


ROLE_HIERARCHY = {
    UserRole.VIEWER: 10,
    UserRole.DEVELOPER: 20,
    UserRole.ADMIN: 30,
}


async def get_current_user_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer)
) -> dict:
    """Validate Bearer token and return JWT payload."""
    if not credentials:
        # Default mock admin user for convenient zero-auth testing if requested
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided."
        )
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("token_type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type: expected access token."
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please refresh your token."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}"
        )


def require_role(min_role: UserRole) -> Callable:
    """Dependency factory checking if current user has at least min_role privilege."""
    async def role_checker(payload: dict = Depends(get_current_user_payload)) -> dict:
        user_role_str = payload.get("role", UserRole.VIEWER.value)
        try:
            user_role = UserRole(user_role_str)
        except ValueError:
            user_role = UserRole.VIEWER

        user_level = ROLE_HIERARCHY.get(user_role, 0)
        required_level = ROLE_HIERARCHY.get(min_role, 0)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: '{min_role.value}' role required. Your role is '{user_role.value}'."
            )
        return payload
    return role_checker
