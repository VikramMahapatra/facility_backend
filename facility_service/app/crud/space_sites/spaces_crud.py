from sqlite3 import IntegrityError
import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, or_, case, literal
from sqlalchemy.dialects.postgresql import UUID

from shared.app_status_code import AppStatusCode
from shared.json_response_helper import error_response
from ...models.space_sites.buildings import Building
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...models.leasing_tenants.leases import Lease
from ...schemas.space_sites.spaces_schemas import SpaceCreate, SpaceListResponse, SpaceOut, SpaceRequest, SpaceUpdate

# ----------------------------------------------------------------------
# CRUD OPERATIONS
# ----------------------------------------------------------------------


def build_space_filters(org_id: UUID, params: SpaceRequest):
    # Always filter out deleted spaces
    filters = [Space.org_id == org_id,
               Space.is_deleted == False]  # Updated filter

    if params.site_id and params.site_id.lower() != "all":
        filters.append(Space.site_id == params.site_id)

    if params.kind and params.kind.lower() != "all":
        filters.append(Space.kind == params.kind)

    if params.status and params.status.lower() != "all":
        filters.append(Space.status == params.status)

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(Space.name.ilike(search_term),
                       Space.code.ilike(search_term)))

    return filters


def get_space_query(db: Session, org_id: UUID, params: SpaceRequest):
    filters = build_space_filters(org_id, params)
    return db.query(Space).filter(*filters)


def get_spaces_overview(db: Session, org_id: UUID, params: SpaceRequest):
    filters = build_space_filters(org_id, params)

    counts = (
        db.query(
            func.count(Space.id).label("total_spaces"),
            func.count(case((Space.status == "available", 1))
                       ).label("available_spaces"),
            func.count(case((Space.status == "occupied", 1))
                       ).label("occupied_spaces"),
            func.count(case((Space.status == "out_of_service", 1))
                       ).label("out_of_service"),
        )
        .filter(*filters)
        .one()
    )

    return {
        "totalSpaces": counts.total_spaces,
        "availableSpaces": counts.available_spaces,
        "occupiedSpaces": counts.occupied_spaces,
        "outOfServices": counts.out_of_service
    }


def get_spaces(db: Session, org_id: UUID, params: SpaceRequest) -> SpaceListResponse:
    base_query = get_space_query(db, org_id, params)
    total = base_query.with_entities(func.count(Space.id)).scalar()

    spaces = (
        base_query
        .order_by(Space.updated_at.desc())
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
        results.append(SpaceOut.model_validate(
            {**space.__dict__, "building_block": building_block_name}))
    return {"spaces": results, "total": total}


def get_space_by_id(db: Session, space_id: str) -> Optional[Space]:
    # Updated filter
    return db.query(Space).filter(Space.id == space_id, Space.is_deleted == False).first()



def create_space(db: Session, space: SpaceCreate):
    # Check for duplicate space code within the same building (case-insensitive)
    if space.building_block_id:
        existing_space = db.query(Space).filter(
            Space.building_block_id == space.building_block_id,
            Space.is_deleted == False,
            func.lower(Space.code) == func.lower(space.code)  # Case-insensitive code within same building
        ).first()
        
        if existing_space:
            building_name = db.query(Building.name).filter(Building.id == space.building_block_id).scalar()
            return error_response(
                message=f"Space with code '{space.code}' already exists in building '{building_name}'",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )
    
    # Check for duplicate space name within the same building (if building and name are specified)
    if space.building_block_id and space.name:
        existing_space_by_name = db.query(Space).filter(
            Space.building_block_id == space.building_block_id,
            Space.is_deleted == False,
            func.lower(Space.name) == func.lower(space.name)  # Case-insensitive name within same building
        ).first()
        
        if existing_space_by_name:
            building_name = db.query(Building.name).filter(Building.id == space.building_block_id).scalar()
            return error_response(
                message=f"Space with name '{space.name}' already exists in building '{building_name}'",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )
    
    # Create space - exclude building_block field
    space_data = space.model_dump(exclude={"building_block"})
    db_space = Space(**space_data)
    db.add(db_space)
    db.commit()
    db.refresh(db_space)
    return db_space

def update_space(db: Session, space: SpaceUpdate):
    db_space = get_space_by_id(db, space.id)
    if not db_space:
        return error_response(
            message="Space not found",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=404
        )
    
    update_data = space.model_dump(exclude_unset=True, exclude={"building_block"})
    
    # Check for code duplicates within same building (if building exists and code is being updated)
    if 'code' in update_data and db_space.building_block_id:
        existing_space = db.query(Space).filter(
            Space.building_block_id == db_space.building_block_id,  # Same building
            Space.id != space.id,  # Different space
            Space.is_deleted == False,
            func.lower(Space.code) == func.lower(update_data.get('code', ''))  # Case-insensitive
        ).first()
        
        if existing_space:
            building_name = db.query(Building.name).filter(Building.id == db_space.building_block_id).scalar()
            return error_response(
                message=f"Space with code '{update_data['code']}' already exists in building '{building_name}'",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )
    
    # Check for name duplicates within same building (if building exists and name is being updated)
    if 'name' in update_data and db_space.building_block_id:
        existing_space_by_name = db.query(Space).filter(
            Space.building_block_id == db_space.building_block_id,  # Same building
            Space.id != space.id,  # Different space
            Space.is_deleted == False,
            func.lower(Space.name) == func.lower(update_data.get('name', ''))  # Case-insensitive
        ).first()
        
        if existing_space_by_name:
            building_name = db.query(Building.name).filter(Building.id == db_space.building_block_id).scalar()
            return error_response(
                message=f"Space with name '{update_data['name']}' already exists in building '{building_name}'",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )
    
    # Update space
    for key, value in update_data.items():
        setattr(db_space, key, value)
    
    try:
        db.commit()
        db.refresh(db_space)
        return db_space
    except IntegrityError as e:
        db.rollback()
        return error_response(
            message="Error updating space",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def delete_space(db: Session, space_id: str) -> Optional[Space]:
    db_space = get_space_by_id(db, space_id)
    if not db_space:
        return None

    # Soft delete - set is_deleted to True instead of actually deleting
    db_space.is_deleted = True  # Updated column name
    db_space.updated_at = func.now()
    db.commit()
    db.refresh(db_space)
    return db_space


def get_space_lookup(db: Session, site_id: str, building_id: str, org_id: str):
    space_query = (
        db.query(
            Space.id,
            Space.name
        )
        .join(Site, Space.site_id == Site.id)
        .join(Building, Space.building_block_id == Building.id)
        .filter(Space.is_deleted == False)
    )

    if org_id:
        space_query = space_query.filter(Space.org_id == org_id)

    if site_id and site_id.lower() != "all":
        space_query = space_query.filter(Space.site_id == site_id)

    if building_id and building_id.lower() != "all":
        space_query = space_query.filter(
            Space.building_block_id == building_id)

    return space_query.all()


def get_space_with_building_lookup(db: Session, site_id: str, org_id: str):
    space_query = (
        db.query(
            Space.id,
            func.concat(Building.name, literal(
                " - "), Space.name).label("name")
        )
        .join(Building, Space.building_block_id == Building.id)
        # Updated filter
        .filter(Space.org_id == org_id, Space.is_deleted == False)
    )

    if site_id and site_id.lower() != "all":
        space_query = space_query.filter(Space.site_id == site_id)

    return space_query.all()
