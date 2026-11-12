from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services.auth_service import AuthService, SESSION_COOKIE_NAME

security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> User:
    """
    Dependency that enforces authentication on protected routes.
    Checks HTTP-only cookie first, falls back to Authorization Bearer header.
    Guarantees user_id is verified for strict multi-tenancy.
    """
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)

    if not raw_token and bearer:
        raw_token = bearer.credentials

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in with Google.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await AuthService.authenticate_session(db=db, raw_token=raw_token)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or is invalid. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> Optional[User]:
    """Dependency for routes that provide personalized responses when logged in."""
    try:
        return await get_current_user(request=request, db=db, bearer=bearer)
    except HTTPException:
        return None
