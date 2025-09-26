
from fastapi import Form
from pydantic import BaseModel, EmailStr,  HttpUrl, field_serializer
from typing import Optional
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
    id: UUID
    name: str
    
    @field_serializer("id")
    def serialize_id(self, v: UUID, _info):
        return str(v)