from pydantic import BaseModel
from typing import Any, List, Optional, Dict
from datetime import date, datetime
from uuid import UUID

from shared.schemas import CommonQueryParams

class BuildingOut(BaseModel):
    id: UUID
    site_id: UUID
    name: str
    site_name: str
    site_kind: str
    floors: Optional[int]
    total_spaces: Optional[int]
    occupied_spaces: Optional[int]
    attributes: Optional[Any] = None

    class Config:
        from_attribute = True
        
class BuildingRequest(CommonQueryParams):
    site_id: Optional[str] = None
    
class BuildingListResponse(BaseModel):
    buildings: List[BuildingOut]
    total: int
    
class BuildingBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    name: str
    floors: Optional[int]
    status: Optional[str] = "active"
    attributes: Optional[Any] = None
    
class BuildingCreate(BuildingBase):
    pass

class BuildingUpdate(BuildingBase):
    id:str
    pass
