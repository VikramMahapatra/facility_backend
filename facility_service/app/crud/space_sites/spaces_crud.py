import uuid
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, or_, case, literal
from sqlalchemy.dialects.postgresql import UUID
from ...models.space_sites.buildings import Building
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...models.leasing_tenants.leases import Lease
from ...schemas.space_sites.spaces_schemas import SpaceCreate, SpaceListResponse, SpaceOut, SpaceRequest, SpaceUpdate


# ----------------------------------------------------------------------
# CRUD OPERATIONS
# ----------------------------------------------------------------------

def build_space_filters(org_id : UUID, params: SpaceRequest):
    filters = [Space.org_id == org_id]
     
    if params.site_id and params.site_id.lower() != "all":
        filters.append(Space.site_id == params.site_id)

    if params.kind and params.kind.lower() != "all":
        filters.append(Space.kind == params.kind)

    if params.status and params.status.lower() != "all":
        filters.append(Space.status == params.status)

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(Space.name.ilike(search_term), Space.code.ilike(search_term)))

    return filters

def get_space_query(db: Session, org_id: UUID, params: SpaceRequest):
    filters = build_space_filters(org_id, params)
    return db.query(Space).filter(*filters)

def get_spaces_overview(db: Session, org_id: UUID, params: SpaceRequest):
    filters = build_space_filters(org_id, params)
        
    counts =(
        db.query(
            func.count(Space.id).label("total_spaces"),
            func.count(case((Space.status == "available", 1))).label("available_spaces"),
            func.count(case((Space.status == "occupied", 1))).label("occupied_spaces"),
            func.count(case((Space.status == "out_of_service", 1))).label("out_of_service"),
        )
        .filter(*filters)
        .one()
    )
    
    return {
        "totalSpaces" : counts.total_spaces,
        "availableSpaces" : counts.available_spaces,
        "occupiedSpaces": counts.occupied_spaces,
        "outOfServices" : counts.out_of_service        
    }

def get_spaces(db: Session, org_id: UUID, params: SpaceRequest) -> SpaceListResponse:
    base_query = get_space_query(db, org_id, params)
    total = base_query.with_entities(func.count(Space.id)).scalar()
    
    spaces = (
        base_query
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )   

    results = []
    for space in spaces:
        building_block_name = (
            db.query(Building.name)
            .filter(Building.id == space.building_block_id)
            .scalar()
        )
        results.append(SpaceOut.model_validate({**space.__dict__, "building_block": building_block_name}))
    return {"spaces": results, "total": total}

def get_space_by_id(db: Session, space_id: str) -> Optional[Space]:
    return db.query(Space).filter(Space.id == space_id).first()

def create_space(db: Session, space: SpaceCreate) -> Space:
    db_space = Space(**space.model_dump(exclude="building_block"))
    db.add(db_space)
    db.commit()
    db.refresh(db_space)
    return db_space


def update_space(db: Session, space: SpaceUpdate) -> Optional[Space]:
    db_space = get_space_by_id(db, space.id)
    if not db_space:
        return None
    for k, v in space.dict(exclude_unset=True).items():
        setattr(db_space, k, v)
    db.commit()
    db.refresh(db_space)
    return db_space


def delete_space(db: Session, space_id: str) -> Optional[Space]:
    db_space = get_space_by_id(db, space_id)
    if not db_space:
        return None
    db.delete(db_space)
    db.commit()
    return db_space

def get_space_lookup(db: Session, site_id:str, org_id: str):
    space_query = (
        db.query(
            Space.id,
            func.concat(Space.name, literal(" - "), Site.name).label("name")
        )
        .join(Site, Space.site_id == Site.id)
        .filter(Space.org_id == org_id)
    )
    
    if site_id and site_id.lower() != "all":  # only add filter if site_id is provided
        space_query = space_query.filter(Space.site_id == site_id)
        
    return space_query.all()

