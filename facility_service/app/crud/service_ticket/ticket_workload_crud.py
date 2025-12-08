from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_
from typing import List
from sqlalchemy.orm import joinedload

from shared.models.users import Users
from ...enum.ticket_service_enum import TicketStatus
from ...models.service_ticket.tickets import Ticket
from ...models.service_ticket.tickets_category import TicketCategory
from ...models.common.staff_sites import StaffSite
from ...schemas.service_ticket.ticket_workload_management_schemas import (
    TechnicianWorkloadSummary,
    AssignedTicketOut,
    UnassignedTicketOut,
    TechnicianOut,
    TeamWorkloadManagementResponse
)
from uuid import UUID
from fastapi import HTTPException


def get_team_workload_management(
    db: Session,
    auth_db: Session,
    site_id: UUID,
    org_id: UUID
) -> TeamWorkloadManagementResponse:
    """
    Get complete team workload management data - ONLY for staff assigned to this site
    """
    try:
        from shared.models.users import Users

        # 1. Get Available Technicians for this site (from StaffSite + Users)
        available_technicians = get_available_technicians_for_site(
            db, auth_db, site_id, org_id)
        staff_user_ids = [tech.user_id for tech in available_technicians]

        # Base query filter - ALL data filtered by site_id AND staff_user_ids
        base_filter = [
            Ticket.site_id == site_id,
            Ticket.org_id == org_id,
            Ticket.status != TicketStatus.CLOSED  # Exclude closed tickets
        ]

        # 2. Get Technician Workload Summary - ONLY NON-ADMIN/NON-ORGANIZATION site staff
        workload_query = db.query(
            Ticket.assigned_to,
            func.count(Ticket.id).label('total_tickets'),
            func.sum(case((Ticket.status == TicketStatus.OPEN, 1), else_=0)).label(
                'open_tickets'),
            func.sum(case((Ticket.status == TicketStatus.IN_PROGRESS, 1), else_=0)).label(
                'in_progress_tickets'),
            func.sum(case((Ticket.status == TicketStatus.ESCALATED, 1), else_=0)).label(
                'escalated_tickets')
        ).filter(
            *base_filter,
            Ticket.assigned_to.isnot(None),
            Ticket.assigned_to.in_(staff_user_ids)  # ✅ ONLY site staff
        ).group_by(Ticket.assigned_to)

        technicians_workload = []
        for workload in workload_query.all():
            # Get technician name from auth database
            user = auth_db.query(Users).filter(
                Users.id == workload.assigned_to
            ).first()
            
            # ✅ ONLY count if assignee is NOT ORGANIZATION and NOT ADMIN
            if user and user.account_type.lower() not in ["organization", "admin"]:
                technician_name = user.full_name if user else f"User {workload.assigned_to}"

                technicians_workload.append(TechnicianWorkloadSummary(
                    technician_id=workload.assigned_to,
                    technician_name=technician_name,
                    total_tickets=workload.total_tickets or 0,
                    open_tickets=workload.open_tickets or 0,
                    in_progress_tickets=workload.in_progress_tickets or 0,
                    escalated_tickets=workload.escalated_tickets or 0
                ))

        # 3. Get All Assigned Tickets - ONLY assigned to NON-ADMIN/NON-ORGANIZATION site staff
        assigned_tickets_query = db.query(Ticket).options(
            joinedload(Ticket.category)
        ).filter(
            *base_filter,
            Ticket.assigned_to.isnot(None),
            # ✅ ONLY tickets assigned to site staff
            Ticket.assigned_to.in_(staff_user_ids)
        ).order_by(Ticket.created_at.desc())

        assigned_tickets = []
        for ticket in assigned_tickets_query.all():
            # Get technician name from auth database
            user = auth_db.query(Users).filter(
                Users.id == ticket.assigned_to
            ).first()
            
            # ✅ ONLY include if assignee is NOT ORGANIZATION and NOT ADMIN type
            if user and user.account_type.lower() not in ["organization", "admin"]:
                technician_name = user.full_name if user else f"User {ticket.assigned_to}"
                
                assigned_tickets.append(AssignedTicketOut(
                    id=ticket.id,
                    ticket_no=ticket.ticket_no,
                    title=ticket.title,
                    category=ticket.category.category_name if ticket.category else "Unknown",
                    assigned_to=ticket.assigned_to,
                    technician_name=technician_name,
                    status=ticket.status.value if hasattr(ticket.status, 'value') else ticket.status,
                    priority=ticket.priority,
                    created_at=ticket.created_at,
                    is_overdue=ticket.is_overdue,
                    can_escalate=ticket.can_escalate
                ))

        # 4. Get All "Unassigned" Tickets - Actually assigned to ADMIN/ORGANIZATION users
        # ✅ Since assigned_to is never NULL, "unassigned" means assigned to ADMIN/ORGANIZATION
        unassigned_tickets_query = db.query(Ticket).options(
            joinedload(Ticket.category).joinedload(TicketCategory.sla_policy)
        ).filter(
            *base_filter,
            Ticket.status == TicketStatus.OPEN,  # Typically "unassigned" tickets are OPEN
            Ticket.assigned_to.isnot(None)  # All tickets have assignee
        ).order_by(Ticket.created_at.desc())

        unassigned_tickets = []
        for ticket in unassigned_tickets_query.all():
            # Get the assigned user
            assigned_user = auth_db.query(Users).filter(
                Users.id == ticket.assigned_to
            ).first()
            
            # ✅ CORRECTED: Only include tickets assigned to organization/admin users
            if assigned_user and assigned_user.account_type.lower() in ["organization", "admin"]:
                # Get default contact from SLA
                default_contact = None
                default_contact_name = None
                if ticket.category and ticket.category.sla_policy:
                    default_contact = ticket.category.sla_policy.default_contact
                    if default_contact:
                        default_user = auth_db.query(Users).filter(
                            Users.id == default_contact
                        ).first()
                        default_contact_name = default_user.full_name if default_user else None
                
                unassigned_tickets.append(UnassignedTicketOut(
                    id=ticket.id,
                    ticket_no=ticket.ticket_no,
                    title=ticket.title,
                    category=ticket.category.category_name if ticket.category else "Unknown",
                    status=ticket.status.value if hasattr(ticket.status, 'value') else ticket.status,
                    priority=ticket.priority,
                    created_at=ticket.created_at,
                    is_overdue=ticket.is_overdue,
                    default_contact=default_contact,
                    default_contact_name=default_contact_name
                ))
        return TeamWorkloadManagementResponse(
            technicians_workload=technicians_workload,
            assigned_tickets=assigned_tickets,
            unassigned_tickets=unassigned_tickets,
            available_technicians=available_technicians,
            total_assigned=len(assigned_tickets),
            total_unassigned=len(unassigned_tickets)
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching team workload management data: {str(e)}")



def get_available_technicians_for_site(
    db: Session,
    auth_db: Session,
    site_id: UUID,
    org_id: UUID
) -> List[TechnicianOut]:
    """
    Get available technicians for a site (for dropdowns) using StaffSite + Users
    """
    try:

        # Step 1: Get all user_ids from staff_sites for this site_id and org_id
        staff_sites = (
            db.query(StaffSite)
            .filter(
                and_(
                    StaffSite.site_id == site_id,
                    StaffSite.org_id == org_id,
                    StaffSite.is_deleted == False
                )
            )
            .all()
        )

        if not staff_sites:
            return []  # No staff assigned to this site

        # Step 2: Extract user_ids
        user_ids = [staff.user_id for staff in staff_sites]

        # Step 3: Fetch all user details from auth db
        users = (
            auth_db.query(Users.id, Users.full_name, Users.email, Users.phone)
            .filter(Users.id.in_(user_ids))
            .all()
        )

        # Step 4: Return as TechnicianOut objects
        available_technicians = []
        for user in users:
            available_technicians.append(TechnicianOut(
                user_id=user.id,
                full_name=user.full_name,
                email=user.email,
                phone=user.phone
            ))

        return available_technicians

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching available technicians: {str(e)}")
