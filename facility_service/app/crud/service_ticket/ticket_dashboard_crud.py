from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session, joinedload

from ...enum.ticket_service_enum import TicketStatus
from ...models.service_ticket.tickets import Ticket
from ...models.service_ticket.tickets_category import TicketCategory
from ...schemas.service_ticket.ticket_dashboard_schemas import (
    CategoryDistributionOut,
    CategoryStatisticsOut,
    DashboardOverviewResponse,
    PerformanceResponse,
    RecentTicketOut,
    RecentTicketsResponse,
    TeamWorkloadResponse,
    CategoryStatisticsResponse,
    CompleteDashboardResponse,
    TechnicianWorkloadOut
)
from uuid import UUID
from fastapi import HTTPException

def get_dashboard_overview(db: Session, site_id: UUID, org_id: UUID) -> DashboardOverviewResponse:
    """
    1. Dashboard Overview - Get main dashboard overview with current ticket counts
    """
    try:
        base_query = db.query(Ticket).filter(
            Ticket.site_id == site_id,
            Ticket.org_id == org_id
        )
        
        total_tickets = base_query.count()
        new_tickets = base_query.filter(Ticket.status == TicketStatus.OPEN).count()
        escalated_tickets = base_query.filter(Ticket.status == TicketStatus.ESCALATED).count()
        in_progress_tickets = base_query.filter(Ticket.status == TicketStatus.IN_PROGRESS).count()
        closed_tickets = base_query.filter(Ticket.status == TicketStatus.CLOSED).count()
        high_priority_tickets = base_query.filter(Ticket.priority == "HIGH").count()
        
        return DashboardOverviewResponse(
            total_tickets=total_tickets,
            new_tickets=new_tickets,
            escalated_tickets=escalated_tickets,
            in_progress_tickets=in_progress_tickets,
            closed_tickets=closed_tickets,
            high_priority_tickets=high_priority_tickets
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching dashboard overview: {str(e)}")

def get_last_30_days_performance(db: Session, site_id: UUID, org_id: UUID) -> PerformanceResponse:
    """
    2. Last 30 Days Performance - Get performance metrics for the last 30 days
    """
    try:
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        last_30_days_tickets = db.query(Ticket).filter(
            Ticket.site_id == site_id,
            Ticket.org_id == org_id,
            Ticket.created_at >= thirty_days_ago
        )
        
        total_created_30d = last_30_days_tickets.count()
        resolved_30d = last_30_days_tickets.filter(Ticket.status == TicketStatus.CLOSED).count()
        escalated_30d = last_30_days_tickets.filter(Ticket.status == TicketStatus.ESCALATED).count()
        pending_30d = total_created_30d - resolved_30d
        
        resolution_rate = round((resolved_30d / total_created_30d * 100) if total_created_30d > 0 else 0, 2)
        escalation_rate = round((escalated_30d / total_created_30d * 100) if total_created_30d > 0 else 0, 2)
        
        return PerformanceResponse(
            pending_tickets=pending_30d,
            resolved=resolved_30d,
            escalated=escalated_30d,
            total_created=total_created_30d,
            resolution_rate=resolution_rate,
            escalation_rate=escalation_rate
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching performance metrics: {str(e)}")

def get_team_workload(db: Session, site_id: UUID, org_id: UUID) -> TeamWorkloadResponse:
    """
    3. Team Workload Distribution - Get team workload distribution by technician
    """
    try:
        workload_query = db.query(
            Ticket.assigned_to,
            func.count(Ticket.id).label('total_tickets'),
            func.sum(case((Ticket.status == TicketStatus.OPEN, 1), else_=0)).label('open_tickets'),
            func.sum(case((Ticket.status == TicketStatus.IN_PROGRESS, 1), else_=0)).label('in_progress_tickets'),
            func.sum(case((Ticket.status == TicketStatus.ESCALATED, 1), else_=0)).label('escalated_tickets')
        ).filter(
            Ticket.site_id == site_id,
            Ticket.org_id == org_id,
            Ticket.assigned_to.isnot(None)
        ).group_by(Ticket.assigned_to)
        
        technicians_workload = []
        for workload in workload_query.all():
            technicians_workload.append(TechnicianWorkloadOut(
                technician_id=str(workload.assigned_to),
                open=workload.open_tickets or 0,
                in_progress=workload.in_progress_tickets or 0,
                escalated=workload.escalated_tickets or 0,
                total=workload.total_tickets or 0
            ))
        
        # Tickets by category
        category_distribution = db.query(
            TicketCategory.category_name,
            func.count(Ticket.id).label('ticket_count')
        ).join(
            Ticket, Ticket.category_id == TicketCategory.id
        ).filter(
            Ticket.site_id == site_id,
            Ticket.org_id == org_id
        ).group_by(TicketCategory.category_name).all()
        
        categories = []
        for category in category_distribution:
            categories.append(CategoryDistributionOut(
                category_name=category.category_name,
                ticket_count=category.ticket_count
            ))
        
        return TeamWorkloadResponse(
            technicians_workload=technicians_workload,
            categories_distribution=categories
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching team workload: {str(e)}")

def get_category_statistics(db: Session, site_id: UUID, org_id: UUID) -> CategoryStatisticsResponse:
    """
    4. Ticket Category Statistics - Get detailed ticket statistics grouped by category
    """
    try:
        stats_query = db.query(
            TicketCategory.category_name,
            func.count(Ticket.id).label('total_tickets'),
            func.sum(case((Ticket.status == TicketStatus.OPEN, 1), else_=0)).label('open_tickets'),
            func.sum(case((Ticket.status == TicketStatus.IN_PROGRESS, 1), else_=0)).label('in_progress_tickets'),
            func.sum(case((Ticket.status == TicketStatus.ESCALATED, 1), else_=0)).label('escalated_tickets'),
            func.sum(case((Ticket.status == TicketStatus.CLOSED, 1), else_=0)).label('closed_tickets'),
            func.sum(case((Ticket.priority == "HIGH", 1), else_=0)).label('high_priority_tickets')
        ).join(
            Ticket, Ticket.category_id == TicketCategory.id
        ).filter(
            Ticket.site_id == site_id,
            Ticket.org_id == org_id
        ).group_by(TicketCategory.category_name)
        
        category_stats = []
        total_tickets = 0
        
        for stat in stats_query.all():
            category_stats.append(CategoryStatisticsOut(
                category_name=stat.category_name,
                total_tickets=stat.total_tickets,
                open_tickets=stat.open_tickets or 0,
                in_progress_tickets=stat.in_progress_tickets or 0,
                escalated_tickets=stat.escalated_tickets or 0,
                closed_tickets=stat.closed_tickets or 0,
                high_priority_tickets=stat.high_priority_tickets or 0
            ))
            total_tickets += stat.total_tickets
        
        return CategoryStatisticsResponse(
            statistics=category_stats,
            total=total_tickets
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching category statistics: {str(e)}")

def get_recent_tickets(db: Session, site_id: UUID, org_id: UUID, limit: int = 10) -> RecentTicketsResponse:
    """
    5. Recent Tickets - Get recent tickets with their details
    """
    try:
        tickets = db.query(Ticket).options(
            joinedload(Ticket.category)
        ).filter(
            Ticket.site_id == site_id,
            Ticket.org_id == org_id
        ).order_by(
            Ticket.created_at.desc()
        ).limit(limit).all()
        
        recent_tickets = []
        for ticket in tickets:
            recent_tickets.append(RecentTicketOut(
                id=ticket.id,
                ticket_no=ticket.ticket_no,
                title=ticket.title,
                description=ticket.description,
                status=ticket.status.value if hasattr(ticket.status, 'value') else ticket.status,
                priority=ticket.priority,
                category=ticket.category.category_name if ticket.category else "Unknown",
                created_at=ticket.created_at,
                is_overdue=ticket.is_overdue,
                can_escalate=ticket.can_escalate
            ))
        
        return RecentTicketsResponse(
            tickets=recent_tickets,
            total=len(recent_tickets)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching recent tickets: {str(e)}")

def get_complete_dashboard(db: Session, site_id: UUID, org_id: UUID) -> CompleteDashboardResponse:
    """
    6. Complete Dashboard - Get all dashboard data in one call
    """
    try:
        overview = get_dashboard_overview(db, site_id, org_id)
        performance = get_last_30_days_performance(db, site_id, org_id)
        recent_tickets = get_recent_tickets(db, site_id, org_id)
        team_workload = get_team_workload(db, site_id, org_id)
        
        return CompleteDashboardResponse(
            overview=overview,
            performance=performance,
            recent_tickets=recent_tickets,
            team_workload=team_workload
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching complete dashboard: {str(e)}")