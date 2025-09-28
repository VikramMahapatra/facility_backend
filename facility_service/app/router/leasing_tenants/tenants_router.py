# app/routes/leasing_tenants/tenants_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
 
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token
from shared.schemas import UserToken
 
from ...schemas.tenants_schemas import (
    TenantListResponse,
    TenantOut,
    TenantCreate,
    TenantUpdate,
    TenantRequest,
    TenantOverview,
)
from ...crud.leasing_tenants import tenant_crud as crud
 
router = APIRouter(
    prefix="/api/tenants",
    tags=["tenants"],
    dependencies=[Depends(validate_current_token)],
)
 
# List
@router.get("/", response_model=TenantListResponse)
def get_tenants(
    params: TenantRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    return crud.get_tenants(db, current_user.org_id, params)
 
 
# Overview
@router.get("/overview", response_model=TenantOverview)
def get_tenants_overview(
    params: TenantRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    return crud.get_tenants_overview(db, current_user.org_id, params)
 
 
# Create
@router.post("/", response_model=TenantOut)
def create_tenant(
    payload: TenantCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    obj = crud.create_tenant(db, payload)
    return TenantOut.model_validate(obj)
 
 
# Update
@router.put("/", response_model=TenantOut)
def update_tenant(
    payload: TenantUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    obj = crud.update_tenant(db, payload)
    if not obj:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return TenantOut.model_validate(obj)
 
 
# Delete
@router.delete("/{tenant_id}", response_model=TenantOut)
def delete_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    obj = crud.delete_tenant(db, tenant_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return TenantOut.model_validate(obj)
 