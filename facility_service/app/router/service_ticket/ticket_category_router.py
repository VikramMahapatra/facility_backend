# routes/ticket_category_routes.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional

from facility_service.app.models.service_ticket.sla_policy import SlaPolicy
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token, UserToken
from shared.schemas import Lookup

from ...schemas.service_ticket.ticket_category_schemas import (
    TicketCategoryCreate,
    TicketCategoryUpdate,
    TicketCategoryOut,
    TicketCategoryListResponse
)
from ...crud.service_ticket import ticket_category_crud as crud

router = APIRouter(
    prefix="/api/ticket-category",
    tags=["Ticket Categories"],
    dependencies=[Depends(validate_current_token)]
)

# ---------------- Get All ----------------
@router.get("/all", response_model=TicketCategoryListResponse)
def get_ticket_categories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_ticket_categories(db, skip, limit, search)


# ---------------- Create ----------------
@router.post("/", response_model=None)
def create_ticket_category(
    category: TicketCategoryCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.create_ticket_category(db, category)

# ---------------- Update ----------------
@router.put("/", response_model=None)
def update_ticket_category(
    category: TicketCategoryUpdate,  
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.update_ticket_category(db, category)

# ---------------- Delete (Soft Delete) ----------------
@router.delete("/{category_id}")
def delete_ticket_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.delete_ticket_category_soft(db, category_id)

# ---------------- Auto Assign Role Lookup (Hardcoded Enum) ----------------
@router.get("/auto-assign-role-lookup", response_model=List[Lookup])
def auto_assign_role_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.auto_assign_role_lookup(db)

# ---------------- Status Lookup (Hardcoded Enum) ----------------
@router.get("/status-lookup", response_model=List[Lookup])
def status_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.status_lookup(db)


# ---------------- SLA Policy Lookup ----------------

@router.get("/sla-policy-lookup", response_model=List[Lookup])
def sla_policy_lookup(
    site_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.sla_policy_lookup(db, site_id)
