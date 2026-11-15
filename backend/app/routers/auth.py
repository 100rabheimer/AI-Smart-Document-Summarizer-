from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import UserRead, GoogleAuthURLResponse, AuthStatusResponse
from app.services.auth_service import AuthService, SESSION_COOKIE_NAME, SESSION_DURATION_DAYS

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.get(
    "/login/google",
    response_model=GoogleAuthURLResponse,
    summary="Get Google OAuth Authorization URL",
    description="Returns the Google consent screen URL and CSRF state token.",
)
async def login_google():
    auth_url, state = AuthService.generate_google_auth_url()
    return GoogleAuthURLResponse(url=auth_url, state=state)


@router.get(
    "/callback/google",
    summary="Google OAuth Callback Handler",
    description="Exchanges Google authorization code for session cookie and redirects to frontend.",
)
async def callback_google(
    request: Request,
    response: Response,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google OAuth authorization error: {error}"
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Google authorization code in callback."
        )

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        user, raw_session_token = await AuthService.process_oauth_login(
            db=db,
            code=code,
            user_agent=user_agent,
            ip_address=client_ip,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {str(e)}"
        )

    # Redirect to frontend application
    redirect_target = f"{settings.FRONTEND_URL}/?auth=success"
    redirect_resp = RedirectResponse(url=redirect_target, status_code=status.HTTP_302_FOUND)

    # Set secure HTTP-only session cookie
    redirect_resp.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_session_token,
        max_age=SESSION_DURATION_DAYS * 86400,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        path="/",
    )

    return redirect_resp


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get Current Authenticated User",
    description="Returns the profile of the user currently authenticated via session cookie or bearer token.",
)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post(
    "/dev-login",
    response_model=UserRead,
    summary="Development Bypass Login",
    description="Bypasses Google OAuth for local testing. Only available when ENVIRONMENT=development.",
)
async def dev_login(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    if settings.ENVIRONMENT != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev login is only available in development environment."
        )

    user, raw_session_token = await AuthService.create_dev_session(
        db=db,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_session_token,
        max_age=SESSION_DURATION_DAYS * 86400,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )
    return user


@router.post(
    "/logout",
    summary="Log Out User",
    description="Revokes the active session in PostgreSQL and clears the session cookie.",
)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if raw_token:
        await AuthService.logout_session(db=db, raw_token=raw_token)

    # Clear cookie in response
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
    )
    return {"message": "Logged out successfully"}
