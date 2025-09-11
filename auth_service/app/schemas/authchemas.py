from pydantic import BaseModel, EmailStr
from typing import Literal, Optional, Union

AllowedRole = Literal["manager", "admin", "superadmin", "user"]

# -------- Google --------
class GoogleAuthRequest(BaseModel):
    token: str

class RegisterRequest(BaseModel):
    email: EmailStr
    role: AllowedRole

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    redirect_url: Optional[str] = None

class NotRegisteredResponse(BaseModel):
    needs_registration: bool = True
    email: EmailStr
    allowed_roles: list[AllowedRole]

class LoginSuccessResponse(BaseModel):
    needs_registration: bool = False
    token: Token

GoogleAuthResponse = Union[NotRegisteredResponse, LoginSuccessResponse]

# -------- Mobile --------
class VerifyResponse(BaseModel):
    needs_registration: bool
    access_token: Optional[str] = None
    token_type: Optional[str] = "bearer"
    redirect_url: Optional[str] = None
    
    class Config:
        from_attributes = True
    


class MobileRequest(BaseModel):
    mobile: str

class OTPVerify(BaseModel):
    mobile: str
    otp: str
    role: Optional[AllowedRole] = None
