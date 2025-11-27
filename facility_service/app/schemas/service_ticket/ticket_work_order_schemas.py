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


class TicketWorkOrderCreate(TicketWorkOrderBase):
    pass


class TicketWorkOrderUpdate(TicketWorkOrderBase):
    id: UUID


class TicketWorkOrderOut(TicketWorkOrderBase):
    id: UUID
    ticket_no: Optional[str] = None  # From ticket relationship
    assigned_to_name: Optional[str] = None  # From users relationship
    site_name: Optional[str] = None  # From site relationship
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_deleted: Optional[bool] = False

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
    site_id: Optional[str] = "all"  # Same pattern as status filter
    status: Optional[str] = "all"   # Status filter