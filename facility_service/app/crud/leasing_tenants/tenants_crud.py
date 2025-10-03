# app/crud/leasing_tenants/tenants_crud.py
from datetime import datetime
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from sqlalchemy.dialects.postgresql import UUID

from ...models.space_sites.sites import Site
from sqlalchemy.orm import joinedload
from ...models.leasing_tenants.tenants import Tenant
from ...models.leasing_tenants.leases import Lease
from ...schemas.leasing_tenants.tenants_schemas import (
    TenantCreate,
    TenantUpdate,
    TenantOut,
    TenantListResponse,
    TenantRequest,
)

# ------------------------------------------------------------

def get_tenants_overview(db: Session, org_id) -> dict:
    # Total tenants
    total_tenants = (
        db.query(func.count(func.distinct(Tenant.id)))
        .filter(Tenant.site_id.in_(
            db.query(Lease.site_id).filter(Lease.org_id == org_id).distinct()
        ))
        .scalar() or 0
    )

    # Active tenants
    active_tenants = (
        db.query(func.count(func.distinct(Lease.tenant_id)))
        .filter(
            Lease.org_id == org_id,
            Lease.status == "active",
            Lease.tenant_id.isnot(None)
        )
        .scalar() or 0
    )

    # Commercial leases
    commercial = (
        db.query(func.count(Lease.id))
        .filter(
            Lease.org_id == org_id,
            Lease.kind == "commercial"
        )
        .scalar() or 0
    )

    # Individual leases
    individual = (
        db.query(func.count(Lease.id))
        .filter(
            Lease.org_id == org_id,
            Lease.kind == "individual"
        )
        .scalar() or 0
    )

    return {
        "total_tenants": total_tenants,
        "active_tenants": active_tenants,
        "commercial": commercial,
        "individual": individual
    }


# ----------------- Build Filters -----------------
def build_tenant_filters(db: Session, org_id, params: TenantRequest):
    # Subquery to get all site IDs for the org
    site_ids_subq = db.query(Site.id).filter(Site.org_id == org_id).subquery()

    filters = [Tenant.site_id.in_(site_ids_subq)]

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(
            or_(
                Tenant.name.ilike(search_term),
                Tenant.email.ilike(search_term),
                Tenant.phone.ilike(search_term),
                Tenant.flat_number.ilike(search_term)
            )
        )

    return filters


# ----------------- Base Query -----------------
def get_tenant_query(db: Session, org_id, params: TenantRequest):
    filters = build_tenant_filters(db, org_id, params)

    query = db.query(Tenant).filter(*filters)

    # Join with Lease if filtering by status/kind
    if (params.status and params.status.lower() != "all") or (params.kind and params.kind.lower() != "all"):
        query = query.join(Lease, Lease.tenant_id == Tenant.id)

        if params.status and params.status.lower() != "all":
            query = query.filter(Lease.status == params.status)

        if params.kind and params.kind.lower() != "all":
            query = query.filter(Lease.kind == params.kind)

    return query


# ----------------- Get All Tenants -----------------
def get_all_tenants(db: Session, org_id, params: TenantRequest) -> TenantListResponse:
    base_query = get_tenant_query(db, org_id, params)
    
    total = base_query.with_entities(func.count(Tenant.id)).scalar()
    
    tenants = (
        base_query
        .order_by(Tenant.name.asc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    results = [TenantOut.model_validate(t.__dict__) for t in tenants]

    return {"tenants": results, "total": total}

# CRUD
# ------------------------------------------------------------
def get_tenant_by_id(db: Session, tenant_id: str) -> Optional[Tenant]:
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()


def create_tenant(db: Session, tenant: TenantCreate):
    tenant_data = tenant.dict(exclude={"tenancy_info"})
    db_tenant = Tenant(user_id=None, **tenant_data)
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)
    return db_tenant

def update_tenant(
    db: Session,
    tenant_id: UUID,
    update_data: TenantUpdate
) -> Optional[Tenant]:
    db_tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not db_tenant:
        return None

    update_dict = update_data.dict(exclude_unset=True)
    update_dict["updated_at"] = datetime.utcnow()

    for key, value in update_dict.items():
        setattr(db_tenant, key, value)

    db.commit()
    db.refresh(db_tenant)
    return db_tenant

# ----------------- Delete Tenant -----------------
def delete_tenant(db: Session, tenant_id: UUID) -> bool:
    db_tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not db_tenant:
        return False
    db.delete(db_tenant)
    db.commit()
    return True

#-----------type lookup
def tenant_type_lookup(db: Session, org_id: str) -> List[Dict]:
    query = (
        db.query(
            Lease.kind.label("id"),
            Lease.kind.label("name")
        )
        .filter(Lease.org_id == org_id)
        .distinct()
        .order_by(Lease.kind)
    )
    rows = query.all()
    return [{"id": r.id, "name": r.name} for r in rows]

#-----------status_lookup 
def tenant_status_lookup(db: Session, org_id: str) -> List[Dict]:
    query = (
        db.query(
            Lease.status.label("id"),
            Lease.status.label("name")
        )
        .filter(Lease.org_id == org_id)
        .distinct()
        .order_by(Lease.status)
    )
    rows = query.all()
    return [{"id": r.id, "name": r.name} for r in rows]