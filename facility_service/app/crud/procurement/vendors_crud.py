# app/crud/vendors.py
from datetime import date, datetime
from sqlite3 import IntegrityError
import uuid
from typing import Dict, List, Optional
from sqlalchemy import case, func, lateral, literal, or_, select, String
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import UUID
from auth_service.app.models.roles import Roles
from auth_service.app.models.userroles import UserRoles
from shared.helpers.password_generator import generate_secure_password
from shared.models.users import Users


from ...models.procurement.contracts import Contract
from shared.helpers.json_response_helper import error_response
from shared.utils.app_status_code import AppStatusCode
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


# ---------------- Create ----------------
def create_vendor(db: Session,auth_db: Session, vendor: VendorCreate, org_id: UUID) -> VendorOut:
    # Check for duplicate name
    existing_vendor = db.query(Vendor).filter(
        Vendor.name.ilike(vendor.name.strip()),
        Vendor.org_id == org_id,
        Vendor.is_deleted == False
    ).first()
    
    if existing_vendor:
        return error_response(
            message=f"Vendor '{vendor.name}' already exists in this organization"
        )
    
    # Check for duplicate GST number if provided
    if vendor.gst_vat_id:
        existing_gst = db.query(Vendor).filter(
            Vendor.gst_vat_id.ilike(vendor.gst_vat_id.strip()),
            Vendor.org_id == org_id,
            Vendor.is_deleted == False
        ).first()
        if existing_gst:
            return error_response(
                message=f"GST number '{vendor.gst_vat_id}' already exists in this organization"
            )

    # Check for duplicate phone if provided
    phone = vendor.contact.get("phone") if vendor.contact else None
    if phone:
        existing_phone = db.query(Vendor).filter(
            Vendor.contact["phone"].astext == phone,
            Vendor.org_id == org_id,
            Vendor.is_deleted == False
        ).first()
        if existing_phone:
            return error_response(
                message=f"Phone number '{phone}' already exists in this organization"
            )
    now = datetime.utcnow()

        # GENERATE RANDOM PASSWORD
    random_password = generate_secure_password()
    
    # CREATE USER RECORD
    new_user_id = str(uuid.uuid4())
    
    contact_info = vendor.contact or {}
    contact_name = contact_info.get("name") 
    contact_email = contact_info.get("email")
    contact_phone = contact_info.get("phone")
    
    new_user = Users(
        id=new_user_id,
        org_id=org_id,
        full_name=vendor.name,
        email=contact_email,
        phone=contact_phone,
        account_type="vendor",
        status="inactive",
        is_deleted=False,
        created_at=now,
        updated_at=now,
        username=contact_email or f"user_{new_user_id[:8]}",  #  Add username
        password=""  #  Initialize with empty string
    )
    #  SET PASSWORD (hashes it)
    new_user.set_password(random_password)
    
    auth_db.add(new_user)
    auth_db.flush()
    
    # Add user_id to contact info
    updated_contact = contact_info.copy()
    if new_user_id:
        updated_contact["user_id"] = str(new_user_id)

    # Add org_id to vendor data
    vendor_data = vendor.model_dump()
    vendor_data['org_id'] = org_id
    vendor_data['user_id'] = new_user_id  # Add user_id to vendor
    vendor_data['contact'] = updated_contact

    db_vendor = Vendor(**vendor_data)
    db.add(db_vendor)
    auth_db.commit()
    db.commit()
    db.refresh(db_vendor)
    return db_vendor


def update_vendor(db: Session,auth_db: Session, vendor: VendorUpdate) -> Optional[Vendor]:
    db_vendor = get_vendor_by_id(db, vendor.id)
    if not db_vendor:
        return error_response(
            message="Vendor not found",
            status_code="OPERATION_ERROR",
            http_status=404
        )

    update_data = vendor.model_dump(exclude_unset=True, exclude={'rating'})

    # ---------------- Duplicate Name Check ----------------
    new_name = update_data.get("name")
    if new_name and new_name.strip() != db_vendor.name:
        existing_vendor = db.query(Vendor).filter(
            Vendor.name.ilike(new_name.strip()),
            Vendor.org_id == db_vendor.org_id,
            Vendor.id != vendor.id,
            Vendor.is_deleted == False
        ).first()
        if existing_vendor:
            return error_response(
                message=f"Vendor name '{new_name}' already exists",
                status_code="OPERATION_ERROR",
                http_status=400
            )

    # ---------------- Duplicate GST Number Check ----------------
    new_gst = update_data.get("gst_vat_id")
    if new_gst and new_gst.strip() != (db_vendor.gst_vat_id or "").strip():
        existing_gst = db.query(Vendor).filter(
            Vendor.gst_vat_id.ilike(new_gst.strip()),
            Vendor.org_id == db_vendor.org_id,
            Vendor.id != vendor.id,
            Vendor.is_deleted == False
        ).first()
        if existing_gst:
            return error_response(
                message=f"GST number '{new_gst}' already exists",
                status_code="OPERATION_ERROR",
                http_status=400
            )
    

    # ---------------- Duplicate Phone Checks ----------------
    new_phone = update_data.get("contact", {}).get("phone") if update_data.get("contact") else None
    current_phone = db_vendor.contact.get("phone") if db_vendor.contact else None
    if new_phone and new_phone != current_phone:
        existing_phone = db.query(Vendor).filter(
            Vendor.contact["phone"].astext == new_phone,
            Vendor.org_id == db_vendor.org_id,
            Vendor.id != vendor.id,
            Vendor.is_deleted == False
        ).first()
        if existing_phone:
            return error_response(
                message=f"Phone number '{new_phone}' already exists",
                status_code="OPERATION_ERROR",
                http_status=400
            )
    # UPDATE USER RECORD
    if db_vendor.user_id:
        user = auth_db.query(Users).filter(
            Users.id == db_vendor.user_id,
            Users.is_deleted == False
        ).first()
        
        if user:
            new_contact = update_data.get("contact", {}) if update_data.get("contact") else {}
            current_contact = db_vendor.contact or {}
            
            vendor_name = update_data.get("name") or db_vendor.name  # Use vendor name
            contact_email = new_contact.get("email") or current_contact.get("email")
            contact_phone = new_contact.get("phone") or current_contact.get("phone")
            
            user.full_name = vendor_name  # Use vendor name
            if contact_email:
                user.email = contact_email
            if contact_phone:
                user.phone = contact_phone
            user.updated_at = datetime.utcnow()
    # ---------------- Update Fields ----------------
    for key, value in update_data.items():
        setattr(db_vendor, key, value)

    try:
        auth_db.commit()  # Commit user updates
        db.commit()
        return get_vendor_by_id(db, vendor.id)

    except IntegrityError:
        auth_db.rollback() 
        db.rollback()
        return error_response(
            message="Error updating vendor",
            status_code="OPERATION_ERROR",
            http_status=400
        )


# ----------------- Delete (Soft Delete) -----------------


def delete_vendor(db: Session, auth_db: Session,vendor_id: uuid.UUID, org_id: uuid.UUID) -> Optional[Vendor]:
    db_vendor = (
        db.query(Vendor)
        .filter(Vendor.id == vendor_id, Vendor.org_id == org_id, Vendor.is_deleted == False)
        .first()
    )
    if not db_vendor:
        return None
    
    if db_vendor.user_id:
        user = auth_db.query(Users).filter(
            Users.id == db_vendor.user_id,
            Users.is_deleted == False
        ).first()
        if user:
            user.is_deleted = True
            user.updated_at = datetime.utcnow()

    # ✅ Remove the variable assignment
    db.query(Contract).filter(
        Contract.vendor_id == vendor_id,
        Contract.org_id == org_id,
        Contract.is_deleted == False
    ).update({
        "is_deleted": True,
        "updated_at": func.now()
    })

    db_vendor.is_deleted = True
    db_vendor.updated_at = func.now()
    
    auth_db.commit()
    db.commit()
    db.refresh(db_vendor)
    return db_vendor


def vendor_lookup(db: Session, org_id: UUID):
    contact_name = Vendor.contact["contact_name"].astext
    subquery = (
        db.query(Vendor.id)
        .filter(Vendor.org_id == org_id, 
                Vendor.is_deleted == False,
                Vendor.status == "active" )
        .distinct()
        .subquery()
    )
    vendors = (
        db.query(
            Vendor.id.label("id"),
            func.concat(
                Vendor.name,
                case(
                    (
                        (contact_name.isnot(None)) & (contact_name != ""),
                        func.concat(" (", contact_name, ")"),
                    ),
                    else_="",
                ),
            ).label("name"),
        )
        .join(subquery, Vendor.id == subquery.c.id)
        .order_by(Vendor.name.asc())
        .all()
    )
    return vendors



def vendor_workorder_lookup(db: Session, org_id: UUID): #lookup for work order creation
    contact_name = Vendor.contact["contact_name"].astext
    
    # ✅ SUBQUERY: Get vendors who have ACTIVE contracts
    vendors_with_active_contracts = (
        db.query(Contract.vendor_id)
        .filter(
            Contract.org_id == org_id,
            Contract.is_deleted == False,
            Contract.status == "active",
            or_(
                Contract.end_date == None,
                Contract.end_date >= date.today()
            )
        )
        .distinct()
        .subquery()
    )
    
    # ✅ MAIN QUERY: Active vendors + have active contracts
    vendors = (
        db.query(
            Vendor.id.label("id"),
            func.concat(
                Vendor.name,
                case(
                    (
                        (contact_name.isnot(None)) & (contact_name != ""),
                        func.concat(" (", contact_name, ")"),
                    ),
                    else_="",
                ),
            ).label("name"),
        )
        .filter(
            Vendor.org_id == org_id,
            Vendor.is_deleted == False,
            Vendor.status == "active",  # ✅ Vendor active
            Vendor.id.in_(select(vendors_with_active_contracts.c.vendor_id))  # ✅ Has active contracts
        )
        .order_by(Vendor.name.asc())
        .all()
    )
    return vendors