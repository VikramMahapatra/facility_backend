from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID


class SpaceFilterBase(BaseModel):
    id: UUID
    site_id: UUID
    kind: str
    code: str
    status: str
    area: Optional[float] = None
    building_block: Optional[str] = None
    floor: Optional[str] = None

    class Config:
        orm_mode = True


class SpaceOverview(BaseModel):
    site_id: UUID
    site_name: str
    total_buildings: int
    total_spaces: int
    occupied_spaces: float   # percentage
    total_floors: List[str]
