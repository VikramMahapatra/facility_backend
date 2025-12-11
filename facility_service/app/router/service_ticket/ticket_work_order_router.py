from fastapi import APIRouter, Depends, Query, HTTPException, Path
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional

from shared.core.database import get_auth_db, get_facility_db as get_db
from shared.core.auth import validate_current_token, UserToken
from shared.core.schemas import Lookup

from ...schemas.service_ticket.ticket_work_order_schemas import (
    TicketWorkOrderCreate,
    TicketWorkOrderUpdate, 
    TicketWorkOrderOut,
    TicketWorkOrderRequest,
    TicketWorkOrderListResponse,
    TicketWorkOrderOverviewResponse
)
from ...crud.service_ticket import ticket_workorder_crud as crud

router = APIRouter(
    prefix="/api/ticket-work-orders",
    tags=["Ticket Work Orders"],
    dependencies=[Depends(validate_current_token)]
)



# ---------------- Create ----------------
@router.post("/", response_model=TicketWorkOrderOut)
def create_ticket_work_order_endpoint(
    work_order:TicketWorkOrderCreate,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Create a new work order from a ticket"""
    return crud.create_ticket_work_order(db,auth_db, work_order, current_user.org_id)







# ---------------- Get All (with filters) ----------------
@router.get("/all", response_model=TicketWorkOrderListResponse)
def get_ticket_work_orders_endpoint(
    params: TicketWorkOrderRequest = Depends(),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get all ticket work orders with search, site filter, status filter, and pagination
    Example: /api/ticket-work-orders?site_id=123&status=pending&search=outlet
    """
    return crud.get_ticket_work_orders(
        db=db,
        auth_db=auth_db,
        org_id=current_user.org_id,
        params=params
    )


# ---------------- Overview Statistics ----------------
@router.get("/overview", response_model=TicketWorkOrderOverviewResponse)
def get_ticket_work_orders_overview_endpoint(
    site_id: Optional[str] = Query("all", description="Filter by site ID"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get overview statistics for ticket work orders with site filter
    """
    return crud.get_ticket_work_orders_overview(
        db=db,
        org_id=current_user.org_id,
        site_id=site_id
    )

@router.get("/filter-status-lookup", response_model=List[Lookup])
def ticket_work_orders_filter_status_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.ticket_work_orders_filter_status_lookup(db, current_user.org_id)
# ---------------- Get By ID ----------------
@router.get("/{work_order_id}", response_model=TicketWorkOrderOut)
def get_ticket_work_order_by_id_endpoint(
    work_order_id: UUID = Path(..., description="Work Order ID (UUID)"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get a specific ticket work order by ID
    """
    work_order = crud.get_ticket_work_order_by_id(db, work_order_id)
    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")
    return work_order





# ---------------- Update ----------------
@router.put("/", response_model=TicketWorkOrderOut)  # No ID in path
def update_ticket_work_order_endpoint(
    work_order_update: TicketWorkOrderUpdate,  # Remove Path parameter
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Update a ticket work order
    """
    return crud.update_ticket_work_order(
        db=db, 
        auth_db=auth_db,
        work_order_update=work_order_update,
        org_id=current_user.org_id
    )


# ---------------- Delete (Soft Delete) ----------------
@router.delete("/{work_order_id}")
def delete_ticket_work_order_endpoint(
    work_order_id: UUID = Path(..., description="Work Order ID (UUID)"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Soft delete a ticket work order
    """
    return crud.delete_ticket_work_order_soft(db, work_order_id)





# ---------------- Status Lookup ----------------
@router.get("/lookup/status", response_model=List[Lookup])
def ticket_work_order_status_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.ticket_work_order_status_lookup(db, current_user.org_id)



@router.get("/lookup/tickets", response_model=List[Lookup])
def ticket_lookup_for_work_orders_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get tickets for work order creation dropdown
    Shows all open/in-progress tickets
    """
    return crud.ticket_lookup_for_work_orders(db, current_user.org_id)





# ---------------- Site Lookup ----------------
@router.get("/lookup/sites", response_model=List[Lookup])
def site_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get sites for dropdown filter
    """
    return crud.site_lookup(db, current_user.org_id)


# ---------------- Contact Lookup ----------------
@router.get("/lookup/contacts", response_model=List[Lookup])
def contact_lookup_endpoint(
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get contacts for work order assignment
    """
    return crud.contact_lookup(auth_db)


@router.get("/tickets/{ticket_id}/assignments")
def read_ticket_assignments(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_names_for_ticket_id(db=db,auth_db=auth_db, ticket_id=ticket_id)