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
def build_sla_policies_filters(org_id: UUID, params: SlaPolicyRequest):
    filters = [
        SlaPolicy.is_deleted == False,
        SlaPolicy.org_id == org_id  # ✅ ALWAYS filter by org_id
    ]

    # ✅ SITE FILTER - Show policies for specific site or all sites in org
    if params.site_id and params.site_id.lower() != "all":
        filters.append(SlaPolicy.site_id == params.site_id)
    # If "all" or no site_id, show all sites within the org (no additional filter)

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
# ---------------- Get All ----------------
def get_sla_policies(
    db: Session,
    auth_db: Session,
    org_id: UUID,
    params: SlaPolicyRequest
) -> SlaPolicyListResponse:

    filters = build_sla_policies_filters(org_id, params)

    base_query = (
        db.query(SlaPolicy)
        .join(Site, SlaPolicy.site_id == Site.id, isouter=True)
        .join(SlaPolicy.org, isouter=True)
        .filter(*filters)
    )

    total = base_query.count()

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

    results = []
    for policy in sla_policies:
        # ✅ FIXED: Use correct field names (without _id suffix)
        default_contact_name = None
        escalation_contact_name = None
        
        if policy.default_contact:  # ✅ NOT default_contact_id
            default_user = auth_db.query(Users.full_name).filter(
                Users.id == policy.default_contact,  # ✅ NOT default_contact_id
                Users.is_deleted == False
            ).first()
            default_contact_name = default_user.full_name if default_user else None
            
        if policy.escalation_contact:  # ✅ NOT escalation_contact_id
            escalation_user = auth_db.query(Users.full_name).filter(
                Users.id == policy.escalation_contact,  # ✅ NOT escalation_contact_id
                Users.is_deleted == False
            ).first()
            escalation_contact_name = escalation_user.full_name if escalation_user else None
        
        policy_out = SlaPolicyOut.model_validate({
            **policy.__dict__,
            "site_name": policy.site.name if policy.site else None,
            "org_name": policy.org.name if policy.org else None,
            "default_contact_name": default_contact_name,
            "escalation_contact_name": escalation_contact_name
        })
        results.append(policy_out)

    return {
        "sla_policies": results,
        "total": total
    }

# ---------------- Overview Endpoint ----------------
# ---------------- Overview Endpoint ----------------
def get_sla_policies_overview(db: Session, org_id: UUID, site_id: Optional[UUID] = None) -> SlaPolicyOverviewResponse:
    """
    Calculate overview statistics for SLA policies - CONSISTENT with site filtering
    """
    # Base filter - always by org_id
    base_filters = [
        SlaPolicy.is_deleted == False,
        SlaPolicy.org_id == org_id
    ]
    
    # ✅ Apply site filter to overview if provided
    if site_id and site_id != "all":
        base_filters.append(SlaPolicy.site_id == site_id)

    # Total SLA policies count - filtered by org_id and optional site
    total_policies_count = db.query(SlaPolicy).filter(*base_filters).count()

    # ✅ CHANGED: Count of ACTIVE SLA policies with proper field name
    active_policies_count = db.query(SlaPolicy).filter(
        *base_filters,
        SlaPolicy.active == True  # ✅ Only count active policies
    ).count()

    # Average response time - with same filters
    avg_response_time_result = db.query(func.avg(SlaPolicy.response_time_mins)).filter(*base_filters).scalar()
    
    avg_response_time_minutes = float(avg_response_time_result) if avg_response_time_result else 0.0

    return {
        "total_sla_policies": total_policies_count,
        "active_sla_policies": active_policies_count,  # ✅ CHANGED FIELD NAME
        "average_response_time": avg_response_time_minutes
    }

# ---------------- Helper function for getting policy with site and org ----------------
def get_sla_policy_with_site_org(db: Session, auth_db: Session, policy_id: UUID):
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
        # ✅ FIXED: Use correct field names (without _id suffix)
        default_contact_name = None
        escalation_contact_name = None
        
        if policy.default_contact:  # ✅ NOT default_contact_id
            default_user = auth_db.query(Users.full_name).filter(
                Users.id == policy.default_contact,  # ✅ NOT default_contact_id
                Users.is_deleted == False
            ).first()
            default_contact_name = default_user.full_name if default_user else None
            
        if policy.escalation_contact:  # ✅ NOT escalation_contact_id
            escalation_user = auth_db.query(Users.full_name).filter(
                Users.id == policy.escalation_contact,  # ✅ NOT escalation_contact_id
                Users.is_deleted == False
            ).first()
            escalation_contact_name = escalation_user.full_name if escalation_user else None
        
        return SlaPolicyOut.model_validate({
            **policy.__dict__,
            "site_name": policy.site.name if policy.site else None,
            "org_name": policy.org.name if policy.org else None,
            "default_contact_name": default_contact_name,
            "escalation_contact_name": escalation_contact_name
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
def update_sla_policy(db: Session, auth_db: Session, policy: SlaPolicyUpdate) -> SlaPolicyOut:  # ✅ ADD auth_db
    db_policy = get_sla_policy_by_id(db, policy.id)
    if not db_policy:
        return error_response(
            message="SLA policy not found",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=404
        )

    update_data = policy.model_dump(exclude_unset=True, exclude={'id'})
    
    if 'site_id' in update_data and update_data['site_id'] != db_policy.site_id:
        categories_with_sla = db.query(TicketCategory.id).filter(
            TicketCategory.sla_id == policy.id,
            TicketCategory.is_deleted == False
        ).subquery()
        
        has_active_tickets = db.query(Ticket).filter(
            Ticket.category_id.in_(categories_with_sla),
            Ticket.status.not_in(['closed', 'returned', 'escalated'])  
        ).first()
        
        if has_active_tickets:
            return error_response(
                message="Cannot update site for SLA policy with active tickets",
                status_code=str(AppStatusCode.OPERATION_ERROR),
                http_status=400
            )
    
    new_category = update_data.get('service_category')
    if new_category and new_category != db_policy.service_category:
        existing_policy = db.query(SlaPolicy).filter(
            SlaPolicy.service_category.ilike(new_category.strip()),
            SlaPolicy.site_id == db_policy.site_id,
            SlaPolicy.id != policy.id,
            SlaPolicy.is_deleted == False
        ).first()

        if existing_policy:
            return error_response(
                message=f"SLA policy '{new_category}' already exists for this site"
            )
    
    for key, value in update_data.items():
        setattr(db_policy, key, value)

    try:
        db.commit()
        # ✅ Return with contact names
        return get_sla_policy_with_site_org(db, auth_db, policy.id)  # ✅ PASS auth_db

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
def contact_lookup(db: Session, auth_db: Session, org_id: UUID, site_id: Optional[str] = None) -> List[Lookup]:
    """
    Fetch contacts for a given site.
    Includes:
      1. All staff users assigned to the site with status='active'
      2. All users with account_type='organization' and status='active'
    """
    if not site_id or not site_id.strip() or site_id.strip().lower() == "all":
        return []

    # Step 1: Fetch staff users with roles for this site
    staff_sites = (
        db.query(StaffSite.user_id, StaffSite.staff_role)
        .filter(
            StaffSite.org_id == org_id,
            StaffSite.site_id == site_id,
            StaffSite.is_deleted == False
        )
        .all()
    )

    staff_user_ids = [s.user_id for s in staff_sites if s.user_id]
    unique_staff_user_ids = list(set(staff_user_ids))
    # Step 2: Fetch staff user names from auth_db
    staff_users = []
    if unique_staff_user_ids:
        users = (
            auth_db.query(Users.id, Users.full_name)
            .filter(
                Users.id.in_(unique_staff_user_ids),
                Users.is_deleted == False,
                Users.status == "active"
            )
            .all()
        )

        # Map user_id -> full_name
        user_map = {u.id: u.full_name for u in users}

        # Map user_id -> role
        role_map = {s.user_id: s.staff_role for s in staff_sites}

        # Combine full name with role
        staff_users = [
            Lookup(
                id=user_id,
                name=f"{user_map.get(user_id, 'Unknown')} ({role_map.get(user_id, 'No Role')})"
            )
            for user_id in unique_staff_user_ids
            if user_id in user_map
        ]
    # Step 3:
    # Fetch all organization users with status='active'
    org_users = (
        auth_db.query(Users.id, Users.full_name)
        .filter(
            Users.org_id == org_id,
            Users.account_type == "organization",
            Users.status == "active",
            Users.is_deleted == False
        )
        .all()
    )

    # Convert org users to Lookup
    org_users_lookup = [Lookup(id=u.id, name=u.full_name) for u in org_users]

    # Combine staff (with roles) + org users
    all_users = staff_users + org_users_lookup

    # Return
    return all_users




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