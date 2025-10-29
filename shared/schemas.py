
from fastapi import Form
from pydantic import BaseModel, EmailStr,  HttpUrl, field_serializer, model_validator
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union, get_args, get_origin
from uuid import UUID
from datetime import datetime

from shared.empty_string_model_wrapper import EmptyStringModel

# Shared properties
T = TypeVar("T")


class UserToken(BaseModel):
    user_id: str
    org_id: UUID
    name: Optional[str] = None  # added for service request requester id
    account_type: str
    status: str
    # added for service request in lease_partner_lookup
    role_ids: Optional[List[str]] = None
    exp: int


class CommonQueryParams(BaseModel):
    search: Optional[str] = None
    skip: Optional[int] = 0
    limit: Optional[int] = 100


class Lookup(BaseModel):
    id: Union[str, UUID]  # accepts both UUID and str
    name: str

    class Config:
        from_attributes = True


class ExportResponse(BaseModel):
    filename: str
    data: List[Dict[str, Any]]

    class Config:
        from_attributes = True


class ExportRequestParams(BaseModel):
    search: Optional[str] = None
    skip: Optional[int] = 0
    limit: Optional[int] = 100


class JsonOutResult(EmptyStringModel, Generic[T]):
    data: Optional[T] = None
    status: str
    status_code: str
    message: str


class MasterLookupQueryParams(BaseModel):
    site_id: Optional[UUID] = None
    building_id: Optional[UUID] = None
