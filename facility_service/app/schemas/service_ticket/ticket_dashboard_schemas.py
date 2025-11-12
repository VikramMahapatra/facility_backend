from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# 1. Dashboard Overview
class DashboardOverviewResponse(BaseModel):
    total_tickets: int
    new_tickets: int
    escalated_tickets: int
    in_progress_tickets: int
    closed_tickets: int
    high_priority_tickets: int

    class Config:
        from_attributes = True

# 2. Last 30 Days Performance
class PerformanceResponse(BaseModel):
    pending_tickets: int
    resolved: int
    escalated: int
    total_created: int
    resolution_rate: float
    escalation_rate: float

    class Config:
        from_attributes = True

# 3. Team Workload Distribution
class TechnicianWorkloadOut(BaseModel):
    technician_id: str
    open: int
    in_progress: int
    escalated: int
    total: int

    class Config:
        from_attributes = True

class CategoryDistributionOut(BaseModel):
    category_name: str
    ticket_count: int

    class Config:
        from_attributes = True

class TeamWorkloadResponse(BaseModel):
    technicians_workload: List[TechnicianWorkloadOut]
    categories_distribution: List[CategoryDistributionOut]

    class Config:
        from_attributes = True

# 4. Ticket Category Statistics
class CategoryStatisticsOut(BaseModel):
    category_name: str
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    escalated_tickets: int
    closed_tickets: int
    high_priority_tickets: int

    class Config:
        from_attributes = True

class CategoryStatisticsResponse(BaseModel):
    statistics: List[CategoryStatisticsOut]
    total: int

    class Config:
        from_attributes = True

# 5. Recent Tickets
class RecentTicketOut(BaseModel):
    id: UUID
    ticket_no: str
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    category: Optional[str] = None
    created_at: Optional[datetime] = None
    is_overdue: Optional[bool] = False
    can_escalate: Optional[bool] = False

    class Config:
        from_attributes = True

class RecentTicketsResponse(BaseModel):
    tickets: List[RecentTicketOut]
    total: int

    class Config:
        from_attributes = True

# 6. Complete Dashboard (All in one)
class CompleteDashboardResponse(BaseModel):
    overview: DashboardOverviewResponse
    performance: PerformanceResponse
    recent_tickets: RecentTicketsResponse
    team_workload: TeamWorkloadResponse

    class Config:
        from_attributes = True