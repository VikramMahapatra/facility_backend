from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


class LeaseChargeCodeBase(BaseModel):
    code: str

class LeaseChargeCodeCreate(LeaseChargeCodeBase):
    pass


class LeaseChargeCodeUpdate(LeaseChargeCodeBase):
   pass


class LeaseChargeCodeOut(LeaseChargeCodeBase):
    id: UUID
    org_id: UUID
    is_deleted: bool

    model_config = {
        "from_attributes": True
    }


class LeaseChargeCodeResponse(BaseModel):
    items: List[LeaseChargeCodeOut]
    total: int

    model_config = {
        "from_attributes": True
    }