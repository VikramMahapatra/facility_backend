from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_
from typing import List
from sqlalchemy.orm import joinedload

from ...enum.ticket_service_enum import TicketStatus
from ...models.service_ticket.tickets import Ticket
from ...models.service_ticket.tickets_category import TicketCategory
from ...schemas.service_ticket.ticket_workload_management_schemas import (
    TechnicianWorkloadSummary,
    AssignedTicketOut,
    UnassignedTicketOut,
    TeamWorkloadManagementResponse
)
from uuid import UUID
from fastapi import HTTPException

def get_team_workload_management(db: Session, site_id: UUID, org_id: UUID) -> TeamWorkloadManagementResponse:
    """
    Get complete team workload management data including:
    - Technician workload summaries
    - All assigned tickets with details
    - All unassigned tickets
    """
    try:
        # Base query filter
        base_filter = [
            Ticket.site_id == site_id,
            Ticket.org_id == org_id,
            Ticket.status != TicketStatus.CLOSED  # Exclude closed tickets
        ]

        # 1. Get Technician Workload Summary
        workload_query = db.query(
            Ticket.assigned_to,
            func.count(Ticket.id).label('total_tickets'),
            func.sum(case((Ticket.status == TicketStatus.OPEN, 1), else_=0)).label('open_tickets'),
            func.sum(case((Ticket.status == TicketStatus.IN_PROGRESS, 1), else_=0)).label('in_progress_tickets'),
            func.sum(case((Ticket.status == TicketStatus.ESCALATED, 1), else_=0)).label('escalated_tickets')
        ).filter(
            *base_filter,
            Ticket.assigned_to.isnot(None)
        ).group_by(Ticket.assigned_to)

        technicians_workload = []
        for workload in workload_query.all():
            technicians_workload.append(TechnicianWorkloadSummary(
                technician_id=f"Tech #{workload.assigned_to}" if workload.assigned_to else "Unassigned",
                technician_name=f"Technician #{workload.assigned_to}",  # You can enhance this with actual technician names
                total_tickets=workload.total_tickets or 0,
                open_tickets=workload.open_tickets or 0,
                in_progress_tickets=workload.in_progress_tickets or 0,
                escalated_tickets=workload.escalated_tickets or 0
            ))

        # 2. Get All Assigned Tickets (with details)
        assigned_tickets_query = db.query(Ticket).options(
            joinedload(Ticket.category)
        ).filter(
            *base_filter,
            Ticket.assigned_to.isnot(None)
        ).order_by(Ticket.created_at.desc())

        assigned_tickets = []
        for ticket in assigned_tickets_query.all():
            assigned_tickets.append(AssignedTicketOut(
                id=ticket.id,
                ticket_no=ticket.ticket_no,
                title=ticket.title,
                category=ticket.category.category_name if ticket.category else "Unknown",
                assigned_to=f"Tech #{ticket.assigned_to}",
                technician_name=f"Technician #{ticket.assigned_to}",
                status=ticket.status.value if hasattr(ticket.status, 'value') else ticket.status,
                priority=ticket.priority,
                created_at=ticket.created_at,
                is_overdue=ticket.is_overdue,
                can_escalate=ticket.can_escalate
            ))

        # 3. Get All Unassigned Tickets
        unassigned_tickets_query = db.query(Ticket).options(
            joinedload(Ticket.category)
        ).filter(
            *base_filter,
            Ticket.assigned_to.is_(None),
            Ticket.status == TicketStatus.OPEN  # Typically unassigned tickets are OPEN
        ).order_by(Ticket.created_at.desc())

        unassigned_tickets = []
        for ticket in unassigned_tickets_query.all():
            unassigned_tickets.append(UnassignedTicketOut(
                id=ticket.id,
                ticket_no=ticket.ticket_no,
                title=ticket.title,
                category=ticket.category.category_name if ticket.category else "Unknown",
                status=ticket.status.value if hasattr(ticket.status, 'value') else ticket.status,
                priority=ticket.priority,
                created_at=ticket.created_at,
                is_overdue=ticket.is_overdue
            ))

        return TeamWorkloadManagementResponse(
            technicians_workload=technicians_workload,
            assigned_tickets=assigned_tickets,
            unassigned_tickets=unassigned_tickets,
            total_assigned=len(assigned_tickets),
            total_unassigned=len(unassigned_tickets)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching team workload management data: {str(e)}")