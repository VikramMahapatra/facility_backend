import datetime
from typing import Optional
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from auth_service.app.models.users import Users
from shared.app_status_code import AppStatusCode
from shared.config import settings
from shared.json_response_helper import error_response
from shared.schemas import UserToken
from shared.database import get_auth_db as get_db
from sqlalchemy.orm import Session

security = HTTPBearer()


def create_access_token(data: dict):
    expires = datetime.datetime.utcnow(
    ) + datetime.timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    data.update({'exp': expires})
    # ✅ Ensure "name" exists if user is passed added it for service request requester id
    if 'name' not in data and 'full_name' in data:
        data['name'] = data['full_name']

    return jwt.encode(data, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET,
                             algorithms=settings.JWT_ALGORITHM)
        return UserToken(**payload)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def validate_current_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials
    # decoded token → contains user_id or email
    user_data = verify_token(token)

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
    user_data = verify_token(token)

    user = db.query(Users).filter(Users.id == user_data.user_id).first()

    if not user:
        return error_response(
            message="User not found",
            status_code=str(AppStatusCode.AUTHENTICATION_USER_INVALID),
            http_status=404
        )

    user_data.status = user.status
    return user_data
