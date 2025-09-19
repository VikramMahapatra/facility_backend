import datetime
from typing import Optional
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from shared.config import settings

security = HTTPBearer()

def create_access_token(data:dict):
    expires = datetime.datetime.utcnow() + datetime.timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    data.update({'exp' : expires})
    return jwt.encode(data, settings.JWT_SECRET, algorithm= settings.JWT_ALGORITHM)

def verify_token(token:str) -> Optional[dict]:
    """Verify and decode a JWT token."""
    try:
        payload= jwt.decode(token, settings.JWT_SECRET, algorithms=settings.JWT_ALGORITHM)
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

def validate_current_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    return verify_token(token)