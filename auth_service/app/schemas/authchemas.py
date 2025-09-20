from pydantic import BaseModel, EmailStr, HttpUrl
from typing import Literal, Optional, Union
from ..schemas.userschema import UserResponse

AllowedRole = Literal["manager", "admin", "superadmin", "user", "default"]

# -------- Google --------
class GoogleAuthRequest(BaseModel):
    access_token: str


# -------- Mobile --------
    
class MobileRequest(BaseModel):
    mobile: str

class OTPVerify(BaseModel):
    mobile: str
    otp: str


# -------Common----------
class NotRegisteredResponse(BaseModel):
    needs_registration: bool = True
    name: str
    email: EmailStr
    picture: Optional[HttpUrl] = None

class LoginSuccessResponse(BaseModel):
    needs_registration: bool = False
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

AuthResponse = Union[NotRegisteredResponse, LoginSuccessResponse]