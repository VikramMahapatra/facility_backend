
from fastapi import Form
from pydantic import BaseModel, EmailStr,  HttpUrl, field_serializer, model_validator
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union
from uuid import UUID
from datetime import datetime

# Shared properties
T = TypeVar("T")


class UserToken(BaseModel):
    user_id: str
    org_id: UUID
    name: Optional[str] = None  # added for service request requester id
    account_type: str
    status: str
    role_ids: Optional[List[str]] = None # added for service request in lease_partner_lookup  
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


class EmptyStringModel(BaseModel):

    @model_validator(mode="after")
    def replace_none_with_empty(self):
        for field, value in self.__dict__.items():
            if value is None:
                setattr(self, field, "")
        return self


class JsonOutResult(EmptyStringModel, Generic[T]):
    data: Optional[T] = None
    status: str
    status_code: str
    message: str
