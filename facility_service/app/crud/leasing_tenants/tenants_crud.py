# app/crud/leasing_tenants/tenants_crud.py
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from sqlalchemy.dialects.postgresql import UUID
 
from ...models.leasing_tenants.tenants import Tenant
from ...models.leasing_tenants.leases import Lease
from ...schemas.tenants_schemas import (
    TenantCreate,
    TenantUpdate,
    TenantOut,
    TenantListResponse,
    TenantRequest,
)
 
# ------------------------------------------------------------
# Filters
# ------------------------------------------------------------
def build_tenant_filters(org_id: UUID, params: TenantRequest):
    filters = [Tenant.org_id == org_id]
 
    # site filter
    if params.site_id and params.site_id.lower() != "all":
        filters.append(Tenant.site_id == params.site_id)
 
    if params.search:
        like = f"%{params.search}%"
        filters.append(
            or_(
                Tenant.name.ilike(like),
                Tenant.email.ilike(like),
                Tenant.phone.ilike(like),
            )
        )
 
    return filters
 
 
# ------------------------------------------------------------
# Overview: total, active tenants , commercial & individual
# ------------------------------------------------------------
def get_tenants_overview(db: Session, org_id: UUID, params: TenantRequest):
    filters = build_tenant_filters(org_id, params)
 
    total = db.query(Tenant).filter(*filters).count()
 
    # distinct tenant_ids with active leases (org scoped)
    active = (
        db.query(func.count(func.distinct(Lease.tenant_id)))
        .filter(
            Lease.org_id == org_id,
            Lease.status == "active",
            Lease.tenant_id.isnot(None),
        )
        .scalar()
        or 0
    )
 
    # distinct partner_ids with active leases (org scoped)
    commercial = (
        db.query(func.count(func.distinct(Lease.partner_id)))
        .filter(
            Lease.org_id == org_id,
            Lease.status == "active",
            Lease.partner_id.isnot(None),
        )
        .scalar()
        or 0
    )
 
    # same as active
    individual = active
 
    return {
        "totalTenants": int(total),
        "activeTenants": int(active),
        "commercialTenants": int(commercial),
        "individualTenants": int(individual),
    }
 
 
# ------------------------------------------------------------
# List + pagination (attach active_leases count like your style)
# ------------------------------------------------------------
def get_tenants(db: Session, org_id: UUID, params: TenantRequest) -> TenantListResponse:
    base_query = db.query(Tenant).filter(*build_tenant_filters(org_id, params))
 
    total = base_query.count()
    rows: List[Tenant] = (
        base_query.offset(params.skip).limit(params.limit).all()
    )
 
    items: List[TenantOut] = []
    for t in rows:
        active_leases = (
            db.query(func.count(Lease.id))
            .filter(
                Lease.tenant_id == t.id,
                Lease.status == "active",
            )
            .scalar()
            or 0
        )
        items.append(
            TenantOut.model_validate({**t.__dict__, "active_leases": int(active_leases)})
        )
 
    return {"tenants": items, "total": total}
 
 
# ------------------------------------------------------------
# CRUD
# ------------------------------------------------------------
def get_tenant_by_id(db: Session, tenant_id: str) -> Optional[Tenant]:
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()
 
 
def create_tenant(db: Session, payload: TenantCreate) -> Tenant:
    obj = Tenant(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
 
 
def update_tenant(db: Session, payload: TenantUpdate) -> Optional[Tenant]:
    obj = get_tenant_by_id(db, payload.id)
    if not obj:
        return None
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj
 
 
def delete_tenant(db: Session, tenant_id: str) -> Optional[Tenant]:
    obj = get_tenant_by_id(db, tenant_id)
    if not obj:
        return None
    db.delete(obj)
    db.commit()
    return obj