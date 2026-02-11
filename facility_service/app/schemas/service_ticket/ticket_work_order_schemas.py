from decimal import Decimal
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from shared.core.schemas import CommonQueryParams
from ...enum.ticket_service_enum import TicketWorkOrderStatusEnum


class TicketWorkOrderBase(BaseModel):
    ticket_id: UUID
    description: str
    assigned_to: Optional[UUID] = None
    status: Optional[TicketWorkOrderStatusEnum] = TicketWorkOrderStatusEnum.PENDING

    # ✅ ADD NEW FIELDS HERE ONLY
    labour_cost: Optional[float] = None
    material_cost: Optional[float] = None
    other_expenses: Optional[float] = None
    estimated_time: Optional[int] = None
    special_instructions: Optional[str] = None
    tax_code_id: Optional[UUID] = None   # ✅ ADD


class TicketWorkOrderCreate(TicketWorkOrderBase):
    pass


class TicketWorkOrderUpdate(TicketWorkOrderBase):
    id: UUID


class TicketWorkOrderOut(TicketWorkOrderBase):
    id: UUID
    ticket_no: Optional[str] = None  # From ticket relationship
    wo_no: Optional[str] = None
    assigned_to_name: Optional[str] = None  # From users relationship
    vendor_name: Optional[str] = None  # From vendor relationship
    site_name: Optional[str] = None  # From site relationship
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_deleted: Optional[bool] = False
    # Calculated field (labour + material + other + tax)
    total_amount: Optional[Decimal] = None
    tax_code: Optional[str] = None  # From tax code relationship

    class Config:
        from_attributes = True


class TicketWorkOrderListResponse(BaseModel):
    work_orders: List[TicketWorkOrderOut]
    total: int

    class Config:
        from_attributes = True


class TicketWorkOrderOverviewResponse(BaseModel):
    total_work_orders: int
    pending: int
    in_progress: int
    completed: int

    class Config:
        from_attributes = True


class TicketWorkOrderRequest(CommonQueryParams):
    site_id: Optional[str] = None  # Same pattern as status filter
    status: Optional[str] = None   # Status filter
