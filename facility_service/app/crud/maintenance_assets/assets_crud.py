# app/crud/maintenance_assets/assets_crud.py
import uuid
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, cast, or_, case, literal, Numeric, and_, distinct
from dateutil.relativedelta import relativedelta
from sqlalchemy.dialects.postgresql import UUID
from dateutil.relativedelta import relativedelta
from ...models.space_sites.sites import Site
from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response
from ...models.space_sites.buildings import Building
from ...models.space_sites.spaces import Space
from ...enum.maintenance_assets_enum import AssetStatus
from shared.core.schemas import Lookup
from ...models.maintenance_assets.asset_category import AssetCategory
from ...models.maintenance_assets.assets import Asset
from ...schemas.maintenance_assets.assets_schemas import AssetCreate, AssetOut, AssetUpdate, AssetsRequest, AssetsResponse
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError


# ----------------------------------------------------------------------
# CRUD OPERATIONS
# ----------------------------------------------------------------------

def build_asset_filters(org_id: UUID, params: AssetsRequest):
    filters = [Asset.org_id == org_id, Asset.is_deleted == False]

    if params.status and params.status.lower() != "all":
        # ✅ CASE-INSENSITIVE: Use ilike for status too
        filters.append(Asset.status.ilike(params.status))

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(
            Asset.tag.ilike(search_term),
            Asset.name.ilike(search_term)
        ))

    return filters


def get_assets_query(db: Session, org_id: UUID, params: AssetsRequest):
    filters = build_asset_filters(org_id, params)

    # ✅ FIXED: Always join with AssetCategory to get category name
    query = db.query(Asset).join(
        AssetCategory, Asset.category_id == AssetCategory.id)

    # ✅ FIXED: Add category filter if provided
    if params.category and params.category.lower() != "all":
        # Filter by category name (from AssetCategory table)
        query = query.filter(AssetCategory.name == params.category)

    return query.filter(*filters)


def get_asset_overview(db: Session, org_id: UUID, params: AssetsRequest):
    today = datetime.utcnow()

    # ✅ Cleaner date calculation
    first_day_this_month = datetime(today.year, today.month, 1)
    first_day_last_month = first_day_this_month - relativedelta(months=1)
    last_day_last_month = first_day_this_month - timedelta(seconds=1)

    # ✅ FIXED: Define base_query FIRST, then use it
    filters = build_asset_filters(org_id, params)

    # Base query with all filters applied
    base_query = db.query(Asset).filter(*filters)

    # ✅ FIXED: Apply filters to all overview metrics
    asset_fields = base_query.with_entities(
        func.count(Asset.id).label("total_assets"),
        func.sum(
            case((func.lower(Asset.status) == "active", 1), else_=0)
        ).label("active_assets"),
        func.coalesce(func.sum(Asset.cost), 0).label("total_cost"),
        func.sum(
            case(
                (and_(
                    Asset.warranty_expiry.isnot(None),
                    Asset.warranty_expiry < today
                ), 1),
                else_=0
            )
        ).label("assets_need_maintenance")
    ).one()

    # ✅ FIXED: Apply filters to last month's assets count (using correct date range)
    last_month_assets = base_query.filter(
        Asset.created_at >= first_day_last_month,  # Fixed: use first_day_last_month
        Asset.created_at <= last_day_last_month    # Fixed: use last_day_last_month
    ).count()

    if asset_fields.total_assets > 0:
        last_month_assets_percent = (
            last_month_assets * 100) / asset_fields.total_assets
    else:
        last_month_assets_percent = 0

    return {
        "totalAssets": int(asset_fields.total_assets or 0),
        "activeAssets": int(asset_fields.active_assets or 0),
        "totalValue": float(asset_fields.total_cost or 0),
        "assetsNeedingMaintenance": int(asset_fields.assets_need_maintenance or 0),
        "lastMonthAssetPercentage": float(last_month_assets_percent)
    }


def get_assets(db: Session, org_id: UUID, params: AssetsRequest) -> AssetsResponse:
    base_query = get_assets_query(db, org_id, params)
    total = base_query.with_entities(func.count(Asset.id)).scalar()

    # ✅ FIXED: Use joinedload to eagerly load the category relationship
    results = (
        base_query
        .options(joinedload(Asset.category))
        .order_by(Asset.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    assets = []
    for asset in results:
        # ✅ FIXED: Now we can access asset.category.name directly due to joinedload
        category_name = asset.category.name if asset.category else None

        # ✅ FIXED: Simplified location query
        location = None
        if asset.site_id:
            try:
                site = db.query(Site).filter(Site.id == asset.site_id).first()
                if site:
                    location = f"{site.name}"
                else:
                    location = "Site not found"
            except Exception as e:
                print(f"Error fetching location for asset {asset.id}: {e}")
                location = "Location not available"

        assets.append(AssetOut.model_validate({
            **asset.__dict__,
            "category_name": category_name,
            "location": location
        }))

    return {"assets": assets, "total": total}


def get_asset_by_id(db: Session, asset_id: str):
    # ✅ FIXED: Use joinedload to include category data
    return (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(Asset.id == asset_id, Asset.is_deleted == False)
        .first()
    )


def create_asset(db: Session, asset: AssetCreate):
    # Check for duplicate name (case-insensitive) within the same org and site
    existing_asset = db.query(Asset).filter(
        Asset.org_id == asset.org_id,
        Asset.site_id == asset.site_id,
        Asset.is_deleted == False,
        func.lower(Asset.name) == func.lower(asset.name)  # Case-insensitive
    ).first()

    if existing_asset:
        return error_response(
            message=f"Asset with name '{asset.name}' already exists in this site",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )

    # Check for duplicate serial_no (case-insensitive) if provided
    if asset.serial_no:
        existing_serial = db.query(Asset).filter(
            Asset.org_id == asset.org_id,
            Asset.site_id == asset.site_id,
            Asset.is_deleted == False,
            func.lower(Asset.serial_no) == func.lower(
                asset.serial_no)  # Case-insensitive
        ).first()

        if existing_serial:
            return error_response(
                message=f"Asset with serial number '{asset.serial_no}' already exists",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )

    # Check for duplicate tag (case-insensitive)
    existing_tag = db.query(Asset).filter(
        Asset.org_id == asset.org_id,
        Asset.site_id == asset.site_id,
        Asset.is_deleted == False,
        func.lower(Asset.tag) == func.lower(asset.tag)  # Case-insensitive
    ).first()

    if existing_tag:
        return error_response(
            message=f"Asset with tag '{asset.tag}' already exists in this site",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )

    # Create the asset
    db_asset = Asset(**asset.model_dump())
    db.add(db_asset)
    db.commit()
    db.refresh(db_asset)
    return db_asset


def update_asset(db: Session, asset_update: AssetUpdate):
    # Ensure asset_id is provided in body
    if not asset_update.id:
        return error_response(
            message="Asset ID is required in request body",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )

    db_asset = get_asset_by_id(db, asset_update.id)
    if not db_asset:
        return error_response(
            message="Asset not found",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=404
        )

    update_data = asset_update.model_dump(exclude_unset=True)

    # Only validate if tag, name, or serial_no are being updated
    if any(field in update_data for field in ['tag', 'name', 'serial_no']):
        duplicate_filters = [
            Asset.org_id == db_asset.org_id,
            Asset.site_id == db_asset.site_id,
            Asset.id != db_asset.id,
            Asset.is_deleted == False
        ]

        duplicate_conditions = []
        if 'tag' in update_data:
            duplicate_conditions.append(Asset.tag == update_data['tag'])
        if 'name' in update_data:
            duplicate_conditions.append(func.lower(
                Asset.name) == func.lower(update_data['name']))
        if 'serial_no' in update_data and update_data['serial_no']:
            duplicate_conditions.append(
                Asset.serial_no == update_data['serial_no'])

        if duplicate_conditions:
            duplicate_filters.append(or_(*duplicate_conditions))
            existing_asset = db.query(Asset).filter(*duplicate_filters).first()

            if existing_asset:
                if 'tag' in update_data and existing_asset.tag == update_data['tag']:
                    return error_response(
                        message=f"Asset with tag '{update_data['tag']}' already exists in this site",
                        status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                        http_status=400
                    )
                if 'name' in update_data and func.lower(existing_asset.name) == func.lower(update_data['name']):
                    return error_response(
                        message=f"Asset with name '{update_data['name']}' already exists in this site",
                        status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                        http_status=400
                    )
                if 'serial_no' in update_data and update_data['serial_no'] and existing_asset.serial_no == update_data['serial_no']:
                    return error_response(
                        message=f"Asset with serial number '{update_data['serial_no']}' already exists",
                        status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                        http_status=400
                    )

    # Perform update
    for field, value in update_data.items():
        setattr(db_asset, field, value)

    try:
        db.commit()
        db.refresh(db_asset)
        location = None
        if db_asset.site_id:
            site = db.query(Site).filter(Site.id == db_asset.site_id).first()
            if site:
                location = f"{site.name}"
        
        # Return enhanced response with location
        return {
            **db_asset.__dict__,
            "location": location
        }
    except IntegrityError as e:
        db.rollback()
        if "uix_org_site_tag" in str(e):
            return error_response(
                message=f"Asset with tag '{update_data.get('tag', db_asset.tag)}' already exists in this site",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )
        return error_response(
            message="Duplicate asset found during update",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def delete_asset(db: Session, asset_id: str, org_id: str) -> bool:
    """
    Soft delete an asset
    Returns: True if deleted, False if not found
    """
    db_asset = db.query(Asset).filter(
        Asset.id == asset_id,
        Asset.org_id == org_id,
        Asset.is_deleted == False
    ).first()

    if not db_asset:
        return False

    # Perform soft delete
    db_asset.is_deleted = True
    db_asset.deleted_at = func.now()
    db.commit()

    return True


def asset_lookup(db: Session, org_id: UUID):
    assets = (
        db.query(
            Asset.id.label("id"),
            Asset.name.label("name"))
        .filter(Asset.org_id == org_id, Asset.is_deleted == False)
        .distinct()
        .order_by(Asset.name.asc())
        .all()
    )
    return assets


def asset_filter_status_lookup(db: Session, org_id: UUID):
    statuses = (
        db.query(
            Asset.status.label("id"),
            func.concat(Asset.tag, literal(" - "), Asset.name).label("name")
        )
        .filter(Asset.org_id == org_id, Asset.is_deleted == False)
        .distinct()
        .order_by(Asset.status.asc())
        .all()
    )
    return statuses


def asset_status_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=status.value, name=status.name.capitalize())
        for status in AssetStatus
    ]


def assets_category_lookup(db: Session, org_id: UUID) -> List[Dict]:
    query = (
        db.query(
            AssetCategory.id.label("id"),
            AssetCategory.name.label("name")
        )
        .filter(AssetCategory.org_id == org_id, AssetCategory.is_deleted == False)
        .distinct()
        .order_by(AssetCategory.name.asc())
    )
    rows = query.all()
    return [Lookup(id=r.id, name=r.name) for r in rows]
