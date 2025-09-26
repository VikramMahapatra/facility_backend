from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from ...models.leasing_tenants.tenants import Tenant
from ...schemas.tenants_schemas import TenantCreate
from ...models.space_sites.sites import Site
# ---------- Get Tenant ----------
def get_tenant(db: Session, tenant_id: str):
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()

#----------- Delete Tenant -------------
def delete_tenant(db: Session, tenant_id: str):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    db.delete(tenant)
    db.commit()
    return {"message": "Tenant deleted successfully"}

