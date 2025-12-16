from pydantic import BaseModel
from typing import  Optional
from uuid import UUID
from ...enum.revenue_enum import RevenueMonth

class RevenueReportsRequest(BaseModel):
    site_id: Optional[UUID] = None 
    month: Optional[RevenueMonth] = None  
    status: Optional[str] = None
