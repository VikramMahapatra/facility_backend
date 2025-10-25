from pydantic import BaseModel, EmailStr, Field, HttpUrl
from typing import Annotated, Literal, Optional, Union
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
    needs_registration: Literal[True]
    name:  Optional[str] = None
    email: Optional[EmailStr] = None
    mobile: Optional[str] = None
    picture: Optional[HttpUrl] = None


class LoginSuccessResponse(BaseModel):
    needs_registration: Literal[False]
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


AuthResponse = Annotated[
    Union[NotRegisteredResponse, LoginSuccessResponse],
    Field(discriminator="needs_registration"),
]
