from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from uuid import UUID
from typing import List, Optional
from datetime import datetime

from ...models.procurement.vendors import Vendor
from shared.helpers.json_response_helper import error_response
from shared.utils.app_status_code import AppStatusCode
from shared.models.users import Users
from ...models.space_sites.sites import Site
from ...models.service_ticket.tickets import Ticket
from ...models.service_ticket.tickets_work_order import TicketWorkOrder
from ...schemas.service_ticket.ticket_work_order_schemas import (
    TicketWorkOrderCreate, 
    TicketWorkOrderUpdate, 
    TicketWorkOrderOut,
    TicketWorkOrderRequest,
    TicketWorkOrderListResponse,
    TicketWorkOrderOverviewResponse
)
from shared.core.schemas import Lookup
from ...enum.ticket_service_enum import TicketWorkOrderStatusEnum


# ---------------- Build Filters ----------------
def build_ticket_work_order_filters(org_id: UUID, params: TicketWorkOrderRequest):
    filters = [
        TicketWorkOrder.is_deleted == False,
        Site.org_id == org_id  
    ]

    
    if params.site_id and params.site_id.lower() != "all":
        filters.append(Ticket.site_id == params.site_id)
    # If "all" or no site_id, show all sites within the org (no additional filter)

    # ✅ STATUS FILTER - Show work orders for specific status or all statuses
    if params.status and params.status.lower() != "all":
        filters.append(func.lower(TicketWorkOrder.status) == params.status.lower())

    # Search across description, ticket number, and site name
    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(
            TicketWorkOrder.description.ilike(search_term),
            Ticket.ticket_no.ilike(search_term),
            Site.name.ilike(search_term),
        ))

    return filters


# ---------------- Get All ----------------
def get_ticket_work_orders(
    db: Session,
    org_id: UUID,
    params: TicketWorkOrderRequest
) -> TicketWorkOrderListResponse:

    filters = build_ticket_work_order_filters(org_id, params)

    # Base query with joins
    base_query = (
        db.query(TicketWorkOrder)
        .join(Ticket, TicketWorkOrder.ticket_id == Ticket.id)
        .join(Site, Ticket.site_id == Site.id)
        .filter(*filters)
    )

    total = base_query.count()

    # Get paginated data with all necessary joins
    work_orders_data = (
        db.query(TicketWorkOrder, Ticket.ticket_no, Site.name.label('site_name'))
        .join(Ticket, TicketWorkOrder.ticket_id == Ticket.id)
        .join(Site, Ticket.site_id == Site.id)
        .filter(*filters)
        .order_by(TicketWorkOrder.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    results = []
    for wo, ticket_no, site_name in work_orders_data:
        # ✅ Get assigned vendor name from VENDOR table
        assigned_to_name = None
        if wo.assigned_to:  # ✅ KEEP original field name
            vendor = db.query(Vendor).filter(
                Vendor.id == wo.assigned_to,  # ✅ KEEP original field name
                Vendor.is_deleted == False
            ).first()
            assigned_to_name = vendor.name if vendor else None
        
        work_order_out = TicketWorkOrderOut.model_validate({
            **wo.__dict__,
            "ticket_no": ticket_no,
            "site_name": site_name,
            "assigned_to_name": assigned_to_name
        })
        results.append(work_order_out)

    return TicketWorkOrderListResponse(
        work_orders=results,
        total=total
    )

# ---------------- Overview Endpoint ----------------
def get_ticket_work_orders_overview(db: Session, org_id: UUID, site_id: Optional[str] = None) -> TicketWorkOrderOverviewResponse:
    """
    Calculate overview statistics for ticket work orders with site filter
    """
    filters = [
        TicketWorkOrder.is_deleted == False,
        Site.org_id == org_id
    ]

    # Apply site filter if provided (same pattern as main query)
    if site_id and site_id.lower() != "all":
        filters.append(Ticket.site_id == site_id)

    base_query = (
        db.query(TicketWorkOrder)
        .join(Ticket, TicketWorkOrder.ticket_id == Ticket.id)
        .join(Site, Ticket.site_id == Site.id)
        .filter(*filters)
    )

    total_work_orders = base_query.count()
    pending_count = base_query.filter(
        TicketWorkOrder.status == TicketWorkOrderStatusEnum.PENDING.value
    ).count()
    in_progress_count = base_query.filter(
        TicketWorkOrder.status == TicketWorkOrderStatusEnum.IN_PROGRESS.value
    ).count()
    completed_count = base_query.filter(
        TicketWorkOrder.status == TicketWorkOrderStatusEnum.COMPLETED.value
    ).count()

    return TicketWorkOrderOverviewResponse(
        total_work_orders=total_work_orders,
        pending=pending_count,
        in_progress=in_progress_count,
        completed=completed_count
    )


# ---------------- Get By ID ----------------
def get_ticket_work_order_by_id(
    db: Session,  
    work_order_id: UUID
) -> Optional[TicketWorkOrderOut]:
    
    work_order_data = (
        db.query(TicketWorkOrder, Ticket.ticket_no, Site.name.label('site_name'))
        .join(Ticket, TicketWorkOrder.ticket_id == Ticket.id)
        .join(Site, Ticket.site_id == Site.id)
        .filter(
            TicketWorkOrder.id == work_order_id,
            TicketWorkOrder.is_deleted == False
        )
        .first()
    )
    
    if work_order_data:
        wo, ticket_no, site_name = work_order_data
        
        # ✅ FIX: Get assigned vendor name from WORK ORDER's assigned_to from VENDOR table
        assigned_to_name = None
        if wo.assigned_to:
            vendor = db.query(Vendor).filter(
                Vendor.id == wo.assigned_to,
                Vendor.is_deleted == False  # Add soft delete filter if needed
            ).first()
            assigned_to_name = vendor.name if vendor else None

        return TicketWorkOrderOut.model_validate({
            **wo.__dict__,    
            "ticket_no": ticket_no,
            "assigned_to_name": assigned_to_name,
            "site_name": site_name
        })
    
    return None

def create_ticket_work_order(
    db: Session, 
    work_order: TicketWorkOrderCreate,
    org_id: UUID
) -> TicketWorkOrderOut:
    
    # Get ticket with site info
    ticket_data = (
        db.query(
            Ticket,
            Site.name.label('site_name')
        )
        .outerjoin(Site, Ticket.site_id == Site.id)
        .filter(
            Ticket.id == work_order.ticket_id,
            Ticket.org_id == org_id
        )
        .first()
    )
    
    if not ticket_data:
        return error_response(
            message="Associated ticket not found",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=404
        )
    
    ticket, site_name = ticket_data
    
    # ✅ FIX: Get assigned vendor name from WORK ORDER's assigned_to from VENDOR table
    assigned_to_name = None
    if work_order.assigned_to:
        vendor = db.query(Vendor).filter(
            Vendor.id == work_order.assigned_to,
            Vendor.is_deleted == False  # Add soft delete filter if needed
        ).first()
        assigned_to_name = vendor.name if vendor else None

    # Create work order
    db_work_order = TicketWorkOrder(**work_order.model_dump())
    db.add(db_work_order)
    db.commit()
    db.refresh(db_work_order)
    
    return TicketWorkOrderOut(
        **db_work_order.__dict__,
        ticket_no=ticket.ticket_no,
        assigned_to_name=assigned_to_name,  # This will now come from Vendor table
        site_name=site_name
    )


# ---------------- Update ----------------
def update_ticket_work_order(
    db: Session, 
    work_order_update: TicketWorkOrderUpdate,
    org_id: UUID
) -> TicketWorkOrderOut:
    
    # Get existing work order with relationships
    work_order_data = (
        db.query(
            TicketWorkOrder, 
            Ticket.ticket_no, 
            Site.name.label('site_name')
        )
        .join(Ticket, TicketWorkOrder.ticket_id == Ticket.id)
        .join(Site, Ticket.site_id == Site.id)
        .filter(
            TicketWorkOrder.id == work_order_update.id,  # Use ID from request body
            TicketWorkOrder.is_deleted == False,
            Ticket.org_id == org_id  # Organization security
        )
        .first()
    )
    
    if not work_order_data:
        return error_response(
            message="Work order not found",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=404
        )
    
    db_work_order, ticket_no, site_name = work_order_data

    # Update fields (exclude id from update data)
    update_data = work_order_update.model_dump(exclude_unset=True, exclude={'id'})
    for key, value in update_data.items():
        setattr(db_work_order, key, value)

    db.commit()
    db.refresh(db_work_order)
    
    # Get assigned vendor name
    assigned_to_name = None
    if db_work_order.assigned_to:
        vendor = db.query(Vendor).filter(
            Vendor.id == db_work_order.assigned_to,
            Vendor.is_deleted == False
        ).first()
        assigned_to_name = vendor.name if vendor else None
    
    # Return complete response like create endpoint
    return TicketWorkOrderOut(
        **db_work_order.__dict__,
        ticket_no=ticket_no,
        assigned_to_name=assigned_to_name,
        site_name=site_name
    )



# ---------------- Soft Delete ----------------
def delete_ticket_work_order_soft(db: Session, work_order_id: UUID):
    db_work_order = db.query(TicketWorkOrder).filter(
        TicketWorkOrder.id == work_order_id,
        TicketWorkOrder.is_deleted == False
    ).first()
    
    if not db_work_order:
        return error_response(
            message="Work order not found",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=404
        )

    db_work_order.is_deleted = True
    db_work_order.updated_at = func.now()
    db.commit()
    
    return {"message": "Work order deleted successfully"}



# ---------------- Filter Work Orders by Status ----------------
def ticket_work_orders_filter_status_lookup(db: Session, org_id: str, status: Optional[str] = None):
    query = (
        db.query(
            TicketWorkOrder.status.label("id"),
            TicketWorkOrder.status.label("name")
        )
        .join(Ticket)
        .filter(Ticket.org_id == org_id, TicketWorkOrder.is_deleted == False)
        .distinct()
        .order_by(TicketWorkOrder.status.asc())
    )
    if status:
        query = query.filter(TicketWorkOrder.status == status)

    return query.all()



# ---------------- Status Lookup ----------------
def ticket_work_order_status_lookup(db: Session, org_id: UUID) -> List[Lookup]:
    return [
        Lookup(id=status.value, name=status.name.capitalize())
        for status in TicketWorkOrderStatusEnum
    ]


def ticket_lookup_for_work_orders(db: Session, org_id: UUID) -> List[Lookup]:
    """
    Get tickets for work order creation dropdown
    Shows all open/in-progress tickets (regardless of whether they already have work orders)
    """
    tickets = (
        db.query(
            Ticket.id.label("id"),
            func.concat(Ticket.ticket_no, ' - ', Ticket.title).label("name")
        )
        .filter(
            Ticket.org_id == org_id,
            Ticket.status.in_(['open', 'in_progress'])  # Only active tickets
        )
        .order_by(Ticket.ticket_no.asc())
        .all()
    )
    return [Lookup(id=str(ticket.id), name=ticket.name) for ticket in tickets]







# ---------------- Site Lookup (for dropdown) ----------------
def site_lookup(db: Session, org_id: UUID) -> List[Lookup]:
    """
    Get sites for dropdown filter
    """
    sites = (
        db.query(Site.id, Site.name)
        .filter(
            Site.org_id == org_id,
            Site.is_deleted == False
        )
        .order_by(Site.name.asc())
        .all()
    )
    
    return [Lookup(id=site.id, name=site.name) for site in sites]


# ---------------- Contact Lookup ----------------
def contact_lookup(auth_db: Session) -> List[Lookup]:
    """
    Fetch contacts for work order assignment
    """
    users = (
        auth_db.query(Users.id, Users.full_name)
        .filter(
            Users.is_deleted == False,
            Users.status == "active"
        )
        .order_by(Users.full_name.asc())
        .all()
    )
    
    return [Lookup(id=user.id, name=user.full_name) for user in users]