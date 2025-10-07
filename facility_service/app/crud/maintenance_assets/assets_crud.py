import uuid
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, cast, or_, case, literal, Numeric, and_,  distinct
from dateutil.relativedelta import relativedelta
from sqlalchemy.dialects.postgresql import UUID

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
            case((func.lower(Asset.status) == "active", 1), else_=0)
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

        location = (
            (
                db.query(
                    func.concat(
                        Space.name,
                        literal(" - "),
                        Site.name
                    ).label("name")
                )
                .join(Site, Site.id == Space.site_id)
                .filter(and_(asset.space_id == Space.id, asset.site_id == Site.id))
                .scalar()
            )
        )
        assets.append(AssetOut.model_validate({
            **asset.__dict__,
            "category_name": category_name,
            "location": location
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


def asset_lookup(db: Session, org_id: UUID):
    assets = (
        db.query(
            Asset.id.label("id"),
            Asset.name.label("name"))
        .filter(Asset.org_id == org_id)
        .distinct()
        .order_by(func.lower(Asset.name))
        .all()
    )
    return assets


def asset_filter_status_lookup(db: Session, org_id: UUID):
    """
    Returns distinct statuses (case-insensitive) return name id
    """
    statuses = (
        db.query(
            func.lower(Asset.status).label("id"),
            func.concat(Asset.tag, literal(" - "), Asset.name).label("name")
        )
        .filter(Asset.org_id == org_id)
        .distinct()
        .order_by(func.lower(Asset.status))
        .all()
    )
    return statuses

# --------------------AssetStatus filter by Enum -----------


def asset_status_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=status.value, name=status.name.capitalize())
        for status in AssetStatus
    ]


# ---------------- Category Lookup ----------------
def assets_category_lookup(db: Session, org_id: UUID) -> List[Dict]:
    query = (
        db.query(
            AssetCategory.id.label("id"),
            AssetCategory.name.label("name")
        )
        .filter(AssetCategory.org_id == org_id)
        .distinct()
        .order_by(AssetCategory.name)
    )
    rows = query.all()
    return [Lookup(id=r.id, name=r.name) for r in rows]
