# app/crud/maintenance_assets/assets_crud.py
import uuid
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, cast, or_, case, literal, Numeric, and_, distinct
from dateutil.relativedelta import relativedelta
from sqlalchemy.dialects.postgresql import UUID
from dateutil.relativedelta import relativedelta
from facility_service.app.models.space_sites.sites import Site
from ...models.space_sites.buildings import Building
from ...models.space_sites.spaces import Space
from ...enum.maintenance_assets_enum import AssetStatus
from shared.schemas import Lookup
from ...models.maintenance_assets.asset_category import AssetCategory
from ...models.maintenance_assets.assets import Asset
from ...schemas.maintenance_assets.assets_schemas import AssetCreate, AssetOut, AssetUpdate, AssetsRequest, AssetsResponse

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
    query = db.query(Asset).join(AssetCategory, Asset.category_id == AssetCategory.id)
    
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
        if asset.space_id and asset.site_id:
            try:
                location_data = (
                    db.query(Space.name, Site.name)
                    .join(Site, Site.id == Space.site_id)
                    .filter(
                        Space.id == asset.space_id,
                        Site.id == asset.site_id
                    )
                    .first()
                )
                if location_data:
                    location = f"{location_data[0]} - {location_data[1]}"
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
    db_asset = Asset(**asset.model_dump())
    db.add(db_asset)
    db.commit()
    db.refresh(db_asset)
    return db_asset

def update_asset(db: Session, asset: AssetUpdate):
    db_asset = get_asset_by_id(db, asset.id)
    if not db_asset:
        return None
    for k, v in asset.dict(exclude_unset=True).items():
        setattr(db_asset, k, v)
    db.commit()
    db.refresh(db_asset)
    return db_asset

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
        .order_by(Asset.name)
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
        .order_by(Asset.status)
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
        .order_by(AssetCategory.name)
    )
    rows = query.all()
    return [Lookup(id=r.id, name=r.name) for r in rows]