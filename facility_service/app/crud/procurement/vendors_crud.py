# app/crud/vendors.py
import uuid
from typing import Dict, List, Optional
from sqlalchemy import func, lateral, or_ , select
from sqlalchemy.orm import Session

from ...models.maintenance_assets.asset_category import AssetCategory
from ...models.procurement.vendors import Vendor
from ...schemas.procurement.vendors_schemas import VendorCreate, VendorListResponse, VendorOut, VendorRequest, VendorUpdate
from ...enum.procurement_enum import VendorStatus , VendorCategories
from shared.schemas import Lookup

# ---------------- Overview ----------------
def get_vendors_overview(db: Session, org_id: uuid.UUID):
    # Total vendors
    total_vendors = db.query(func.count(Vendor.id)).filter(Vendor.org_id == org_id).scalar()

    # Active vendors
    active_vendors = db.query(func.count(Vendor.id)).filter(
        Vendor.org_id == org_id,
        func.lower(Vendor.status) == "active"
    ).scalar()

    # Average rating
    avg_rating = db.query(func.avg(Vendor.rating)).filter(Vendor.org_id == org_id).scalar()
    avg_rating = float(avg_rating) if avg_rating else 0.0


    categories_lateral = lateral(
        select(func.jsonb_array_elements_text(Vendor.categories).label("category"))
    ).alias("categories_lateral")

    distinct_categories = db.query(func.count(func.distinct(categories_lateral.c.category))).filter(
        Vendor.org_id == org_id
    ).scalar()
    
    return {
        "total_vendors": total_vendors,
        "active_vendors": active_vendors,
        "avg_rating": round(avg_rating, 2),
        "distinct_categories": distinct_categories
    }


#-----status_lookup
def vendors_filter_status_lookup(db: Session, org_id: str, status: Optional[str] = None):
    query = (
        db.query(
            Vendor.status.label("id"),
            Vendor.status.label("name")
        )
        .filter(Vendor.org_id == org_id)
        .distinct()
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

#---------categories_lookup
def vendors_filter_categories_lookup(db: Session, org_id: str):
    # Use jsonb_array_elements_text to expand JSON array into rows
    categories_subquery = (
        db.query(
            func.distinct(func.trim(func.jsonb_array_elements_text(Vendor.categories))).label("category")
        )
        .filter(Vendor.org_id == org_id)
        .subquery()
    )
    query = db.query(
        categories_subquery.c.category.label("id"),
        categories_subquery.c.category.label("name")
    )

    return query.all()

def Vendor_Categories_lookup(org_id: uuid.UUID, db: Session):
    return [
        Lookup(id=categories.value, name=categories.name.capitalize())
        for categories in VendorCategories
    ]



# ----------------- Build Filters for Vendors -----------------
def build_vendor_filters(org_id: uuid.UUID, params: VendorRequest):
    filters = [Vendor.org_id == org_id]

    if params.status and params.status.lower() != "all":
        filters.append(Vendor.status == params.status)

    if params.category and params.category.lower() != "all":
        # JSONB contains filter
        filters.append(func.jsonb_contains(Vendor.categories, f'"{params.category}"'))

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(
            or_(
                Vendor.name.ilike(search_term),
                func.cast(Vendor.id, func.Text).ilike(search_term),
                Vendor.gst_vat_id.ilike(search_term)
            )
        )

    return filters


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
        .order_by(Vendor.name.asc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )
    # Convert ORM objects to Pydantic models
    results = [VendorOut.from_orm(v) for v in vendors]

    return VendorListResponse(vendors=results, total=total)


def get_vendor_by_id(db: Session, vendor_id: str) -> Optional[Vendor]:
    return db.query(Vendor).filter(Vendor.id == vendor_id).first()



def create_vendor(db: Session, vendor: VendorCreate) -> Vendor:
    db_vendor = Vendor(**vendor.model_dump())  # Convert Pydantic model to dict
    db.add(db_vendor)
    db.commit()
    db.refresh(db_vendor)
    return db_vendor

def update_vendor(db: Session, vendor: VendorUpdate) -> Optional[Vendor]:
    db_vendor = get_vendor_by_id(db, vendor.id)
    if not db_vendor:
        return None
    # Update only provided fields
    for k, v in vendor.dict(exclude_unset=True).items():
        setattr(db_vendor, k, v)
    db.commit()
    db.refresh(db_vendor)
    return db_vendor

# ----------------- Delete -----------------
def delete_vendor(db: Session, vendor_id: uuid.UUID) -> bool:
    db_vendor = get_vendor_by_id(db, vendor_id)
    if not db_vendor:
        return False
    db.delete(db_vendor)
    db.commit()
    return True