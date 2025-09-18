# app/schemas/space_groups.py
from pydantic import BaseModel
from typing import Optional, Any

class SpaceGroupBase(BaseModel):
    org_id: str
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

    model_config = {
    "from_attributes": True
}
