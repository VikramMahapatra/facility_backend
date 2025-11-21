from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional

from shared.core.database import get_auth_db, get_facility_db as get_db
from shared.core.auth import validate_current_token, UserToken
from shared.core.schemas import Lookup

from ...schemas.service_ticket.sla_policy_schemas import (
    SlaPolicyCreate,
    SlaPolicyRequest,
    SlaPolicyUpdate,
    SlaPolicyOut,
    SlaPolicyListResponse,
    SlaPolicyOverviewResponse
)
from ...crud.service_ticket import sla_policy_crud as crud

router = APIRouter(
    prefix="/api/sla-policies",
    tags=["SLA Policies"],
    dependencies=[Depends(validate_current_token)]
)


# ---------------- Get All ----------------
@router.get("/all", response_model=SlaPolicyListResponse)
def get_sla_policies_endpoint(
    params: SlaPolicyRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get SLA policies with search, site filter, org filter, and pagination
    Default: Show all SLA policies from all organizations
    """
    return crud.get_sla_policies(
        db=db,
        params=params
    )


# ---------------- Overview Endpoint ----------------
@router.get("/overview", response_model=SlaPolicyOverviewResponse)
def get_sla_policies_overview(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get SLA policies overview with statistics:
    - Total SLA policies count
    - Count of organizations across all sites
    - Average response time across all policies
    """
    return crud.get_sla_policies_overview(db, current_user.org_id)

# ---------------- Create ----------------
@router.post("/", response_model=SlaPolicyOut)
def create_sla_policy(
    policy: SlaPolicyCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.create_sla_policy(db, policy, current_user.org_id)


# ---------------- Update ----------------
@router.put("/", response_model=SlaPolicyOut)
def update_sla_policy(
    policy: SlaPolicyUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.update_sla_policy(db, policy)


# ---------------- Delete (Soft Delete) ----------------
@router.delete("/{policy_id}")
def delete_sla_policy(
    policy_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.delete_sla_policy_soft(db, policy_id)



# ---------------- Service Category Lookup ----------------
@router.get("/service-category-lookup", response_model=List[Lookup])
def get_service_category_lookup(
    site_id: Optional[str] = Query(None, description="Filter by site ID. Returns empty if no site_id provided."),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.service_category_lookup(db, site_id)


# ---------------- Default Contact Lookup ----------------
@router.get("/user-contact-lookup", response_model=List[Lookup])
def get_user_contact_lookup(
    site_id: Optional[str] = Query(None, description="Filter by site ID. Returns empty if no site_id provided."),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),  
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get default contacts (users) from staff_sites for dropdown/lookup.
    """
    return crud.contact_lookup(db, auth_db, site_id)




@router.get("/org-lookup", response_model=List[Lookup])
def get_org_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get all active organizations for dropdown/lookup.
    """
    return crud.get_org_lookup(db)