# app/crud/vendors.py
import uuid
from typing import Dict, List, Optional
from sqlalchemy import case, func, lateral, literal, or_, select, String
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import UUID
from ...models.maintenance_assets.asset_category import AssetCategory
from ...models.procurement.vendors import Vendor
from ...schemas.procurement.vendors_schemas import VendorCreate, VendorListResponse, VendorOut, VendorRequest, VendorUpdate
from ...enum.procurement_enum import VendorStatus, VendorCategories
from shared.core.schemas import Lookup

# ----------------- Build Filters for Vendors -----------------


def build_vendor_filters(org_id: uuid.UUID, params: VendorRequest):
    # Always filter out deleted vendors
    filters = [Vendor.org_id == org_id,
               Vendor.is_deleted == False]  # ✅ Updated filter

    if params.status and params.status.lower() != "all":
        filters.append(Vendor.status == params.status)

    if params.category and params.category.lower() != "all":
        # JSONB contains filter
        filters.append(func.jsonb_contains(
            Vendor.categories, f'"{params.category}"'))

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(
            or_(
                Vendor.name.ilike(search_term),
                func.cast(Vendor.id, String).ilike(search_term),
                Vendor.gst_vat_id.ilike(search_term)
            )
        )

    return filters

# ---------------- Overview ----------------


def get_vendors_overview(db: Session, org_id: uuid.UUID, params: VendorRequest):
    filters = build_vendor_filters(org_id, params)

    # Total vendors
    total_vendors = db.query(func.count(Vendor.id)).filter(*filters).scalar()

    # Active vendors
    active_vendors = db.query(func.count(Vendor.id)).filter(
        *filters,
        func.lower(Vendor.status) == "active"
    ).scalar()

    # Average rating
    avg_rating = db.query(func.avg(Vendor.rating)).filter(*filters).scalar()
    avg_rating = round(float(avg_rating or 0), 2)

    # Categories
    categories_lateral = lateral(
        select(func.jsonb_array_elements_text(
            Vendor.categories).label("category"))
    ).alias("categories_lateral")

    categories = db.query(
        func.count(func.distinct(categories_lateral.c.category))
    ).filter(*filters).scalar() or 0

    return {
        "totalVendors": total_vendors,
        "activeVendors": active_vendors,
        "avgRating": avg_rating,
        "Categories": categories
    }

# -----status_lookup-----


def vendors_filter_status_lookup(db: Session, org_id: str, status: Optional[str] = None):
    query = (
        db.query(
            Vendor.status.label("id"),
            Vendor.status.label("name")
        )
        # ✅ Updated filter
        .filter(Vendor.org_id == org_id, Vendor.is_deleted == False)
        .distinct()
        .order_by(Vendor.status.asc())
    )
    if status:
        query = query.filter(Vendor.status == status)

    return query.all()

# ----------------- Filter by status Enum-----------------


def vendors_status_lookup(db: Session, org_id: str):
    return [
        Lookup(id=status.value, name=status.name.capitalize())
        for status in VendorStatus
    ]

# ---------categories_lookup---------


def vendors_filter_categories_lookup(db: Session, org_id: str):
    # Use jsonb_array_elements_text to expand JSON array into rows
    categories_subquery = (
        db.query(
            func.distinct(func.trim(func.jsonb_array_elements_text(
                Vendor.categories))).label("category")
        )
        # ✅ Updated filter
        .filter(Vendor.org_id == org_id, Vendor.is_deleted == False)
        .subquery()
    )
    query = db.query(
        categories_subquery.c.category.label("id"),
        categories_subquery.c.category.label("name")
    ).order_by(categories_subquery.c.category.asc())

    return query.all()


def Vendor_Categories_lookup(org_id: uuid.UUID, db: Session):
    return [
        Lookup(id=categories.value, name=categories.name.capitalize())
        for categories in VendorCategories
    ]

# ----------------- Vendor Query -----------------


def get_vendor_query(db: Session, org_id: uuid.UUID, params: VendorRequest):
    filters = build_vendor_filters(org_id, params)
    return db.query(Vendor).filter(*filters)

# ----------------- Get All Vendors -----------------


def get_vendors(db: Session, org_id: uuid.UUID, params: VendorRequest) -> VendorListResponse:
    base_query = get_vendor_query(db, org_id, params)

    # Total count for pagination
    total = base_query.with_entities(func.count(Vendor.id)).scalar()

    # Fetch vendors with offset & limit
    vendors = (
        base_query
        .order_by(Vendor.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )
    # Convert ORM objects to Pydantic models
    results = [VendorOut.from_orm(v) for v in vendors]

    return VendorListResponse(vendors=results, total=total)


def get_vendor_by_id(db: Session, vendor_id: str) -> Optional[Vendor]:
    # ✅ Updated filter to exclude deleted vendors
    return db.query(Vendor).filter(Vendor.id == vendor_id, Vendor.is_deleted == False).first()


def create_vendor(db: Session, vendor: VendorCreate) -> Vendor:
    db_vendor = Vendor(**vendor.model_dump())
    db.add(db_vendor)
    db.commit()
    db.refresh(db_vendor)
    return db_vendor


def update_vendor(db: Session, vendor: VendorUpdate) -> Optional[Vendor]:
    # ✅ Use the updated get_vendor_by_id
    db_vendor = get_vendor_by_id(db, vendor.id)
    if not db_vendor:
        return None
    # Update only provided fields
    for k, v in vendor.dict(exclude_unset=True).items():
        setattr(db_vendor, k, v)
    db.commit()
    db.refresh(db_vendor)
    return db_vendor

# ----------------- Delete (Soft Delete) -----------------


def delete_vendor(db: Session, vendor_id: uuid.UUID, org_id: uuid.UUID) -> Optional[Vendor]:
    db_vendor = (
        db.query(Vendor)
        .filter(Vendor.id == vendor_id, Vendor.org_id == org_id, Vendor.is_deleted == False)
        .first()
    )
    if not db_vendor:
        return None

    # ✅ Soft delete - set is_deleted to True instead of actually deleting
    db_vendor.is_deleted = True
    db_vendor.updated_at = func.now()
    db.commit()
    db.refresh(db_vendor)
    return db_vendor


def vendor_lookup(db: Session, org_id: UUID):
    contact_name = Vendor.contact["contact_name"].astext

    vendors = (
        db.query(
            Vendor.id.label("id"),
            func.concat(
                Vendor.name,
                # conditionally append " (contact_name)" only when it exists
                case(
                    (
                        (contact_name.isnot(None)) & (contact_name != ""),
                        func.concat(literal(" ("), contact_name, literal(")")),
                    ),
                    else_=literal(""),
                ),
            ).label("name"),
        )
        # ✅ Updated filter
        .filter(Vendor.org_id == org_id, Vendor.is_deleted == False)
        .distinct()
        .all()
    )
    return vendors
