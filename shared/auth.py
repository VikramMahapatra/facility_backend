import datetime
from typing import Optional
from jose import JWTError, jwt
from shared.config import settings

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
        return None

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return plain_password == hashed_password  # Replace with actual hashing logic if needed