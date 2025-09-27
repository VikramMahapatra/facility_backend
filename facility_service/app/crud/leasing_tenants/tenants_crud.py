from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from uuid import UUID
from ...models.leasing_tenants.tenants import Tenant
from ...models.leasing_tenants.leases import Lease
from ...schemas.tenants_schemas import TenantCreate, TenantDelete, TenantUpdate, TenantView
from ...models.space_sites.sites import Site
# ---------- Create Tenant ----------
def create_tenant(db: Session, tenant: TenantCreate):
    try:
        db_tenant = Tenant(**tenant.dict())
        db.add(db_tenant)
        db.commit()
        db.refresh(db_tenant)
        return db_tenant
    except Exception as e:
        db.rollback()
        print("❌ DB ERROR:", e)
        raise

def delete_tenant(db: Session, tenant_id: str):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    db.delete(tenant)
    db.commit()
    return {"message": "Tenant deleted successfully"}

def update_tenant(db: Session, tenant_id: str, tenant_data: dict):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    for key, value in tenant_data.items():
        setattr(tenant, key, value)
    
    db.commit()
    db.refresh(tenant)
    return tenant

def get_tenant(db: Session, tenant_id: str):
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()

def get_tenants_by_status_and_type(
    db: Session,
    org_id: UUID,
    status: Optional[str] = None,
    tenant_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    tenant_type_case = case(
        (Lease.partner_id.isnot(None), "commercial"),
        else_="individual"
    ).label("tenant_type")

    q = db.query(
        Lease.id,
        Lease.tenant_name,
        Lease.status,
        tenant_type_case,
        Lease.start_date,
        Lease.end_date,
        Lease.rent_amount
    ).filter(Lease.org_id == org_id)

