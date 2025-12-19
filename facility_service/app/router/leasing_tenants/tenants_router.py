# app/routes/leasing_tenants/tenants_router.py
from typing import Dict, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from shared.core.database import get_auth_db, get_facility_db as get_db
from shared.core.auth import allow_admin, validate_current_token
from shared.helpers.json_response_helper import success_response
from shared.core.schemas import Lookup, UserToken

from ...schemas.leasing_tenants.tenants_schemas import (
    TenantListResponse,
    TenantOut,
    TenantCreate,
    TenantOverviewResponse,
    TenantUpdate,
    TenantRequest,
    TenantDropdownResponse
)
from ...crud.leasing_tenants import tenants_crud as crud

router = APIRouter(
    prefix="/api/tenants",
    tags=["tenants"],
    dependencies=[Depends(validate_current_token)],
)

# ------------all


@router.get("/all", response_model=TenantListResponse)
def tenants_all(
    params: TenantRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_all_tenants(db, current_user.org_id, params)

# Overview


@router.get("/overview", response_model=TenantOverviewResponse)
def tenants_overview(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_tenants_overview(db, current_user.org_id)

# ----------------- Create Tenant -----------------


@router.post("/", response_model=TenantOut)
def create_tenant_endpoint(
    tenant: TenantCreate,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token),
     _ : UserToken = Depends(allow_admin)

):
    # Assign org_id from current user if needed
    # tenant.org_id = current_user.org_id  # Uncomment if your Tenant model has org_id
    return crud.create_tenant(db,auth_db, tenant)


# ----------------- Update Tenant -----------------
@router.put("/", response_model=TenantOut)
def update_tenant(
    update_data: TenantUpdate,  # Get full payload (includes id)
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token),
    _ : UserToken = Depends(allow_admin)
):
    return crud.update_tenant(db,auth_db, update_data.id, update_data)


# ---------------- Delete Tenant ----------------
@router.delete("/{tenant_id}")
def delete_tenant_route(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
): return crud.delete_tenant(db,auth_db, tenant_id)

# ----------------  Type Lookup ----------------


@router.get("/type-lookup", response_model=List[Lookup])
def tenant_type_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.tenant_type_lookup(db, current_user.org_id)

# ----------------  Status Lookup ----------------


@router.get("/status-lookup", response_model=List[Lookup])
def tenant_status_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.tenant_status_lookup(db, current_user.org_id)



# Add to app/routes/leasing_tenants/tenants_router.py

@router.get("/by-site-space")
def get_tenants_by_site_and_space(
    site_id: UUID = Query(..., description="Site ID"),
    space_id: UUID = Query(..., description="Space ID"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get tenants filtered by both site_id and space_id
    """
    tenants = crud.get_tenants_by_site_and_space(db, site_id, space_id)
    
    # If you're using success_response wrapper
    return success_response(
        data=tenants,  # This should be a list
        message="Data retrieved successfully"
    )