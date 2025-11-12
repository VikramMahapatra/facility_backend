# crud/service_ticket/ticket_category_crud.py
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_
from uuid import UUID
from typing import List, Optional
from datetime import datetime

from auth_service.app.models.users import Users
from shared.core.config import Settings

from ...models.common.staff_sites import StaffSite
from ...models.service_ticket.tickets import Ticket
from ...models.service_ticket.sla_policy import SlaPolicy

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
        .order_by(TicketCategory.updated_at.desc())
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
    # Check for duplicate category name for the same site
    existing_category = db.query(TicketCategory).filter(
        TicketCategory.category_name.ilike(category.category_name.strip()),
        TicketCategory.site_id == category.site_id,
        TicketCategory.is_deleted == False
    ).first()
    
    if existing_category:
        raise HTTPException(
            status_code=400,
            detail=f"Ticket category '{category.category_name}' already exists for this site"
        )
    
    db_category = TicketCategory(**category.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

# ---------------- Update ----------------
def update_ticket_category(db: Session, category: TicketCategoryUpdate) -> TicketCategoryOut:
    db_category = get_ticket_category_by_id(db, category.id)
    if not db_category:
        raise HTTPException(
            status_code=404,
            detail="Ticket category not found"
        )

    update_data = category.model_dump(exclude_unset=True, exclude={'id'})
    
    # Check for duplicate category name
    new_name = update_data.get('category_name')
    if new_name and new_name != db_category.category_name:
        if db.query(TicketCategory).filter(
            TicketCategory.category_name.ilike(new_name.strip()),
            TicketCategory.site_id == db_category.site_id,
            TicketCategory.id != category.id,
            TicketCategory.is_deleted == False
        ).first():
            raise HTTPException(
                status_code=400,
                detail=f"Ticket category '{new_name}' already exists for this site"
            )

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





#-----------------get Employee------------------------

# Add this to your existing ticket_crud.py file

def get_employees_by_ticket(db: Session, auth_db: Session, ticket_id: str):
    """
    Get all employees for a ticket based on site_id from staff_sites table
    Simplified version - returns users directly
    """
    # Step 1: Fetch ticket with related data
    ticket = (
        db.query(Ticket)
        .filter(Ticket.id == ticket_id)
        .first()
    )

    if not ticket:
        raise HTTPException(
            status_code=404, detail="Ticket not found")

    # Step 2: Get site_id and org_id from ticket
    site_id = ticket.site_id
    org_id = ticket.org_id

    if not site_id or not org_id:
        return []  # No site or org associated with ticket

    # Step 3: Get all user_ids from staff_sites for this site_id and org_id
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

    # Step 4: Extract user_ids
    user_ids = [staff.user_id for staff in staff_sites]

    # Step 5: Fetch all user names from auth db and return directly
    users = (
        auth_db.query(Users.id, Users.full_name)
        .filter(Users.id.in_(user_ids))
        .all()
    )
    
    # Return directly -
    return [
        {
            "user_id": user.id,
            "full_name": user.full_name
        }
        for user in users
    ]
    
    
def category_lookup(db: Session, site_id: Optional[str] = None) -> List[Lookup]:
    """
    Fetch DISTINCT ticket categories filtered by site_id.
    Returns unique category names.
    """
    query = db.query(TicketCategory.id, TicketCategory.category_name).filter(
        TicketCategory.is_deleted == False,
        TicketCategory.is_active == True
    )

    if site_id and site_id.lower() != "all":
        query = query.filter(TicketCategory.site_id == site_id)

    # Get all categories first
    categories = query.order_by(TicketCategory.category_name).all()
    
    # Remove duplicates by category name, keeping the first occurrence
    seen = set()
    distinct_categories = []
    
    for row in categories:
        if row.category_name not in seen:
            seen.add(row.category_name)
            distinct_categories.append(row)
    
    return [Lookup(id=row.id, name=row.category_name) for row in distinct_categories]