from pydantic import BaseModel, EmailStr, Field, HttpUrl
from typing import Annotated, Literal, Optional, Union

from shared.schemas import EmptyStringModel
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
class NotRegisteredResponse(EmptyStringModel):
    needs_registration: Literal[True]
    name:  Optional[str] = None
    email: Optional[EmailStr] = None
    mobile: Optional[str] = None
    picture: Optional[HttpUrl] = None


class LoginSuccessResponse(EmptyStringModel):
    needs_registration: Literal[False]
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class AuthenticationResponse(EmptyStringModel):
    needs_registration: Literal[True, False]
    access_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[UserResponse] = None
    name:  Optional[str] = None
    email: Optional[EmailStr] = None
    mobile: Optional[str] = None
    picture: Optional[str] = None


AuthResponse = Annotated[
    Union[NotRegisteredResponse, LoginSuccessResponse],
    Field(discriminator="needs_registration"),
]
