# schemas/service_ticket/ticket_category_schemas.py
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from shared.core.schemas import CommonQueryParams
from ...enum.ticket_service_enum import AutoAssignRoleEnum

class TicketCategoryBase(BaseModel):
    category_name: str
    auto_assign_role: Optional[AutoAssignRoleEnum] = None
    sla_hours: Optional[int] = 24
    is_active: Optional[bool] = True
    sla_id: Optional[UUID] = None
    site_id: Optional[UUID] = None

class TicketCategoryCreate(TicketCategoryBase):
    pass

class TicketCategoryUpdate(TicketCategoryBase):

    id: UUID

class TicketCategoryOut(TicketCategoryBase):
    id: UUID
    is_deleted: Optional[bool] = False
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    site_name: Optional[str] = None  # ✅ Added site name for grid display

    class Config:
        from_attributes = True

class TicketCategoryListResponse(BaseModel):
    ticket_categories: List[TicketCategoryOut]
    total: int

    class Config:
        from_attributes = True
        
# Add to your existing tickets_schemas.py

class EmployeeOut(BaseModel):
    user_id: UUID
    full_name: str

class EmployeeListResponse(BaseModel):
    employees: List[EmployeeOut]    
    

class TicketCategoryRequest(CommonQueryParams):
    site_id: Optional[str] = None  
    is_active: Optional[str] = None  
