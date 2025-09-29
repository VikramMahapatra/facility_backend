# app/schemas/space_groups.py
from datetime import date
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional, Any
from shared.schemas import CommonQueryParams


class TaxCodeBase(BaseModel):
    org_id: Optional[UUID] = None
    code: str
    rate: Decimal
    status: str
    jurisdiction: str
    accounts: Optional[Any] = None

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class TaxCodeCreate(TaxCodeBase):
    pass


class TaxCodeUpdate(TaxCodeBase):
    id: str
    pass


class TaxCodeOut(TaxCodeBase):
    id: UUID
    org_id: Optional[UUID] = None
    code: str
    rate: Decimal
    status: str
    jurisdiction: str
    accounts: Optional[Any] = None

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class TaxCodesRequest(CommonQueryParams):
    jurisdiction: Optional[str] = None


class TaxCodesResponse(BaseModel):
    tax_codes: List[TaxCodeOut]
    total: int

    model_config = {"from_attributes": True}


class TaxOverview(BaseModel):
    activeTaxCodes: int
    totalTaxCollected: Decimal
    avgTaxRate: Decimal
    pendingReturns: int
    lastMonthActiveTaxCodes: int

    model_config = {"from_attributes": True}


class TaxReturnOut(BaseModel):
    id: UUID
    org_id: Optional[UUID] = None
    year: int
    month_no: int
    period: str
    total_sales: Decimal
    gst18: Decimal
    gst12: Decimal
    gst5: Decimal
    total_tax: Decimal
    filed: bool

    class Config:
        from_attributes = True


class TaxReturnResponse(BaseModel):
    tax_returns: List[TaxReturnOut]
    total: int

    model_config = {"from_attributes": True}
