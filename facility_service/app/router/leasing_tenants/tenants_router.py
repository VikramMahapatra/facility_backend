from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional
from shared.schemas import UserToken
from ...schemas.tenants_schemas import TenantCreate, TenantView, TenantUpdate
from ...crud.leasing_tenants import tenants_crud as crud
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token

router = APIRouter(prefix="/tenants", tags=["Tenants"])

# ---------- Create Tenant ----------
@router.get("/{tenant_id}", response_model=TenantView)
def get_tenant_by_id(tenant_id: str, db: Session = Depends(get_db)):
    db_tenant = crud.get_tenant(db, tenant_id)
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return db_tenant