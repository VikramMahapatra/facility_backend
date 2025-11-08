import re
from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator, model_validator
from typing import Annotated, Literal, Optional, Union
from shared.wrappers.empty_string_model_wrapper import EmptyStringModel
from ..schemas.userschema import UserResponse

AllowedRole = Literal["manager", "admin", "superadmin", "user", "default"]

# -------- Google --------


class GoogleAuthRequest(BaseModel):
    access_token: str


# -------- Mobile --------

class MobileRequest(BaseModel):
    mobile: Optional[str] = None
    email: Optional[EmailStr] = None

    @field_validator("mobile", mode="before")
    def clean_mobile(cls, v):
        if not v:
            return None
        # remove spaces and all invisible unicode chars
        cleaned = re.sub(
            r"[\s\u200b-\u200f\u202a-\u202e\u2066-\u2069]", "", v.strip())
        return cleaned if cleaned else None

    @field_validator("email", mode="before")
    def empty_to_none(cls, v):
        return v or None

    @model_validator(mode="after")
    def validate_either_mobile_or_email(cls, values):
        if not values.mobile and not values.email:
            raise ValueError("Either mobile or email is required")
        return values


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


class AuthenticationResponse(BaseModel):
    needs_registration: Literal[True, False]
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[UserResponse] = None
    name:  Optional[str] = None
    email: Optional[EmailStr] = None
    mobile: Optional[str] = None
    picture: Optional[str] = None

    @model_validator(mode="after")
    def convert_null_values(self):
        for field, value in self.__dict__.items():
            if field == "user":
                if value is None:
                    setattr(self, field, {})  # ✅ Empty object
            else:
                if value is None:
                    setattr(self, field, "")  # ✅ Empty string
        return self
