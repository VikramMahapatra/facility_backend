# app/schemas/space_groups.py
from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional, Any

from shared.schemas import CommonQueryParams

class SpaceGroupBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    name: str
    kind: str
    specs: Optional[Any] = None
    group_members: Optional[int] = None

class SpaceGroupCreate(SpaceGroupBase):
    pass

class SpaceGroupUpdate(SpaceGroupBase):
    id: str
    pass

class SpaceGroupOut(SpaceGroupBase):
    id: UUID

    model_config = {"from_attributes": True}

    
class SpaceGroupRequest(CommonQueryParams):
    site_id: Optional[str] = None
    kind: Optional[str] = None
    
    
class SpaceGroupResponse(BaseModel):
    spaceGroups: List[SpaceGroupOut]
    total: int
    
    model_config = {"from_attributes": True}
