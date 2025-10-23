
from fastapi import Form
from pydantic import BaseModel, EmailStr,  HttpUrl, field_serializer
from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from datetime import datetime

# Shared properties


class UserToken(BaseModel):
    user_id: str
    org_id: UUID
    mobile: Optional[str]
    email: EmailStr
    role: list[str]
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
