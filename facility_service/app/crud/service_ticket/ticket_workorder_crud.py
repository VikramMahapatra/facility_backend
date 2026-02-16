from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from uuid import UUID
from typing import List, Optional, Dict, Any
from datetime import datetime

from facility_service.app.crud.service_ticket.tickets_crud import fetch_role_admin
from facility_service.app.models.financials.tax_codes import TaxCode
from facility_service.app.models.maintenance_assets import work_order
from facility_service.app.models.system.notifications import Notification, NotificationType, PriorityType

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
from shared.core.schemas import Lookup, UserToken
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
        filters.append(func.lower(TicketWorkOrder.status)
                       == params.status.lower())

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
    auth_db: Session,
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
        db.query(TicketWorkOrder, Ticket.ticket_no,
                 Site.name.label('site_name'))
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
        # ------- Fetch Ticket (we need vendor_id & assigned_to) -------
        ticket = db.query(Ticket).filter(Ticket.id == wo.ticket_id).first()

        assigned_to_name = None
        vendor_name = None

        if ticket:
            # Assigned To Name from Ticket.assigned_to
            if ticket.assigned_to:
                assigned_user = (
                    auth_db.query(Users)
                    .filter(Users.id == ticket.assigned_to)
                    .first())
            assigned_to_name = assigned_user.full_name if assigned_user else None

            # Vendor Name from Ticket.vendor_id
            if ticket.vendor_id:
                vendor = db.query(Vendor).filter(
                    Vendor.id == ticket.vendor_id,
                    Vendor.is_deleted == False
                ).first()
                vendor_name = vendor.name if vendor else None

        work_order_out = TicketWorkOrderOut.model_validate({
            **wo.__dict__,
            "ticket_no": ticket_no,
            "site_name": site_name,
            "assigned_to_name": assigned_to_name,
            "vendor_name": vendor_name,
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
        db.query(TicketWorkOrder, Ticket.ticket_no,
                 Site.name.label('site_name'))
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
    auth_db: Session,
    work_order: TicketWorkOrderCreate,
    current_user: UserToken
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
            Ticket.org_id == current_user.org_id
        )
        .first()
    )

    if not ticket_data:
        return error_response(
            message="Associated ticket not found",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=404
        )

    # Unpack the tuple correctly
    ticket, site_name = ticket_data  # ticket_data is (Ticket, site_name)
    # Create work order
    labour = Decimal(work_order.labour_cost or 0)
    material = Decimal(work_order.material_cost or 0)
    other = Decimal(work_order.other_expenses or 0)

    base_amount = labour + material + other

    tax_rate = Decimal("0")
    if work_order.tax_code_id:
        tax = db.query(TaxCode).filter(
            TaxCode.id == work_order.tax_code_id,
            TaxCode.is_deleted == False
        ).first()
        if tax:
            tax_rate = tax.rate

    tax_amount = (base_amount * tax_rate) / Decimal("100")
    total_amount = base_amount + tax_amount

    db_work_order = TicketWorkOrder(
        **work_order.model_dump(exclude={"total_amount", "tax_code"}),
        total_amount=total_amount
    )
    db.add(db_work_order)
    db.commit()
    db.refresh(db_work_order)
    # ---------------- NOTIFICATION LOGIC ---------------- #

    # Fetch action user (creator of work order)
    action_by_user = auth_db.query(Users).filter(
        Users.id == current_user.user_id
    ).first()

    action_by_name = action_by_user.full_name if action_by_user else "Unknown User"

    recipient_ids = []

    # 1️⃣ Assigned to
    if ticket.assigned_to:
        recipient_ids.append(ticket.assigned_to)

    # 2️⃣ Ticket created for (Owner/Tenant)
    if ticket.user_id:
        recipient_ids.append(ticket.user_id)

    # Vendor (if any) — comes from Ticket
    if ticket.vendor_id:
        recipient_ids.append(ticket.vendor_id)

    # 4️⃣ Admin users
    admin_user_ids = fetch_role_admin(
        auth_db,
        current_user.org_id
    )

    if isinstance(admin_user_ids, list):
        recipient_ids.extend([a["user_id"] for a in admin_user_ids])

    recipient_ids = list(set(recipient_ids))

    # Create notifications
    notifications = []
    for recipient_id in recipient_ids:
        notification = Notification(
            user_id=recipient_id,
            type=NotificationType.alert,
            title="Work Order Created",
            message=f"Work order created for Ticket {ticket.ticket_no} by {action_by_name}",
            posted_date=datetime.utcnow(),
            priority=PriorityType(ticket.priority),
            read=False,
            is_deleted=False
        )
        notifications.append(notification)

    db.add_all(notifications)
    db.commit()

    # ---------------- END NOTIFICATION LOGIC ---------------- #
    # Replace the entire return block with:
    work_order_out = TicketWorkOrderOut(
        id=db_work_order.id,
        ticket_id=db_work_order.ticket_id,
        description=db_work_order.description,
        assigned_to=db_work_order.assigned_to,
        status=db_work_order.status,
        labour_cost=db_work_order.labour_cost,
        material_cost=db_work_order.material_cost,
        other_expenses=db_work_order.other_expenses,
        estimated_time=db_work_order.estimated_time,
        special_instructions=db_work_order.special_instructions,
        tax_code_id=db_work_order.tax_code_id,
        wo_no=db_work_order.wo_no,
        created_at=db_work_order.created_at,
        updated_at=db_work_order.updated_at,
        is_deleted=db_work_order.is_deleted,
        total_amount=db_work_order.total_amount,
        tax_code=db_work_order.tax_code.code if db_work_order.tax_code else None,
        ticket_no=ticket.ticket_no,
        site_name=site_name,
        assigned_to_name=None,  # You can fetch these if needed
        vendor_name=None
    )
    return work_order_out


# ---------------- Update ----------------
def update_ticket_work_order(
    db: Session,
    auth_db: Session,
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
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=404
        )

    db_work_order, ticket_no, site_name = work_order_data
    # Update fields (exclude id from update data)
    update_data = work_order_update.model_dump(
        exclude_unset=True, exclude={'id'})
    for key, value in update_data.items():
        setattr(db_work_order, key, value)
    labour = Decimal(db_work_order.labour_cost or 0)
    material = Decimal(db_work_order.material_cost or 0)
    other = Decimal(db_work_order.other_expenses or 0)

    base_amount = labour + material + other

    tax_rate = Decimal("0")
    if db_work_order.tax_code_id:
        tax = db.query(TaxCode).filter(
            TaxCode.id == db_work_order.tax_code_id,
            TaxCode.is_deleted == False
        ).first()
        if tax:
            tax_rate = tax.rate

    db_work_order.total_amount = base_amount + (
        base_amount * tax_rate / Decimal("100")
    )

    db.commit()
    db.refresh(db_work_order)

    return TicketWorkOrderOut(
        **db_work_order.__dict__,
        ticket_no=ticket_no,
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


def get_names_for_ticket_id(
    db: Session,
    auth_db: Session,
    ticket_id: UUID
) -> Optional[Dict[str, Any]]:

    ticket = (db.query(Ticket).filter(Ticket.id == ticket_id).first())
    if not ticket:
        return None

    assigned_to_id = ticket.assigned_to
    vendor_id = ticket.vendor_id

    assigned_to_name = None
    vendor_name = None

    if assigned_to_id:
        assigned_user = (auth_db.query(Users).filter(
            Users.id == assigned_to_id).first())
        if assigned_user:
            assigned_to_name = assigned_user.full_name

    if vendor_id:
        vendor = (db.query(Vendor).filter(
            Vendor.id == vendor_id, Vendor.is_deleted == False).first())
        if vendor:
            vendor_name = vendor.name
    return {
        "ticket_id": ticket_id,
        "assigned_to_id": assigned_to_id,
        "assigned_to_name": assigned_to_name,
        "vendor_id": vendor_id,
        "vendor_name": vendor_name
    }
