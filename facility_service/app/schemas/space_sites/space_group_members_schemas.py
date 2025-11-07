# app/schemas/space_groups.py
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional, Any
from ...schemas.space_sites.space_groups_schemas import SpaceGroupOut
from ...schemas.space_sites.spaces_schemas import SpaceOut
from shared.core.schemas import CommonQueryParams


class SpaceGroupMemberBase(BaseModel):
    group_id: UUID
    space_id: UUID
    assigned_by: str

    model_config = {"from_attributes": True}


class SpaceGroupMemberCreate(SpaceGroupMemberBase):
    pass


class SpaceGroupMemberUpdate(SpaceGroupMemberBase):
    pass


class SpaceGroupMemberOut(SpaceGroupMemberBase):
    id: str
    site_id: UUID
    site_name: str
    assigned_date: Optional[datetime]
    assigned_by: Optional[str]
    space: SpaceOut
    group: SpaceGroupOut

    model_config = {"from_attributes": True}


class SpaceGroupMemberRequest(CommonQueryParams):
    site_id: Optional[str] = None
    space_id: Optional[str] = None
    group_id: Optional[str] = None


class SpaceGroupMemberResponse(BaseModel):
    assignments: List[SpaceGroupMemberOut]
    total: int

    model_config = {"from_attributes": True}


class SpaceGroupMemberOverview(BaseModel):
    totalAssignments: int
    groupUsed: int
    spaceAssigned: int
    assignmentRate: Optional[float] = None

    model_config = {"from_attributes": True}


class AssignmentPreview(BaseModel):
    site_name: str
    space_name: str
    space_code: str
    kind: str
    group_name: str
    specs: Optional[Any] = None

    model_config = {"from_attributes": True}
