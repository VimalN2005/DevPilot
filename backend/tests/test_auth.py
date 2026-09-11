import pytest
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password
)
from app.core.rbac import UserRole, ROLE_HIERARCHY


def test_password_hashing():
    pw = "SuperSecretPassword123!"
    h = hash_password(pw)
    assert h != pw
    assert verify_password(pw, h) is True
    assert verify_password("WrongPassword", h) is False


def test_jwt_access_token_lifecycle():
    data = {"sub": "user_123", "email": "dev@devpilot.ai", "role": "DEVELOPER"}
    token = create_access_token(data)
    assert isinstance(token, str)

    payload = decode_token(token)
    assert payload["sub"] == "user_123"
    assert payload["email"] == "dev@devpilot.ai"
    assert payload["role"] == "DEVELOPER"
    assert payload["token_type"] == "access"


def test_jwt_refresh_token_lifecycle():
    data = {"sub": "user_456", "email": "admin@devpilot.ai", "role": "ADMIN"}
    token = create_refresh_token(data)
    payload = decode_token(token)
    assert payload["sub"] == "user_456"
    assert payload["token_type"] == "refresh"


def test_rbac_hierarchy():
    assert ROLE_HIERARCHY[UserRole.ADMIN] > ROLE_HIERARCHY[UserRole.DEVELOPER]
    assert ROLE_HIERARCHY[UserRole.DEVELOPER] > ROLE_HIERARCHY[UserRole.VIEWER]
