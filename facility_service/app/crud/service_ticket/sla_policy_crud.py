from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_
from uuid import UUID
from typing import List, Optional
from datetime import datetime

from facility_service.app.models.space_sites.orgs import Org
from shared.models.users import Users
from shared.helpers.json_response_helper import error_response
from shared.utils.app_status_code import AppStatusCode
from ...models.space_sites.sites import Site
from shared.core.config import Settings

from ...models.common.staff_sites import StaffSite
from ...models.service_ticket.tickets import Ticket
from ...models.service_ticket.sla_policy import SlaPolicy
from ...models.service_ticket.tickets_category import TicketCategory
from sqlalchemy.orm import joinedload
from ...schemas.service_ticket.sla_policy_schemas import (
    SlaPolicyCreate, 
    SlaPolicyUpdate, 
    SlaPolicyOut,
    SlaPolicyRequest,
    SlaPolicyListResponse,
    SlaPolicyOverviewResponse
)
from shared.core.schemas import CommonQueryParams, Lookup
from fastapi import HTTPException


# ---------------- Build Filters ----------------
def build_sla_policies_filters(params: SlaPolicyRequest):
    filters = [
        SlaPolicy.is_deleted == False
    ]

    # Organization filter - only apply if org_id is provided in params
    if params.org_id and params.org_id.lower() != "all":
        filters.append(SlaPolicy.org_id == params.org_id)
    # If no org_id filter, show all organizations (no org filter applied)

    # site filter
    if params.site_id and params.site_id.lower() != "all":
        filters.append(SlaPolicy.site_id == params.site_id)

    # Active status filter
    if params.active and params.active.lower() != "all":
        if params.active.lower() == "true":
            filters.append(SlaPolicy.active == True)
        elif params.active.lower() == "false":
            filters.append(SlaPolicy.active == False)

    # Search across service category and site name
    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(
            SlaPolicy.service_category.ilike(search_term),
            Site.name.ilike(search_term),
        ))

    return filters


# ---------------- Get All ----------------
def get_sla_policies(
    db: Session,
    params: SlaPolicyRequest
) -> SlaPolicyListResponse:

    filters = build_sla_policies_filters(params)

    # Base query with joins for site and org
    base_query = (
        db.query(SlaPolicy)
        .join(Site, SlaPolicy.site_id == Site.id, isouter=True)
        .join(SlaPolicy.org, isouter=True)
        .filter(*filters)
    )

    total = base_query.count()

    # Get policies with pagination and site + org relationships
    sla_policies = (
        base_query
        .options(
            joinedload(SlaPolicy.site),
            joinedload(SlaPolicy.org)
        )
        .order_by(SlaPolicy.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    # Convert to output schema with site name and org name
    results = []
    for policy in sla_policies:
        policy_out = SlaPolicyOut.model_validate({
            **policy.__dict__,
            "site_name": policy.site.name if policy.site else None,
            "org_name": policy.org.name if policy.org else None
        })
        results.append(policy_out)

    return {
        "sla_policies": results,
        "total": total
    }

# ---------------- Overview Endpoint ----------------
def get_sla_policies_overview(db: Session, org_id: UUID) -> SlaPolicyOverviewResponse:
    """
    Calculate overview statistics for SLA policies
    """
    # Total SLA policies count - filtered by org_id
    total_policies_count = db.query(SlaPolicy).filter(
        SlaPolicy.is_deleted == False,
        SlaPolicy.org_id == org_id
    ).count()

    # Count of organizations across all sites (distinct orgs with SLA policies)
    organizations_count = db.query(SlaPolicy.org_id).filter(
        SlaPolicy.is_deleted == False,
        SlaPolicy.org_id == org_id
    ).distinct().count()

    # Average response time across all policies - filtered by org_id
    avg_response_time_result = db.query(func.avg(SlaPolicy.response_time_mins)).filter(
        SlaPolicy.is_deleted == False,
        SlaPolicy.org_id == org_id
    ).scalar()
    
    avg_response_time_minutes = float(avg_response_time_result) if avg_response_time_result else 0.0
    
    # Format average response time directly in the function
    hours = int(avg_response_time_minutes // 60)
    remaining_minutes = int(avg_response_time_minutes % 60)
    
    if hours > 0 and remaining_minutes > 0:
        avg_response_time_formatted = f"{hours}h {remaining_minutes}min"
    elif hours > 0:
        avg_response_time_formatted = f"{hours}h"
    else:
        avg_response_time_formatted = f"{remaining_minutes}min"

    return {
        "total_sla_policies": total_policies_count,
        "total_organizations": organizations_count,
        "average_response_time": avg_response_time_formatted
    }

# ---------------- Helper function for getting policy with site and org ----------------
def get_sla_policy_with_site_org(db: Session, policy_id: UUID):
    policy = (
        db.query(SlaPolicy)
        .options(
            joinedload(SlaPolicy.site),
            joinedload(SlaPolicy.org)
        )
        .filter(
            SlaPolicy.id == policy_id,
            SlaPolicy.is_deleted == False
        )
        .first()
    )
    
    if policy:
        return SlaPolicyOut.model_validate({
            **policy.__dict__,
            "site_name": policy.site.name if policy.site else None,
            "org_name": policy.org.name if policy.org else None
        })
    return None


# ---------------- Get By ID ----------------
def get_sla_policy_by_id(db: Session, policy_id: UUID) -> Optional[SlaPolicy]:
    return db.query(SlaPolicy).filter(
        SlaPolicy.id == policy_id,
        SlaPolicy.is_deleted == False
    ).first()


# ---------------- Create ----------------
def create_sla_policy(db: Session, policy: SlaPolicyCreate, org_id: UUID) -> SlaPolicyOut:
    existing_policy = db.query(SlaPolicy).filter(
        SlaPolicy.service_category.ilike(policy.service_category.strip()),
        SlaPolicy.site_id == policy.site_id,
        SlaPolicy.org_id == org_id,
        SlaPolicy.is_deleted == False
    ).first()

    if existing_policy:
        return error_response(
            message=f"SLA policy '{policy.service_category}' already exists for this site"
        )

    # Add org_id to the policy data
    policy_data = policy.model_dump()
    policy_data['org_id'] = org_id
    
    db_policy = SlaPolicy(**policy_data)
    db.add(db_policy)
    db.commit()
    db.refresh(db_policy)
    return db_policy


# ---------------- Update ----------------
def update_sla_policy(db: Session, policy: SlaPolicyUpdate) -> SlaPolicyOut:

    db_policy = get_sla_policy_by_id(db, policy.id)
    if not db_policy:
        return error_response(
            message="SLA policy not found",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=404
        )

    # Exclude org_id from update data since it shouldn't be changed
    update_data = policy.model_dump(exclude_unset=True, exclude={'id'})
    
    # Check for duplicate service category within same org and site
    new_category = update_data.get('service_category')
    if new_category and new_category != db_policy.service_category:
        existing_policy = db.query(SlaPolicy).filter(
            SlaPolicy.service_category.ilike(new_category.strip()),
            SlaPolicy.site_id == db_policy.site_id,
            SlaPolicy.org_id == db_policy.org_id,  # Use existing org_id
            SlaPolicy.id != policy.id,
            SlaPolicy.is_deleted == False
        ).first()

        if existing_policy:
            return error_response(
                message=f"SLA policy '{new_category}' already exists for this site and organization",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )
    
    # Update fields
    for key, value in update_data.items():
        setattr(db_policy, key, value)

    try:
        db.commit()
        # Return updated policy with site and org names
        return get_sla_policy_with_site_org(db, policy.id)

    except IntegrityError as e:
        db.rollback()
        return error_response(
            message="Error updating SLA policy",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


# ---------------- Soft Delete ----------------
def delete_sla_policy_soft(db: Session, policy_id: UUID) -> bool:
    db_policy = get_sla_policy_by_id(db, policy_id)
    if not db_policy:
        return False

    # Check if policy has associated ticket categories
    associated_categories = db.query(TicketCategory).filter(
        TicketCategory.sla_id == policy_id,
        TicketCategory.is_deleted == False
    ).first()
    
    if associated_categories:
        return error_response(
            message="Cannot delete SLA policy with associated ticket categories",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR)
        )

    # Soft delete
    db_policy.is_deleted = True
    db.commit()
    return True


# ---------------- Service Category Lookup ----------------
def service_category_lookup(db: Session, site_id: Optional[str] = None) -> List[Lookup]:
    if not site_id or site_id.strip() == "" or site_id.lower() == "all":
        return []

    query = (
        db.query(
            SlaPolicy.id,
            SlaPolicy.service_category
        )
        .filter(
            SlaPolicy.is_deleted == False,
            SlaPolicy.active == True,
            SlaPolicy.site_id == site_id  
        )
        .distinct(SlaPolicy.service_category)
        .order_by(SlaPolicy.service_category.asc())
    )

    categories = query.all()

    return [
        Lookup(id=row.id, name=row.service_category)
        for row in categories
    ]

# ---------------- Contact Lookup (for both default and escalation) ----------------
def contact_lookup(db: Session, auth_db: Session, site_id: Optional[str] = None) -> List[Lookup]:
    """
    Fetch contacts (users) from staff_sites table.
    STRICTLY filtered by site_id - returns empty if no site_id provided.
    Uses auth_db for Users table.
    """
    # Return empty if no site_id or invalid site_id
    if not site_id or not site_id.strip() or site_id.strip().lower() == "all":
        return []

    # Step 1: Get user_ids from staff_sites for the given site
    staff_records = (
        db.query(StaffSite.user_id)
        .filter(
            StaffSite.is_deleted == False,
            StaffSite.site_id == site_id,
            StaffSite.user_id.isnot(None)
        )
        .distinct()
        .all()
    )

    if not staff_records:
        return []

    # Extract user_ids
    user_ids = [record.user_id for record in staff_records]

    # Step 2: Get user details from auth database
    users = (
        auth_db.query(Users.id, Users.full_name)
        .filter(
            Users.id.in_(user_ids),
            Users.is_deleted == False,
            Users.account_type == "organization" 
        )
        .order_by(Users.full_name.asc())
        .all()
    )

    return [
        Lookup(id=user.id, name=user.full_name)
        for user in users
    ]


# ---------------- Org Lookup (Simple) ----------------
def get_org_lookup(db: Session) -> List[Lookup]:
    """
    Get organizations for dropdown/lookup.
    """
    orgs = (
        db.query(Org.id, Org.name)
        .filter(Org.status == "active")
        .order_by(Org.name.asc())
        .all()
    )

    return [
        Lookup(id=org.id, name=org.name)
        for org in orgs
    ]