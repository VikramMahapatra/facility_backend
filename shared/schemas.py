
from fastapi import Form
from pydantic import BaseModel, EmailStr,  HttpUrl
from typing import Optional
from uuid import UUID
from datetime import datetime

# Shared properties
class UserToken(BaseModel):
    user_id: str
    org_id: str
    mobile: Optional[str]
    email: EmailStr
    role: list[str]
    exp: int