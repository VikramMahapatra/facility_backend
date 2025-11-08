from datetime import datetime, timedelta
import secrets
from typing import Optional
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from auth_service.app.models.refresh_token import RefreshToken
from auth_service.app.models.user_login_session import UserLoginSession
from auth_service.app.models.users import Users
from shared.utils.app_status_code import AppStatusCode
from shared.core.config import settings
from shared.helpers.json_response_helper import error_response
from shared.core.schemas import UserToken
from shared.core.database import get_auth_db as get_db
from sqlalchemy.orm import Session

security = HTTPBearer()


def create_access_token(data: dict):
    expires = datetime.utcnow(
    ) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    data.update({'exp': expires})
    # ✅ Ensure "name" exists if user is passed added it for service request requester id
    if 'name' not in data and 'full_name' in data:
        data['name'] = data['full_name']

    return jwt.encode(data, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(db, session_id):
    token_str = secrets.token_urlsafe(64)
    expires = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    refresh = RefreshToken(
        session_id=session_id,
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
