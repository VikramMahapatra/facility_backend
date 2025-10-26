import datetime
from typing import Optional
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from auth_service.app.models import users
from shared.app_status_code import AppStatusCode
from shared.config import settings
from shared.json_response_helper import error_response
from shared.schemas import UserToken

security = HTTPBearer()


def create_access_token(data: dict):
    expires = datetime.datetime.utcnow(
    ) + datetime.timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    data.update({'exp': expires})
    # ✅ Ensure "name" exists if user is passed added it for service request requester id
    if users and 'name' not in data and hasattr(users, 'full_name'):
        data['name'] = users.full_name
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


def validate_current_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    user = verify_token(token)

    # ✅ Check if user is inactive
    if user.status.lower() == "inactive":
        return error_response(
            message="User is inactive. Access denied",
            status_code=str(AppStatusCode.AUTHENTICATION_USER_INACTIVE),
            http_status=400
        )
    return user


def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    return verify_token(token)
