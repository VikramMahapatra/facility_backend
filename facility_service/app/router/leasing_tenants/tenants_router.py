# app/routes/leasing_tenants/tenants_router.py
from typing import Dict, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token
from shared.json_response_helper import success_response
from shared.schemas import Lookup, UserToken

from ...schemas.leasing_tenants.tenants_schemas import (
    TenantListResponse,
    TenantOut,
    TenantCreate,
    TenantOverviewResponse,
    TenantUpdate,
    TenantRequest,
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
@router.post("/", response_model=None)
def create_tenant_endpoint(
    tenant: TenantCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    # Assign org_id from current user if needed
    # tenant.org_id = current_user.org_id  # Uncomment if your Tenant model has org_id
    return crud.create_tenant(db, tenant)


# ----------------- Update Tenant -----------------
@router.put("/{tenant_id}", response_model=None) 
def update_tenant(
    tenant_id: UUID,  # Get from URL path
    update_data: TenantUpdate,  # Get from request body
    db: Session = Depends(get_db)
):
    
    return crud.update_tenant(db, tenant_id, update_data)

# ---------------- Delete Tenant ----------------
@router.delete("/{tenant_id}")
def delete_tenant_route(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    result = crud.delete_tenant(db, tenant_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return {"message": result["message"]}

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