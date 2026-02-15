
from fastapi import Form
from pydantic import BaseModel, EmailStr,  HttpUrl
from typing import Any, List, Literal, Optional
from uuid import UUID
from datetime import datetime

from shared.utils.enums import UserAccountType
from shared.wrappers.empty_string_model_wrapper import EmptyStringModel

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
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    account_type: UserAccountType
    organizationName: Optional[str] = None
    plan: Optional[Literal["pro", "basic", "enterprise"]] = None
    site_id: Optional[UUID] = None
    space_id: Optional[UUID] = None
    pictureUrl: Optional[HttpUrl] = None

    class Config:
        from_attributes = True  # allows Pydantic to work with SQLAlchemy objects


class UserOrganizationOut(BaseModel):
    account_type: str
    user_org_id: UUID
    org_id: UUID
    organization_name: Optional[str] = None
    is_default: bool
    status: str


class RoleOut(BaseModel):
    id: UUID
    name: str
    description: str

    model_config = {
        "from_attributes": True
    }

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


class RolePolicyOut(BaseModel):
    resource: str
    action: str

    class Config:
        from_attributes = True


class UserResponse(EmptyStringModel):
    id: str
    name: str
    email: str
    phone: str
    account_types: List[UserOrganizationOut]
    default_account_type: str
    default_organization_name: Optional[str] = None
    status: str
    is_authenticated: bool = False
    roles: Optional[List[RoleOut]] = None
    role_policies: Optional[List[RolePolicyOut]] = None

    class Config:
        from_attributes = True
