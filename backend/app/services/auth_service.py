import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from typing import Optional, Tuple
import httpx

from app.core.config import get_settings
from app.repositories.user_repo import UserRepository
from app.models.user import User, UserSession
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"

SESSION_COOKIE_NAME = "docmind_session"
SESSION_DURATION_DAYS = 7


class AuthService:
    """Service orchestrating Google OAuth 2.0 flow and user sessions."""

    @staticmethod
    def hash_token(token: str) -> str:
        """Computes SHA-256 hash of raw session token for secure DB storage."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_google_auth_url(state: Optional[str] = None) -> Tuple[str, str]:
        """
        Builds Google OAuth consent URL with state token for CSRF protection.
        Returns: (authorization_url, csrf_state)
        """
        csrf_state = state or secrets.token_urlsafe(16)
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID or "placeholder-google-client-id",
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "state": csrf_state,
            "prompt": "select_account",
        }
        auth_url = f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"
        return auth_url, csrf_state

    @staticmethod
    async def exchange_google_code(code: str) -> dict:
        """
        Exchanges authorization code for Google access token and user identity.
        """
        token_payload = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            token_response = await client.post(GOOGLE_TOKEN_ENDPOINT, data=token_payload)
            if token_response.status_code != 200:
                raise ValueError(f"Failed to exchange code with Google: {token_response.text}")
            
            token_data = token_response.json()
            access_token = token_data.get("access_token")

            # Fetch Google user profile
            headers = {"Authorization": f"Bearer {access_token}"}
            userinfo_response = await client.get(GOOGLE_USERINFO_ENDPOINT, headers=headers)
            if userinfo_response.status_code != 200:
                raise ValueError(f"Failed to fetch userinfo from Google: {userinfo_response.text}")

            return userinfo_response.json()

    @classmethod
    async def process_oauth_login(
        cls,
        db: AsyncSession,
        code: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[User, str]:
        """
        Full OAuth completion flow:
        1. Exchange code with Google.
        2. Upsert user in PostgreSQL.
        3. Create new hashed session in PostgreSQL.
        Returns: (User, raw_session_token)
        """
        google_profile = await cls.exchange_google_code(code)
        
        email = google_profile["email"]
        name = google_profile.get("name") or email.split("@")[0]
        avatar_url = google_profile.get("picture")

        # Upsert user record
        user = await UserRepository.upsert_user(
            db=db,
            email=email,
            name=name,
            avatar_url=avatar_url,
        )

        # Generate session
        raw_session_token = secrets.token_urlsafe(32)
        token_hash = cls.hash_token(raw_session_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_DURATION_DAYS)

        await UserRepository.create_session(
            db=db,
            user_id=user.id,
            session_token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return user, raw_session_token

    @classmethod
    async def authenticate_session(
        cls,
        db: AsyncSession,
        raw_token: str
    ) -> Optional[User]:
        """
        Validates raw token against active hashed sessions and returns authenticated User.
        """
        token_hash = cls.hash_token(raw_token)
        session: Optional[UserSession] = await UserRepository.get_active_session(db, token_hash)
        if not session:
            return None

        return await UserRepository.get_by_id(db, session.user_id)

    @classmethod
    async def logout_session(
        cls,
        db: AsyncSession,
        raw_token: str
    ) -> bool:
        """Revokes active session."""
        token_hash = cls.hash_token(raw_token)
        return await UserRepository.revoke_session(db, token_hash)
