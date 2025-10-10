from uuid import UUID
from pydantic import BaseModel, ConfigDict
from typing import Optional, Any, List
from datetime import date, datetime

# -------------------- Base Schema --------------------
class ContractBase(BaseModel):
    org_id: UUID
    vendor_id: Optional[UUID] = None
    site_id: Optional[UUID] = None
    title: str
    type: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    value: Optional[float] = None
    terms: Optional[Any] = None
    documents: Optional[Any] = None



# -------------------- Output Schema --------------------
class ContractOut(ContractBase):
    id: UUID
    vendor_name: Optional[str] = None
    site_name: Optional[str] = None
    created_at: Optional[datetime] = None  
    updated_at: Optional[datetime] = None  



    model_config = ConfigDict(from_attributes=True)


# -------------------- Create / Update --------------------
class ContractCreate(ContractBase):
    org_id: UUID

class ContractUpdate(ContractBase):
    id: UUID


# -------------------- Overview Response --------------------
class ContractOverviewResponse(BaseModel):
    total_contracts: int
    active_contracts: int
    expiring_soon: int
    total_value: float


# -------------------- List Request Filters --------------------
class ContractRequest(BaseModel):
    skip: int = 0
    limit: int = 10
    type: Optional[str] = None
    status: Optional[str] = None
    search: Optional[str] = None


# -------------------- List Response --------------------
class ContractListResponse(BaseModel):
    contracts: List[ContractOut]
    total: int

    model_config = {"from_attributes": True}