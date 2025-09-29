import uuid
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, or_, case, literal, Numeric, and_
from dateutil.relativedelta import relativedelta
from sqlalchemy.dialects.postgresql import UUID
from ...models.maintenance_assets.asset_category import AssetCategory
from ...models.maintenance_assets.assets import Asset
from ...schemas.maintenance_assets.assets_schemas import AssetCreate, AssetOut, AssetUpdate, AssetsRequest, AssetsResponse


# ----------------------------------------------------------------------
# CRUD OPERATIONS
# ----------------------------------------------------------------------

def build_asset_filters(org_id: UUID, params: AssetsRequest):
    filters = [Asset.org_id == org_id]

    if params.status and params.status.lower() != "all":
        filters.append(Asset.status.lower() == params.status.lower())

    if params.category and params.category.lower() != "all":
        filters.append(Asset.category.lower() == params.category.lower())

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(Asset.code.ilike(search_term),
                       Asset.tag.ilike(search_term)))

    return filters


def get_assets_query(db: Session, org_id: UUID, params: AssetsRequest):
    filters = build_asset_filters(org_id, params)
    return db.query(Asset).filter(*filters)


def get_asset_overview(db: Session, org_id: UUID):
    today = datetime.utcnow()

    first_day_this_month = datetime(today.year, today.month, 1)
    last_day_last_month = first_day_this_month - timedelta(days=1)

    asset_fields = db.query(
        func.count(Asset.id).label("total_assets"),
        func.sum(
            case((Asset.status == "active", 1), else_=0)
        ).label("active_assets"),
        func.coalesce(func.sum(Asset.cost), 0).label("total_cost"),
        func.sum(
            case(
                (and_(Asset.warranty_expiry.isnot(None),
                 Asset.warranty_expiry < today), 1),
                else_=0
            )
        ).label("assets_need_maintenance")
    ).filter(Asset.org_id == org_id).one()

    last_month_assets = db.query(func.count()).filter(
        Asset.org_id == org_id,
        Asset.created_at >= last_day_last_month,
        Asset.created_at <= today
    ).scalar()

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

    results = (
        base_query
        .order_by(Asset.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    assets = []
    for asset in results:
        category_name = (
            db.query(AssetCategory.name)
            .filter(AssetCategory.id == asset.category_id)
            .scalar()
        )
        assets.append(AssetOut.model_validate({
            **asset,
            "category_name": category_name
        }))

    return {"assets": assets, "total": total}


def get_asset_by_id(db: Session, asset_id: str):
    return db.query(Asset).filter(Asset.id == asset_id).first()


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


def delete_asset(db: Session, asset_id: str):
    db_asset = get_asset_by_id(db, asset_id)
    if not db_asset:
        return None
    db.delete(db_asset)
    db.commit()
    return True
