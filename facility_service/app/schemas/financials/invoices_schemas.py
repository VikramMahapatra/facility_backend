# app/schemas/space_groups.py
from datetime import date as date_type, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional, Any
from shared.core.schemas import CommonQueryParams


class AdvancePaymentCreate(BaseModel):
    user_id: Optional[UUID] = None
    method: str
    ref_no: Optional[str] = None
    amount: Decimal
    paid_at: Optional[date_type] = None
    notes: Optional[str] = None
    currency: Optional[str] = None

    class Config:
        json_encoders = {
            Decimal: float
        }


class PaymentCreateWithInvoice(BaseModel):
    id: Optional[UUID] = None
    invoice_id: Optional[UUID] = None
    method: str
    ref_no: Optional[str] = None
    amount: Decimal
    paid_at: Optional[date_type] = None
    meta: Optional[Any] = None

    class Config:
        json_encoders = {
            Decimal: float
        }


class InvoiceLineBase(BaseModel):
    code: str  # RENT | WORKORDER | OWNER_MAINTENANCE | PARKING_PASS
    item_id: UUID
    description: Optional[str] = None
    amount: Decimal
    tax_pct: Optional[Decimal] = 0

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class InvoiceLineCreate(InvoiceLineBase):
    pass


class InvoiceBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    space_id: UUID
    user_id: UUID
    date: date_type
    due_date: Optional[date_type] = None
    currency: str
    totals: Optional[Any] = None
    meta: Optional[Any] = None
    status: str

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class InvoiceCreate(InvoiceBase):
    lines: List[InvoiceLineCreate]


class PaymentUpdateItem(BaseModel):
    id: Optional[UUID] = None  # None = new payment, UUID = update existing
    method: str
    ref_no: Optional[str] = None
    amount: Decimal
    paid_at: Optional[date_type] = None
    meta: Optional[Any] = None


class InvoiceUpdate(InvoiceBase):
    id: str


class AdvancePaymentOut(BaseModel):
    id: UUID
    org_id: Optional[UUID] = None
    user_id: UUID
    method: str
    ref_no: str
    amount: Decimal
    balance: Decimal
    paid_at: Optional[date_type] = None
    notes: Optional[Any] = None
    customer_name: Optional[str] = None  # Add this field

    class Config:
        from_attributes = True


class PaymentOut(BaseModel):
    id: UUID
    org_id: Optional[UUID] = None
    invoice_id: UUID
    invoice_no: Optional[str] = None
    code: Optional[str] = None
    item_no: Optional[str] = None
    method: str
    ref_no: str
    amount: Decimal
    paid_at: Optional[date_type] = None
    meta: Optional[Any] = None
    customer_name: Optional[str] = None  # Add this field

    class Config:
        from_attributes = True


class InvoiceLineOut(BaseModel):
    id: UUID
    invoice_id: UUID
    code: str
    item_id: UUID
    item_no: Optional[str] = None
    item_label: Optional[str] = None
    description: Optional[str] = None
    amount: Decimal
    tax_pct: Optional[Decimal] = 0

    class Config:
        from_attributes = True


class InvoiceOut(BaseModel):
    id: UUID
    org_id: UUID
    site_id: UUID
    space_id: UUID
    invoice_no: str
    date: Optional[str]
    due_date: Optional[str]
    currency: str
    totals: Optional[Any] = None
    meta: Optional[Any] = None
    status: str
    is_paid: bool

    # Derived / Extra fields
    site_name: Optional[str] = None
    space_name: Optional[str] = None
    code: Optional[str] = None
    user_name: Optional[str] = None

    # Relationships
    lines: List[InvoiceLineOut] = []
    payments: List[PaymentOut] = []

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


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


class AdvancePaymentResponse(BaseModel):
    advances: List[AdvancePaymentOut]
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
    total_amount: Decimal
    status: str

    code: Optional[str] = None
    item_no: Optional[str] = None
    user_name: Optional[str] = None

    payments: List[PaymentOut]
