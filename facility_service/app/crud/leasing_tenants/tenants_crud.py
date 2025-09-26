from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from ...models.leasing_tenants.tenants import Tenant
from ...schemas.tenants_schemas import TenantCreate
from ...models.space_sites.sites import Site
# ---------- Get Tenant ----------
def get_tenant(db: Session, tenant_id: str):
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()

#----------- Create Tenant -------------


#----------- Delete Tenant -------------
def delete_tenant(db: Session, tenant_id: str):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    db.delete(tenant)
    db.commit()
    return {"message": "Tenant deleted successfully"}

#---------- Update Tenant --------------

#---------- Dashboard Details-----------
def get_tenant_stats(db: Session):
    total = db.query(func.count(Tenant.id)).scalar()

    active = db.query(func.count(Lease.id)).filter(Lease.status == "active").scalar()
    inactive = db.query(func.count(Lease.id)).filter(Lease.status == "inactive").scalar()
    suspended = db.query(func.count(Lease.id)).filter(Lease.status == "suspended").scalar()

    individual = db.query(func.count(Lease.id)).filter(Lease.kind == "individual").scalar()
    commercial = db.query(func.count(Lease.id)).filter(Lease.kind == "commercial").scalar()

    return {
        "total": total,
        "active": active,
        "inactive": inactive,
        "suspended": suspended,
        "individual": individual,
        "commercial": commercial
    }
    
def get_tenants_by_filter(db: Session, status: str = None, kind: str = None):
    query = db.query(Tenant).join(Lease)

    if status:
        query = query.filter(Lease.status == status)
    if kind:
        query = query.filter(Lease.kind == kind)

    return query.all()