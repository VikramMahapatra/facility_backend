# app/schemas/space_groups.py
from pydantic import BaseModel
from typing import Optional, Any
from uuid import UUID

class SpaceGroupBase(BaseModel):
    org_id: UUID
    site_id: str
    name: str
    kind: str
    specs: Optional[Any] = None

class SpaceGroupCreate(SpaceGroupBase):
    pass

class SpaceGroupUpdate(SpaceGroupBase):
    pass

class SpaceGroupOut(SpaceGroupBase):
    id: str

    class Config:
        attribute = True
