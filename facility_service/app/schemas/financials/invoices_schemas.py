# app/schemas/space_groups.py
from datetime import date as date_type, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional, Any
from shared.core.schemas import CommonQueryParams

class PaymentCreateWithInvoice(BaseModel):
    method: str
    ref_no: Optional[str] = None
    amount: Decimal
    paid_at: Optional[date_type] = None
    meta: Optional[Any] = None
   
class InvoiceBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    billable_item_type: Optional[str] = None
    billable_item_id: Optional[UUID] = None
    date: date_type 
    due_date: Optional[date_type] = None 
    currency: str
    totals: Optional[Any] = None
    meta: Optional[Any] = None

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class InvoiceCreate(InvoiceBase):
    payments: Optional[List[PaymentCreateWithInvoice]] = None


class PaymentUpdateItem(BaseModel):
    id: Optional[UUID] = None  # None = new payment, UUID = update existing
    method: str
    ref_no: Optional[str] = None
    amount: Decimal
    paid_at: Optional[date_type] = None
    meta: Optional[Any] = None

class InvoiceUpdate(BaseModel):
    id: str
    date: Optional[date_type] = None
    due_date: Optional[date_type] = None
    currency: Optional[str] = None
    totals: Optional[Any] = None
    meta: Optional[Any] = None
    payments: Optional[List[PaymentUpdateItem]] = None


class PaymentOut(BaseModel):
    id: UUID
    org_id: Optional[UUID] = None
    invoice_id: UUID
    invoice_no: str
    billable_item_name: Optional[str] = None
    method: str
    ref_no: str
    amount: Decimal
    paid_at: Optional[date_type]=None
    meta: Optional[Any] = None
    customer_name: Optional[str] = None  # Add this field

    class Config:
        from_attributes = True


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
    payments: Optional[List[PaymentOut]] = None  # ADD THIS LINE
    
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
    totalAmount: float
    paidAmount: float
    outstandingAmount: float

    model_config = {"from_attributes": True}



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


class InvoiceDetailRequest(BaseModel):
    search: Optional[str] = None
    skip: int = 0
    limit: int = 10
    status: Optional[str] = None
    invoice_id: Optional[UUID] = None
    
    
class InvoicePaymentHistoryOut(BaseModel):
    invoice_id: UUID
    invoice_no: str
    total_amount: float
    status: str
    payments: Optional[List[PaymentOut]] = None