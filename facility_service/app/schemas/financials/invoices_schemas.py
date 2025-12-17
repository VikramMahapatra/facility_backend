# app/schemas/space_groups.py
from datetime import date
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional, Any
from shared.core.schemas import CommonQueryParams


class InvoiceBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    billable_item_type: Optional[str] = None
    billable_item_id: Optional[UUID] = None
    date: Optional[str]
    due_date: Optional[str]
    status: str
    currency: str
    totals: Optional[Any] = None
    meta: Optional[Any] = None
    is_paid: Optional[bool] = None

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceUpdate(InvoiceBase):
    id: str
    pass


class InvoiceOut(InvoiceBase):
    id: UUID
    org_id: Optional[UUID] = None
    site_id: UUID
    billable_item_type:  Optional[str] = None
    billable_item_id:  Optional[UUID] = None
    billable_item_name: Optional[str] = None
    invoice_no: str
    date: Optional[str]
    due_date: Optional[str]
    status: str
    currency: str
    totals: Optional[Any] = None
    meta: Optional[Any] = None
    is_paid: Optional[bool] = None
    site_name:  Optional[str] = None

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class InvoicesRequest(CommonQueryParams):
    status: Optional[str] = None
    billable_item_type: Optional[str] = None


class InvoicesResponse(BaseModel):
    invoices: List[InvoiceOut]
    total: int

    model_config = {"from_attributes": True}



class InvoicesOverview(BaseModel):
    totalInvoices: int
    totalAmount: int
    paidAmount: int
    outstandingAmount: int

    model_config = {"from_attributes": True}


class PaymentOut(BaseModel):
    id: UUID
    org_id: Optional[UUID] = None
    invoice_id: UUID
    invoice_no: str
    billable_item_name: Optional[str] = None
    method: str
    ref_no: str
    amount: Decimal
    paid_at: Optional[str]
    meta: Optional[Any] = None

    class Config:
        from_attributes = True


class PaymentResponse(BaseModel):
    payments: List[PaymentOut]
    total: int

    model_config = {"from_attributes": True}
    
    
class InvoiceTotalsRequest(BaseModel):
    billable_item_type: str
    billable_item_id: UUID

class InvoiceTotalsResponse(BaseModel):
    subtotal: Optional[Decimal] = None
    tax: Optional[Decimal] = None
    grand_total: Optional[Decimal] = None

    
    class Config:
        from_attributes = True
