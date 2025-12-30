from datetime import datetime, timedelta, timezone
import secrets
from typing import Optional
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from shared.models.refresh_token import RefreshToken
from shared.models.user_login_session import LoginPlatform, UserLoginSession
from shared.models.users import Users
from shared.utils.app_status_code import AppStatusCode
from shared.core.config import settings
from shared.helpers.json_response_helper import error_response
from shared.core.schemas import UserToken
from shared.core.database import get_auth_db as get_db
from sqlalchemy.orm import Session

security = HTTPBearer()


def create_access_token(data: dict, is_mobile: bool = False):
    payload = data.copy()

    # Only add expiry for non-mobile users
    if not is_mobile:
        expires = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        payload['exp'] = expires

    # Ensure "name" exists (for service request requester_id use case)
    if 'name' not in payload and 'full_name' in payload:
        payload['name'] = payload['full_name']

    token = jwt.encode(payload, settings.JWT_SECRET,
                       algorithm=settings.JWT_ALGORITHM)
    return token


def create_refresh_token(db, session_id):
    # 1️⃣ Fetch the session
    session = db.query(UserLoginSession).filter(
        UserLoginSession.id == session_id).first()

    print(f"session : {session}")

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Login session not found."
        )

    # Only allow refresh token for web/portal platform
    if session.platform != LoginPlatform.portal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Refresh tokens are only available for web logins (not for {session.platform})."
        )

    existing = (
        db.query(RefreshToken)
        .filter(RefreshToken.session_id == session.id, RefreshToken.revoked == False)
        .first()
    )

    if existing:
        return existing  # or revoke it before creating new

    # Generate the secure token
    token_str = secrets.token_urlsafe(64)
    expires = datetime.now(timezone.utc) + \
        timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    # Save refresh token
    refresh = RefreshToken(
        session_id=session.id,
        token=token_str,
        expires_at=expires
    )
    db.add(refresh)
    db.commit()
    db.refresh(refresh)

    return refresh


def verify_token(db: Session, token: str) -> Optional[dict]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET,
                             algorithms=settings.JWT_ALGORITHM)
        user = UserToken(**payload)

        if not user.user_id or not user.session_id:
            return error_response(
                message="Invalid token structure",
                status_code=str(AppStatusCode.AUTHENTICATION_TOKEN_INVALID),
                http_status=status.HTTP_401_UNAUTHORIZED
            )

        # ✅ Check session validity
        session = db.query(UserLoginSession).filter(
            UserLoginSession.id == user.session_id,
            UserLoginSession.user_id == user.user_id
        ).first()

        if not session or not session.is_active:
            return error_response(
                message="Session has been logged out or is inactive",
                status_code=str(AppStatusCode.AUTHENTICATION_SESSION_TIMEOUT),
                http_status=status.HTTP_401_UNAUTHORIZED
            )

        return user
    except JWTError:
        return error_response(
            message="Invalid or expired token",
            status_code=str(AppStatusCode.AUTHENTICATION_TOKEN_EXPIRED),
            http_status=status.HTTP_401_UNAUTHORIZED
        )


def validate_current_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials
    # decoded token → contains user_id or email
    user_data = verify_token(db, token)

    # Fetch the user from the database
    user = db.query(Users).filter(Users.id == user_data.user_id).first()

    if not user:
        return error_response(
            message="User not found",
            status_code=str(AppStatusCode.AUTHENTICATION_USER_INVALID),
            http_status=404
        )

    if user.status.lower() != "active":
        return error_response(
            message="User is not active. Access denied",
            status_code=str(AppStatusCode.AUTHENTICATION_USER_INACTIVE),
            http_status=403
        )

    user_data.status = user.status
    return user_data


def validate_token(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db)
):
    token = credentials.credentials
    user_data = verify_token(db, token)

    user = db.query(Users).filter(Users.id == user_data.user_id).first()

    if not user:
        return error_response(
            message="User not found",
            status_code=str(AppStatusCode.AUTHENTICATION_USER_INVALID),
            http_status=404
        )
    user_data.status = user.status
    return user_data




def allow_admin(current_user: UserToken = Depends(validate_current_token)):
    if current_user.account_type.lower() != "organization":
        return error_response(
            message="Access forbidden: Admins only",
            http_status=403
        )
    
    return current_user