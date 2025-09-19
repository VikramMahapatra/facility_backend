from pydantic import BaseModel, EmailStr
from typing import Literal, Optional, Union

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
    email: Optional[EmailStr] = None
    mobile: Optional[str] = None
    allowed_roles: list[AllowedRole]

class LoginSuccessResponse(BaseModel):
    needs_registration: bool = False
    access_token: str
    token_type: str = "bearer"
    redirect_url: Optional[str] = None

AuthResponse = Union[NotRegisteredResponse, LoginSuccessResponse]