from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Technician for dropdown (using StaffSite + Users)
class TechnicianOut(BaseModel):
    user_id: UUID
    full_name: str
   

    class Config:
        from_attributes = True

# Technician Workload Summary
class TechnicianWorkloadSummary(BaseModel):
    technician_id: UUID  # user_id from StaffSite
    technician_name: str
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    escalated_tickets: int

    class Config:
        from_attributes = True

# Assigned Ticket Details
class AssignedTicketOut(BaseModel):
    id: UUID
    ticket_no: str
    title: str
    category: str
    assigned_to: UUID  # user_id from StaffSite
    technician_name: str
    status: str
    priority: str
    created_at: datetime
    is_overdue: bool = False
    can_escalate: bool = False

    class Config:
        from_attributes = True

# Unassigned Ticket Details
class UnassignedTicketOut(BaseModel):
    id: UUID
    ticket_no: str
    title: str
    category: str
    status: str
    priority: str
    created_at: datetime
    is_overdue: bool = False

    class Config:
        from_attributes = True

# Complete Team Workload Response
class TeamWorkloadManagementResponse(BaseModel):
    technicians_workload: List[TechnicianWorkloadSummary]
    assigned_tickets: List[AssignedTicketOut]
    unassigned_tickets: List[UnassignedTicketOut]
    available_technicians: List[TechnicianOut]  # For dropdown
    total_assigned: int
    total_unassigned: int

    class Config:
        from_attributes = True