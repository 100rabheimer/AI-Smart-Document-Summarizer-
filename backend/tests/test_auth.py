import uuid
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import status, HTTPException

from app.models.user import User
from app.routers.auth import login_google, get_me, logout
from app.services.auth_service import AuthService


def test_hash_token_consistency():
    """Verify that hashing a session token is deterministic."""
    token = "secret-test-token-12345"
    h1 = AuthService.hash_token(token)
    h2 = AuthService.hash_token(token)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest length


def test_generate_google_auth_url():
    """Verify that the generated Google OAuth URL contains required query parameters."""
    url, state = AuthService.generate_google_auth_url(state="custom-state-token")
    assert "accounts.google.com" in url
    assert "response_type=code" in url
    assert "state=custom-state-token" in url
    assert "openid" in url


@pytest.mark.asyncio
async def test_login_google_endpoint():
    """Verify that GET /auth/login/google returns an authorization URL."""
    res = await login_google()
    assert "accounts.google.com" in res.url
    assert len(res.state) > 0


@pytest.mark.asyncio
async def test_get_me_unauthorized():
    """Verify that accessing protected /auth/me without a user raises 401."""
    # When dependency get_current_user fails, it raises HTTPException 401
    from app.core.dependencies import get_current_user
    from fastapi import Request

    # Mock request without cookies or auth header
    mock_request = Request({"type": "http", "headers": [], "cookies": {}})
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request=mock_request, db=AsyncMock(), bearer=None)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_me_success():
    """Verify that /auth/me returns the authenticated user's details."""
    user_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        email="learner@docmind.io",
        name="DocMind Learner",
        avatar_url="https://lh3.googleusercontent.com/test",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    res = await get_me(current_user=mock_user)
    assert res.email == "learner@docmind.io"
    assert res.name == "DocMind Learner"
    assert res.id == user_id


@pytest.mark.asyncio
async def test_logout():
    """Verify that logout successfully revokes session and instructs cookie deletion."""
    from fastapi import Response, Request

    mock_db = AsyncMock()
    # Starlette Request scope receives headers as raw byte tuples
    mock_request = Request({
        "type": "http",
        "headers": [(b"cookie", b"docmind_session=test-token")],
    })
    mock_response = Response()
    mock_user = User(id=uuid.uuid4(), email="test@docmind.io", name="Test", is_active=True)

    with patch("app.routers.auth.AuthService.logout_session", new_callable=AsyncMock) as mock_logout:
        mock_logout.return_value = True
        result = await logout(
            request=mock_request,
            response=mock_response,
            db=mock_db,
            current_user=mock_user,
        )
        assert result["message"] == "Logged out successfully"
        mock_logout.assert_called_once_with(db=mock_db, raw_token="test-token")
