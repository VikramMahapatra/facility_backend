# crud/service_ticket/ticket_category_crud.py
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_
from uuid import UUID
from typing import List, Optional
from datetime import datetime

from auth_service.app.models.users import Users
from shared.helpers.json_response_helper import error_response
from shared.utils.app_status_code import AppStatusCode
from facility_service.app.models.space_sites.sites import Site
from shared.core.config import Settings

from ...models.common.staff_sites import StaffSite
from ...models.service_ticket.tickets import Ticket
from ...models.service_ticket.sla_policy import SlaPolicy
from sqlalchemy.orm import joinedload
from ...enum.ticket_service_enum import AutoAssignRoleEnum, StatusEnum
from ...schemas.service_ticket.ticket_category_schemas import TicketCategoryListResponse, TicketCategoryRequest
from ...models.service_ticket.tickets_category import TicketCategory
from ...schemas.service_ticket.ticket_category_schemas import (
    TicketCategoryCreate,
    TicketCategoryUpdate,
    TicketCategoryOut
)
from shared.core.schemas import Lookup
from fastapi import HTTPException



# ---------------- Build Filters ----------------
def build_ticket_categories_filters(org_id: UUID, params: TicketCategoryRequest):
    filters = [
        TicketCategory.is_deleted == False,
        Site.org_id == org_id  
    ]

    # site filter
    if params.site_id and params.site_id.lower() != "all":
        filters.append(TicketCategory.site_id == params.site_id)

    # Active status filter
    if params.is_active and params.is_active.lower() != "all":
        if params.is_active.lower() == "true":
            filters.append(TicketCategory.is_active == True)
        elif params.is_active.lower() == "false":
            filters.append(TicketCategory.is_active == False)

    # Search across category name and auto assign role
    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(
            TicketCategory.category_name.ilike(search_term),
            TicketCategory.auto_assign_role.ilike(search_term),
            Site.name.ilike(search_term)
        ))

    return filters

# ---------------- Get All ----------------
def get_ticket_categories(
    db: Session,
    org_id: UUID, 
    params: TicketCategoryRequest
) -> TicketCategoryListResponse:

    filters = build_ticket_categories_filters(org_id, params)  
    
    # Base query with joins for site
    base_query = (
        db.query(TicketCategory)
        .join(Site, TicketCategory.site_id == Site.id, isouter=True)
        .filter(*filters)
    )

    total = base_query.count()

    # Get categories with pagination and site relationship
    ticket_categories = (
        base_query
        .options(joinedload(TicketCategory.site))
        .order_by(TicketCategory.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    # Convert to output schema with site name
    results = []
    for category in ticket_categories:
        category_out = TicketCategoryOut.model_validate({
            **category.__dict__,
            "site_name": category.site.name if category.site else None
        })
        results.append(category_out)

    return {
        "ticket_categories": results,
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
       return error_response (
        message="Cannot delete category with associated tickets",
        status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR)
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
    Strictly fetch SLA policies filtered by site_id.
    Returns SLA policies only for that specific site.
    """

    if not site_id or site_id.lower() == "all":
        # STRICT MODE: do NOT return all policies
        return []

    query = (
        db.query(SlaPolicy.id, SlaPolicy.service_category)
        .filter(
            SlaPolicy.is_deleted == False,
            SlaPolicy.site_id == site_id   # STRICT FILTER HERE
        )
        .order_by(SlaPolicy.service_category.asc())  # ASCENDING ORDER
    )

    policies = query.all()

    return [
        Lookup(id=row.id, name=row.service_category)
        for row in policies
    ]





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
    Strictly fetch ticket categories filtered by site_id.
    Returns distinct category names sorted ASC.
    """

    if not site_id or site_id.lower() == "all":
        return []

    query = (
        db.query(
            TicketCategory.id,
            TicketCategory.category_name
        )
        .filter(
            TicketCategory.is_deleted == False,
            TicketCategory.is_active == True,
            TicketCategory.site_id == site_id
        )
        .order_by(
            TicketCategory.category_name.asc()
        )
        .distinct(
            TicketCategory.category_name
        )
    )

    categories = query.all()

    return [
        Lookup(id=row.id, name=row.category_name)
        for row in categories
    ]
