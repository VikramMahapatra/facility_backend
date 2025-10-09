# app/crud/leasing_tenants/tenants_crud.py
from datetime import datetime
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, literal, or_
from sqlalchemy.dialects.postgresql import UUID

from facility_service.app.models.space_sites.spaces import Space

from ...schemas.leases_schemas import LeaseOut
from ...enum.leasing_tenants_enum import TenantStatus, TenantType
from shared.schemas import Lookup
from ...models.leasing_tenants.commercial_partners import CommercialPartner
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
    total_individual = (
        db.query(func.count(func.distinct(Tenant.id)))
        .filter(Tenant.site_id.in_(
            db.query(Lease.site_id).filter(Lease.org_id == org_id).distinct()
        ))
        .scalar() or 0
    )

    total_partners = (
        db.query(func.count(func.distinct(CommercialPartner.id))
                 .filter(CommercialPartner.org_id == org_id)).scalar() or 0
    )

    total_tenants = total_individual + total_partners

    # Active tenants
    active_tenants = total_individual + (
        db.query(func.count(func.distinct(CommercialPartner.id)))
        .filter(
            CommercialPartner.org_id == org_id,
            CommercialPartner.status == "active"
        )
        .scalar() or 0
    )

    # Individual leases
    individual = total_individual

    return {
        "totalTenants": total_tenants,
        "activeTenants": active_tenants,
        "commercialTenants": total_partners,
        "individualTenants": individual
    }


# ----------------- Get All Tenants -----------------
def get_all_tenants(db: Session, org_id, params: TenantRequest) -> TenantListResponse:
    # residential query
    tenant_query = (
        db.query(
            Tenant.id.label("id"),
            literal(str(org_id)).label("org_id"),
            Tenant.site_id.label("site_id"),
            Tenant.name.label("name"),
            Tenant.email.label("email"),
            Tenant.phone.label("phone"),
            literal("individual").label("tenant_type"),
            literal(None).label("legal_name"),
            literal(None).label("type"),
            literal("active").label("status"),
            Tenant.address.label("address"),
            literal(None).label("contact"),
        ).join(Site, Site.id == Tenant.site_id).filter(Site.org_id == org_id)
    )

    if params.status and params.status.lower() != "all":
        if params.status.lower() != "active":
            tenant_query = tenant_query.filter(False)  # always false

    if params.search:
        search_term = f"%{params.search}%"
        tenant_query = tenant_query.filter(
            or_(
                Tenant.name.ilike(search_term),
                Tenant.email.ilike(search_term),
                Tenant.phone.ilike(search_term),
                Tenant.flat_number.ilike(search_term),
            )
        )

    # commercial query
    partner_query = db.query(
        CommercialPartner.id.label("id"),
        CommercialPartner.org_id.label("org_id"),
        CommercialPartner.site_id.label("site_id"),
        CommercialPartner.legal_name.label("name"),
        (CommercialPartner.contact["email"].astext).label("email"),
        (CommercialPartner.contact["phone"].astext).label("phone"),
        literal("commercial").label("tenant_type"),
        CommercialPartner.legal_name.label("legal_name"),
        CommercialPartner.type.label("type"),
        CommercialPartner.status.label("status"),
        literal(None).label("address"),
        CommercialPartner.contact.label("contact"),
    ).filter(CommercialPartner.org_id == org_id)

    if params.status and params.status.lower() != "all":
        partner_query = partner_query.filter(func.lower(
            CommercialPartner.status) == params.status.lower())

    if params.search:
        partner_query = partner_query.filter(
            CommercialPartner.legal_name.ilike(f"%{params.search}%")
        )

    # choose query
    if params.type and params.type.lower() == "individual":
        final_query = tenant_query
    elif params.type and params.type.lower() == "commercial":
        final_query = partner_query
    else:
        final_query = tenant_query.union_all(partner_query)

    # total count
    subq = final_query.subquery()
    total = db.query(func.count()).select_from(subq).scalar()

    # paginate
    rows = (
        db.query(final_query.subquery())
        .order_by("name")
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    results = []
    for r in rows:
        record = dict(r._mapping)

        if record.get("tenant_type") == "individual":
            # Build contact_info from tenant fields
            record["contact_info"] = {
                "name": record["name"],
                "email": record["email"],
                "phone": record["phone"],
                "address": record.get("address"),
            }
        else:
            # Commercial already has contact JSON
            contact = record.get("contact") or {}
            # Ensure address structure exists
            if contact.get("address") is None:
                contact["address"] = {
                    "line1": "",
                    "line2": "",
                    "city": "",
                    "state": "",
                    "pincode": "",
                }
            record["contact_info"] = contact

        record["tenant_leases"] = get_tenant_leases(
            db, org_id, record.get("id"), record.get("tenant_type"))

        results.append(TenantOut.model_validate(record))

    return {"tenants": results, "total": total}


def get_tenant_leases(db: Session, org_id: UUID, tenant_id: str, tenant_type: str) -> List[LeaseOut]:
    query = db.query(Lease).filter(Lease.org_id == org_id)

    if tenant_type == "commercial":
        query = query.filter(Lease.partner_id == tenant_id)
    else:  # individual
        query = query.filter(Lease.tenant_id == tenant_id)

    rows = query.all()

    leases = []
    for row in rows:

        tenant_name = None
        if row.partner is not None:
            tenant_name = row.partner.legal_name
        elif row.tenant is not None:
            tenant_name = row.tenant.name
        else:
            tenant_name = "Unknown"  # fallback

        space_code = None
        site_name = None
        if row.space_id:
            space_code = db.query(Space.code).filter(
                Space.id == row.space_id).scalar()
        if row.site_id:
            site_name = db.query(Site.name).filter(
                Site.id == row.site_id).scalar()
        leases.append(
            LeaseOut.model_validate(
                {
                    **row.__dict__,
                    "space_code": space_code,
                    "site_name": site_name,
                    "tenant_name": tenant_name
                }
            )
        )
    return leases

# CRUD
# ------------------------------------------------------------


def get_tenant_by_id(db: Session, tenant_id: str) -> Optional[Tenant]:
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()


def create_tenant(db: Session, tenant: TenantCreate):
    now = datetime.utcnow()

    if tenant.tenant_type == "individual":
        # Only create Tenant
        tenant_data = {
            "site_id": tenant.site_id,
            "name": tenant.name,
            "email": tenant.email,
            "phone": tenant.phone,
            "address": tenant.contact_info.address if tenant.contact_info else None,
            "created_at": now,
            "updated_at": now,
        }
        db_tenant = Tenant(**tenant_data)
        db.add(db_tenant)
        db.commit()
        db.refresh(db_tenant)
        return db_tenant

    elif tenant.tenant_type == "commercial":
        # Only create CommercialPartner
        partner_data = {
            "org_id": tenant.org_id,
            "site_id": tenant.site_id,
            "type": tenant.type or "merchant",
            "legal_name": tenant.legal_name or tenant.name,
            "contact": tenant.contact_info.dict() if tenant.contact_info else None,
            "status": tenant.status or "active",
        }
        db_partner = CommercialPartner(**partner_data)
        db.add(db_partner)
        db.commit()
        db.refresh(db_partner)
        return db_partner


def update_tenant(db: Session, update_data: TenantUpdate):
    update_dict = update_data.dict(exclude_unset=True)
    update_dict["updated_at"] = datetime.utcnow()

    if update_data.tenant_type == "individual":
        db_tenant = db.query(Tenant).filter(
            Tenant.id == update_data.id).first()
        if not db_tenant:
            return None

        # Update Tenant table
        db.query(Tenant).filter(Tenant.id == update_data.id).update(
            {
                Tenant.name: update_dict.get("name", db_tenant.name),
                Tenant.email: update_dict.get("email", db_tenant.email),
                Tenant.phone: update_dict.get("phone", db_tenant.phone),
                Tenant.address: (
                    update_dict.get("contact_info", {}).get("address")
                    if update_dict.get("contact_info")
                    else db_tenant.address
                ),
                Tenant.updated_at: datetime.utcnow(),
            }
        )

        db.commit()
        db.refresh(db_tenant)
        return db_tenant

    # Handle commercial tenant updates
    elif update_data.tenant_type == "commercial":
        db_partner = (
            db.query(CommercialPartner)
            .filter(CommercialPartner.id == update_data.id)
            .first()
        )

        if not db_partner:
            return None

        if db_partner:
            # Update existing commercial partner
            db_partner.legal_name = update_dict.get(
                "legal_name", db_partner.legal_name)
            db_partner.type = update_dict.get("type", db_partner.type)
            db_partner.contact = update_dict.get(
                "contact_info") or db_partner.contact
            db_partner.status = update_dict.get("status", db_partner.status)
            db_partner.updated_at = datetime.utcnow()

        db.commit()
        return db_partner

    else:
        raise ValueError(f"Invalid tenant_type: {update_data.tenant_type}")

# ----------------- Delete Tenant -----------------


def delete_tenant(db: Session, tenant_id: UUID) -> bool:
    db_tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not db_tenant:
        return False
    db.delete(db_tenant)
    db.commit()
    return True

# -----------type lookup


def tenant_type_lookup(db: Session, org_id: str) -> List[Dict]:
    return [
        Lookup(id=type.value, name=type.name.capitalize())
        for type in TenantType
    ]


def tenant_type_filter_lookup(db: Session, org_id: str) -> List[Dict]:
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

# -----------status_lookup


def tenant_status_lookup(db: Session, org_id: str) -> List[Dict]:
    return [
        Lookup(id=status.value, name=status.name.capitalize())
        for status in TenantStatus
    ]


def tenant_status_filter_lookup(db: Session, org_id: str) -> List[Dict]:
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
