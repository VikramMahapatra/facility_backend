import re
from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator, model_validator
from typing import Annotated, Literal, Optional, Union
from shared.wrappers.empty_string_model_wrapper import EmptyStringModel
from ..schemas.userschema import UserResponse


# -------- Google --------


class GoogleAuthRequest(BaseModel):
    access_token: str


# -------- Mobile --------

class MobileRequest(EmptyStringModel):
    mobile: Optional[str] = None
    email: Optional[EmailStr] = None

    @model_validator(mode="after")
    def validate_either_mobile_or_email(cls, values):
        if not values.mobile and not values.email:
            raise ValueError("Either mobile or email is required")
        return values

# -------- Username & Password


class UserAuthRequest(BaseModel):
    username: str
    password: str


class SwitchUserAccountRequest(BaseModel):
    user_org_id: str
    account_type: str


class OTPVerify(MobileRequest):
    otp: str


# -------Common----------
class NotRegisteredResponse(EmptyStringModel):
    needs_registration: Literal[True]
    name:  Optional[str] = None
    email: Optional[EmailStr] = None
    mobile: Optional[str] = None
    picture: Optional[HttpUrl] = None


class TokenSuccessResponse(EmptyStringModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthenticationResponse(EmptyStringModel):
    needs_registration: Literal[True, False]
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[UserResponse] = None
    name:  Optional[str] = None
    email: Optional[EmailStr] = None
    mobile: Optional[str] = None
    picture: Optional[str] = None
