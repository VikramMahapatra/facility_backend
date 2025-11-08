# crud/service_ticket/ticket_category_crud.py
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from uuid import UUID
from typing import List, Optional
from datetime import datetime

from facility_service.app.models.service_ticket.sla_policy import SlaPolicy

from ...enum.ticket_service_enum import AutoAssignRoleEnum, StatusEnum
from ...schemas.service_ticket.ticket_category_schemas import TicketCategoryListResponse
from ...models.service_ticket.tickets_category import TicketCategory
from ...schemas.service_ticket.ticket_category_schemas import (
    TicketCategoryCreate,
    TicketCategoryUpdate,
    TicketCategoryOut
)
from shared.core.schemas import Lookup
from fastapi import HTTPException

# ---------------- Build Filters ----------------


def build_ticket_categories_filters(search: Optional[str] = None):
    # Always filter out soft deleted records
    filters = [TicketCategory.is_deleted == False]

    if search:
        search_term = f"%{search}%"
        filters.append(or_(
            TicketCategory.category_name.ilike(search_term),
            TicketCategory.auto_assign_role.ilike(search_term)
        ))

    return filters

# ---------------- Get All ----------------


def get_ticket_categories(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None
) -> TicketCategoryListResponse:

    filters = build_ticket_categories_filters(search)
    base_query = db.query(TicketCategory).filter(*filters)

    total = base_query.count()

    ticket_categories = (
        base_query
        .order_by(TicketCategory.category_name.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "ticket_categories": ticket_categories,
        "total": total
    }

# ---------------- Get By ID ----------------


def get_ticket_category_by_id(db: Session, category_id: UUID) -> Optional[TicketCategory]:
    return db.query(TicketCategory).filter(
        TicketCategory.id == category_id,
        TicketCategory.is_deleted == False  # Exclude soft deleted
    ).first()

# ---------------- Create ----------------


def create_ticket_category(db: Session, category: TicketCategoryCreate) -> TicketCategoryOut:
    db_category = TicketCategory(**category.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

# ---------------- Update ----------------


def update_ticket_category(db: Session, category: TicketCategoryUpdate) -> Optional[TicketCategoryOut]:
    db_category = get_ticket_category_by_id(db, category.id)
    if not db_category:
        return None

    # Update only the provided fields (excluding id since we already used it to find the record)
    update_data = category.model_dump(exclude_unset=True, exclude={'id'})
    for key, value in update_data.items():
        setattr(db_category, key, value)

    db.commit()
    db.refresh(db_category)
    return db_category

# ---------------- Soft Delete ----------------


def delete_ticket_category_soft(db: Session, category_id: UUID) -> bool:
    """
    Soft delete ticket category - set is_deleted to True
    Returns: True if deleted, False if not found
    """
    db_category = get_ticket_category_by_id(db, category_id)
    if not db_category:
        return False

    # Check if category has associated tickets
    if db_category.tickets:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete category with associated tickets"
        )

    # Soft delete
    db_category.is_deleted = True
    db_category.deleted_at = func.now()
    db.commit()
    return True

# ---------------- Auto Assign Role Lookup ----------------


def auto_assign_role_lookup(db: Session) -> List[Lookup]:
    return [
        Lookup(id=role.value, name=role.value.capitalize())
        for role in AutoAssignRoleEnum
    ]

# ---------------- Status Lookup ----------------


def status_lookup(db: Session) -> List[Lookup]:
    return [
        Lookup(id=status.value, name=status.value.capitalize())
        for status in StatusEnum
    ]


#-----------------sla policy------------------------
def sla_policy_lookup(db: Session, site_id: Optional[str] = None) -> List[Lookup]:
    """
    Fetch SLA policies filtered by site_id.
    Returns id and service_category as lookup values.
    """
    query = db.query(SlaPolicy.id, SlaPolicy.service_category).filter(SlaPolicy.is_deleted == False)

    if site_id and site_id.lower() != "all":
        query = query.filter(SlaPolicy.site_id == site_id)

    return [Lookup(id=row.id, name=row.service_category) for row in query.all()]