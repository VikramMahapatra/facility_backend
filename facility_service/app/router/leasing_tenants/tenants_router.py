from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional
from shared.schemas import UserToken
from ...schemas.tenants_schemas import TenantCreate, TenantView, TenantUpdate, TenantStatsResponse, TenantFilterResponse
from ...crud.leasing_tenants import tenants_crud as crud
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token

router = APIRouter(prefix="/tenants", tags=["Tenants"])

# ---------- Get Tenant ----------
@router.get("/{tenant_id}", response_model=TenantView)
def get_tenant_by_id(tenant_id: str, db: Session = Depends(get_db)):
    db_tenant = crud.get_tenant(db, tenant_id)
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return db_tenant


#----------- Delete Tenant -------------
@router.delete("/{tenant_id}", summary="Delete a tenant by ID")
def delete_tenant(tenant_id: str, db: Session = Depends(get_db)):
    return crud.delete_tenant(db=db, tenant_id=tenant_id)

#---------- Dashboard Details-----------
@router.get("/stats", response_model=TenantStatsResponse)
def tenant_statistics(db: Session = Depends(get_db)):
    return get_tenant_stats(db)
