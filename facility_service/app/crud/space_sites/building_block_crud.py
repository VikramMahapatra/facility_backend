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

def get_aggregate_overview(db: Session, org_id: UUID, site_id: Optional[str] = None):
    now = datetime.utcnow()

    site = None
    if site_id:
        site = db.query(Site).filter(Site.id == site_id, Site.org_id == org_id).first()
        if not site:
            site_id = None

    # Base filters
    space_filters = [Space.org_id == org_id]
    lease_filters = [Space.org_id == org_id, Lease.start_date <= now, Lease.end_date >= now]

    if site_id:
        space_filters.append(Space.site_id == site_id)
        lease_filters.append(Space.site_id == site_id)

    # Total spaces
    total_spaces = db.query(func.count(Space.id)).filter(*space_filters).scalar() or 0

    # Total buildings (from Building table)
    building_filters = [Building.site.has(org_id=org_id)]
    if site_id:
        building_filters.append(Building.site_id == site_id)

    total_buildings = db.query(func.count(Building.id)).filter(*building_filters).scalar() or 0

    # Distinct floors
    '''distinct_floors = db.query(func.distinct(Space.floor)).filter(*space_filters).all()
    distinct_floors = [f[0] for f in distinct_floors if f[0] is not None]
'''
    distinct_floors_count = (
    db.query(func.count(func.distinct(Space.floor)))
    .filter(*space_filters)
    .scalar() or 0
    )


    # Occupied spaces
    occupied_spaces_count = (
        db.query(func.count(func.distinct(Space.id)))
        .join(Lease, Space.id == Lease.space_id)
        .filter(*lease_filters)
        .scalar() or 0
    )

    '''available_spaces = max(total_spaces - occupied_spaces_count, 0)
    occupied_percentage = round((occupied_spaces_count / total_spaces * 100) if total_spaces else 0.0, 2)
'''
    return {
        "total_buildings": total_buildings,
        "total_spaces": total_spaces,
        "total_floors": distinct_floors_count,
        "occupied_spaces": occupied_spaces_count,
    }

def get_buildings(db: Session, org_id: UUID, params: BuildingRequest):
    now = datetime.utcnow()
    
    #Subquery to calculate total_spaces and occupied per site
    space_subq = (
        db.query(
            Space.site_id.label("site_id"),
            func.count(Space.id).label("total_spaces"),
            func.sum(
                case(
                    ((Lease.start_date <= now) & (Lease.end_date >= now), 1),
                    else_=0
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
            func.coalesce(space_subq.c.occupied_spaces, 0).label("occupied_spaces")
        )
        .join(Site, Building.site_id == Site.id)
        .outerjoin(space_subq, Site.id == space_subq.c.site_id)
        .filter(Site.org_id == org_id)
    )
    
    if params.site_id and params.site_id.lower() != "all":
        building_query = building_query.filter(Building.site_id == params.site_id)
        
    if params.search:
        search_term = f"%{params.search}%"
        building_query = building_query.filter(or_(Building.name.ilike(search_term),Site.name.ilike(search_term)))
    
    total = building_query.count()
    
    building_query = building_query.order_by(Building.created_at.desc()).offset(params.skip).limit(params.limit)
        
    buildings = building_query.all()
    return {"buildings": buildings, "total": total}


def create_building(db: Session, building: BuildingCreate):
    db_building = Building(**building.model_dump(exclude={"org_id"}))
    db.add(db_building)
    db.commit()
    db.refresh(db_building)
    return get_building(db, db_building.id)


def update_site(db: Session, building: BuildingUpdate):
    db_building =  db.query(Building).filter(Building.id == building.id).first()
    if not db_building:
        return None
    for key, value in building.dict(exclude_unset=True).items():
        setattr(db_building, key, value)
    db.commit()
    db.refresh(db_building)
    return get_building(db, db_building.id)

def get_building(db: Session, id:str):
    now = datetime.utcnow()
    
    #Subquery to calculate total_spaces and occupied per site
    space_subq = (
        db.query(
            Space.site_id.label("site_id"),
            func.count(Space.id).label("total_spaces"),
            func.sum(
                case(
                    ((Lease.start_date <= now) & (Lease.end_date >= now), 1),
                    else_=0
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
            func.coalesce(space_subq.c.occupied_spaces, 0).label("occupied_spaces")
        )
        .join(Site, Building.site_id == Site.id)
        .outerjoin(space_subq, Site.id == space_subq.c.site_id)
        .filter(Building.id == id)
    )
    return building_query.first()
    