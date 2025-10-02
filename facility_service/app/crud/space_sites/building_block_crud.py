from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_
from datetime import datetime
from uuid import UUID
from ...schemas.space_sites.building_schemas import BuildingCreate, BuildingRequest, BuildingUpdate
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...models.leasing_tenants.leases import Lease
from ...models.space_sites.buildings import Building


def get_buildings(db: Session, org_id: UUID, params: BuildingRequest):
    now = datetime.utcnow()

    # Subquery to calculate total_spaces and occupied per site
    space_subq = (
        db.query(
            Space.site_id.label("site_id"),
            func.count(Space.id).label("total_spaces"),
            func.count(
                case(
                    (Space.status == 'occupied', 1)
                )
            ).label("occupied_spaces")
        )
        .outerjoin(Lease, Space.id == Lease.space_id)
        .group_by(Space.site_id)
    ).subquery()

    building_query = (
        db.query(
            Building.id,
            Building.site_id,
            Building.name,
            Building.floors,
            Building.attributes,
            Site.name.label("site_name"),
            Site.kind.label("site_kind"),
            func.coalesce(space_subq.c.total_spaces, 0).label("total_spaces"),
            func.coalesce(space_subq.c.occupied_spaces,
                          0).label("occupied_spaces")
        )
        .join(Site, Building.site_id == Site.id)
        .outerjoin(space_subq, Site.id == space_subq.c.site_id)
        .filter(Site.org_id == org_id)
    )

    if params.site_id and params.site_id.lower() != "all":
        building_query = building_query.filter(
            Building.site_id == params.site_id)

    if params.search:
        search_term = f"%{params.search}%"
        building_query = building_query.filter(
            or_(Building.name.ilike(search_term), Site.name.ilike(search_term)))

    total = building_query.count()

    building_query = building_query.order_by(
        Building.created_at.desc()).offset(params.skip).limit(params.limit)

    buildings = building_query.all()
    return {"buildings": buildings, "total": total}


def create_building(db: Session, building: BuildingCreate):
    db_building = Building(**building.model_dump(exclude={"org_id"}))
    db.add(db_building)
    db.commit()
    db.refresh(db_building)
    return get_building(db, db_building.id)


def update_site(db: Session, building: BuildingUpdate):
    db_building = db.query(Building).filter(Building.id == building.id).first()
    if not db_building:
        return None
    for key, value in building.dict(exclude_unset=True).items():
        setattr(db_building, key, value)
    db.commit()
    db.refresh(db_building)
    return get_building(db, db_building.id)


def get_building(db: Session, id: str):
    now = datetime.utcnow()

    # Subquery to calculate total_spaces and occupied per site
    space_subq = (
        db.query(
            Space.site_id.label("site_id"),
            func.count(Space.id).label("total_spaces"),
            func.count(
                case(
                    (Space.status == 'occupied', 1)
                )
            ).label("occupied_spaces")
        )
        .outerjoin(Lease, Space.id == Lease.space_id)
        .group_by(Space.site_id)
    ).subquery()

    building_query = (
        db.query(
            Building.id,
            Building.site_id,
            Building.name,
            Building.floors,
            Building.attributes,
            Site.name.label("site_name"),
            Site.kind.label("site_kind"),
            func.coalesce(space_subq.c.total_spaces, 0).label("total_spaces"),
            func.coalesce(space_subq.c.occupied_spaces,
                          0).label("occupied_spaces")
        )
        .join(Site, Building.site_id == Site.id)
        .outerjoin(space_subq, Site.id == space_subq.c.site_id)
        .filter(Building.id == id)
    )
    return building_query.first()


def get_building_lookup(db: Session, site_id: str, org_id: str):
    building_query = (
        db.query(Building.id, Building.name)
        .join(Site, Site.id == Building.site_id)
        .filter(Site.org_id == org_id)
    )
    if site_id and site_id.lower() != "all":  # only add filter if site_id is provided
        building_query = building_query.filter(Site.id == site_id)

    return building_query.all()
