
from fastapi import Form
from pydantic import BaseModel, EmailStr,  HttpUrl
from typing import List, Literal, Optional
from uuid import UUID
from datetime import datetime

# Shared properties


class UserBase(BaseModel):
    full_name: str
    email: Optional[EmailStr] = None
    phone_e164: Optional[str] = None
    picture_url: Optional[HttpUrl] = None
    status: Optional[str] = "active"

# For reading a user (response model)


class UserRead(UserBase):
    id: UUID
    org_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # allows Pydantic to work with SQLAlchemy objects


class UserCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    accountType: Literal["Organization", "Vendor", "Tenant"]
    organizationName: Optional[str] = None
    pictureUrl: Optional[HttpUrl] = None

    class Config:
        from_attributes = True  # allows Pydantic to work with SQLAlchemy objects


class RoleOut(BaseModel):
    id: UUID
    name: str
    description: str

    model_config = {
        "from_attributes": True
    }


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    accountType: str
    organizationName: str
    roles: List[RoleOut]

    # dependency to convert Form fields → Pydantic model


def as_form(
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    role: str = Form(...)
) -> UserCreate:
    return UserCreate(
        name=name,
        email=email,
        phone=phone,
        role=role,
    )
