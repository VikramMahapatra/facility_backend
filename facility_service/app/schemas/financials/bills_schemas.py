from datetime import date as date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional, Any
from shared.core.schemas import AttachmentOut, CommonQueryParams

# Bill Lines


class BillLineBase(BaseModel):
    item_id: UUID
    description: Optional[str] = None
    amount: Decimal
    tax_pct: Optional[Decimal] = 0

    class Config:
        from_attributes = True


class BillLineCreate(BillLineBase):
    pass


class BillLineOut(BillLineBase):
    id: UUID
    bill_id: UUID
    work_order_no: Optional[str] = None

# Bill Payments


class BillPaymentBase(BaseModel):
    amount: Decimal
    method: Optional[str] = None
    ref_no: Optional[str] = None
    paid_at: Optional[datetime] = None
    meta: Optional[Any] = None

    class Config:
        from_attributes = True


class BillPaymentCreate(BillPaymentBase):
    bill_id: UUID


class BillPaymentOut(BillPaymentBase):
    id: UUID
    bill_id: UUID
    bill_no: Optional[str] = None
    site_name: Optional[str] = None
    space_name: Optional[str] = None
    customer_name: Optional[str] = None
    notes: Optional[str] = None

# Bills


class BillBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    space_id: UUID
    vendor_id: UUID
    bill_no: str
    date: date
    status: str = "draft"
    totals: Optional[Any] = None
    meta: Optional[Any] = None

    class Config:
        from_attributes = True


class BillCreate(BillBase):
    lines: List[BillLineCreate] = []


class BillUpdate(BillBase):
    id: UUID


class BillOut(BillBase):
    id: UUID
    created_at: Optional[datetime] = None

    # fields needed for the UI Table
    vendor_name: Optional[str] = None
    space_name: Optional[str] = None
    site_name: Optional[str] = None
    total_amount: Optional[Decimal] = None
    paid_amount: Optional[Decimal] = None

    # Relationships
    lines: List[BillLineOut] = []
    payments: List[BillPaymentOut] = []
    attachments: Optional[List[AttachmentOut]] = None

# API Responses & Requests


class BillsRequest(CommonQueryParams):
    status: Optional[str] = None
    vendor_id: Optional[UUID] = None
    site_id: Optional[UUID] = None


class BillsResponse(BaseModel):
    bills: List[BillOut]
    total: int

    class Config:
        from_attributes = True


class BillsOverview(BaseModel):
    totalBills: int
    totalAmount: float
    paidAmount: float
    outstandingAmount: float

    class Config:
        from_attributes = True


class BillPaymentResponse(BaseModel):
    payments: List[BillPaymentOut]
    total: int
    total_made: int

    model_config = {"from_attributes": True}


class AutoBillResponse(BaseModel):
    total_bill_created: int
