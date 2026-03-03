
from fastapi import Form
from pydantic import BaseModel, EmailStr,  HttpUrl, field_serializer, model_validator
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union, get_args, get_origin
from uuid import UUID
from datetime import datetime

from shared.wrappers.empty_string_model_wrapper import EmptyStringModel

# Shared properties
T = TypeVar("T")


class UserToken(BaseModel):
    user_id: str
    session_id: str
    org_id: Optional[UUID] = None
    name: Optional[str] = None  # added for service request requester id
    account_type: str
    status: Optional[str] = None
    exp: Optional[int] = None


class CommonQueryParams(EmptyStringModel):
    search: Optional[str] = None
    skip: Optional[int] = 0
    limit: Optional[int] = None


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


class MasterQueryParams(BaseModel):
    site_id: Optional[str] = None
    building_id: Optional[str] = None
    space_id: Optional[str] = None


class AttachmentOut(BaseModel):
    id: str  # ADD THIS LINE - Attachment ID from database
    file_name: str
    content_type: str
    file_data_base64: Optional[str] = None

    class Config:
        from_attributes = True
