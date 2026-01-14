# building_crud.py
from sqlite3 import IntegrityError
from typing import Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_
from datetime import datetime
from uuid import UUID
from fastapi import HTTPException

from shared.core.schemas import UserToken
from shared.helpers.property_helper import get_allowed_buildings, get_allowed_sites
from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response
from shared.utils.enums import UserAccountType
from ...schemas.space_sites.building_schemas import BuildingCreate, BuildingOut, BuildingRequest, BuildingUpdate
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...models.leasing_tenants.leases import Lease
from ...models.space_sites.buildings import Building


def get_buildings(db: Session, user:UserToken, params: BuildingRequest):
    allowed_building_ids = None

    if user.account_type.lower() == UserAccountType.TENANT:
        allowed_buildings = get_allowed_buildings(db, user)
        allowed_building_ids = [b["building_id"] for b in allowed_buildings]

        if not allowed_building_ids:
            return {"buildings": [], "total": 0}

    now = datetime.utcnow()

    # Subquery to calculate total_spaces and occupied per site
    space_subq = (
        db.query(
            Space.building_block_id.label("building_id"),  # Changed this
            func.count(Space.id).label("total_spaces"),
            func.count(
                case(
                    (Space.status == 'occupied', 1)
                )
            ).label("occupied_spaces")

        )
        .filter(Space.is_deleted == False)  # Add this filter
        .group_by(Space.building_block_id)  # Changed this
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
                          0).label("occupied_spaces"),
            # ADD OCCUPANCY RATE CALCULATION
            func.round(
                case(
                    (func.coalesce(space_subq.c.total_spaces, 0) > 0,
                     (func.coalesce(space_subq.c.occupied_spaces, 0) * 100.0) /
                     func.coalesce(space_subq.c.total_spaces, 1)),
                    else_=0.0
                ), 2
            ).label("occupancy_rate")
        )
        .join(Site, Building.site_id == Site.id)
        # Changed this
        .outerjoin(space_subq, Building.id == space_subq.c.building_id)
        .filter(
            Building.is_deleted == False,  # Add this filter
            Site.is_deleted == False      # Add this filter
        )
    )
    if allowed_building_ids is not None:
        building_query = building_query.filter(
                Building.id.in_(allowed_building_ids)
        )
    else:
        building_query = building_query.filter(
                Site.org_id == user.org_id
        )

    if params.site_id and params.site_id.lower() != "all":
        building_query = building_query.filter(
            Building.site_id == params.site_id)

    if params.search:
        search_term = f"%{params.search}%"
        building_query = building_query.filter(
            or_(Building.name.ilike(search_term), Site.name.ilike(search_term)))

    total = db.query(func.count()).select_from(
        building_query.subquery()).scalar()

    building_query = building_query.order_by(
        Building.updated_at.desc()).offset(params.skip).limit(params.limit)

    buildings = building_query.all()
    # Use _asdict() to convert Row objects to dictionaries
    results = [BuildingOut.model_validate(r._asdict()) for r in buildings]

    return {"buildings": results, "total": total}


def create_building(db: Session, building: BuildingCreate):
    # Check for duplicate building name within the same site (case-insensitive)
    existing_building = db.query(Building).filter(
        Building.site_id == building.site_id,
        Building.is_deleted == False,
        func.trim(func.lower(Building.name)) == func.trim(func.lower(building.name))
    ).first()

    if existing_building:
        return error_response(
            message=f"Building with name '{building.name}' already exists in this site",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )

    # Create building - exclude org_id if not needed in model
    building_data = building.model_dump(exclude={"org_id"})
    db_building = Building(**building_data)
    db.add(db_building)
    db.commit()
    db.refresh(db_building)
    return db_building  # Return the model directly like space CRUD


def update_building(db: Session, building: BuildingUpdate):
    db_building = db.query(Building).filter(
        Building.id == building.id,
        Building.is_deleted == False  # Add this filter
     ).first()
    
    if not db_building:
        return error_response(
            message="Building not found",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=404
        )

    update_data = building.model_dump(exclude_unset=True)

    # Check if trying to update site when spaces exist
    if 'site_id' in update_data and update_data['site_id'] != db_building.site_id:
        # Check if building has any active spaces
        has_spaces = db.query(Space).filter(
            Space.building_block_id == building.id,
            Space.is_deleted == False
            ).first()

        if has_spaces:
                return error_response(
                message="Cannot update site for a building that has spaces assigned to it"
            )
        existing_building = db.query(Building).filter(
            Building.site_id == building.site_id,
            Building.id != building.id,
            Building.is_deleted == False,
            func.trim(func.lower(Building.name)) == func.trim(func.lower(update_data.get('name', '')))
        ).first()
        if existing_building:
            return error_response(
                message=f"Building with name '{update_data['name']}' already exists in this site"
            )
        
    # Check for duplicates only if name is being updated
    if 'name' in update_data and update_data['name'] != db_building.name:
        existing_building = db.query(Building).filter(
            Building.site_id == db_building.site_id,
            Building.id != building.id,
            Building.is_deleted == False,
            func.trim(func.lower(Building.name)) == func.trim(func.lower(update_data.get('name', '')))
        ).first()

        if existing_building:
            return error_response(
                message=f"Building with name '{update_data['name']}' already exists in this site"
            )

    # Update building
    for key, value in update_data.items():
        setattr(db_building, key, value)

    try:
        db.commit()
        db.refresh(db_building)
        return get_building_by_id(db, building.id)
        
    except IntegrityError as e:
        db.rollback()
        return error_response(
            message="Error updating building",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def get_building_lookup(db: Session, site_id: str, user: UserToken):
    allowed_building_ids = None

    if user.account_type.lower() == UserAccountType.TENANT:
        allowed_buildings = get_allowed_buildings(db, user)
        allowed_building_ids = [b["building_id"] for b in allowed_buildings]

        if not allowed_building_ids:
            return {"buildings": [], "total": 0}
        
    building_query = (
        db.query(Building.id, Building.name)
        .join(Site, Site.id == Building.site_id)
        .filter(
            Building.is_deleted == False,  # Add this filter
            Site.is_deleted == False,     # Add this filter
            Site.status == "active",
            Building.status == "active"
        ).order_by(Building.name.asc())
    )

    if allowed_building_ids is not None:
        building_query = building_query.filter(
                Building.id.in_(allowed_building_ids)
        )
    else:
        building_query = building_query.filter(
                Site.org_id == user.org_id
        )

    if site_id and site_id.lower() != "all":
        building_query = building_query.filter(Site.id == site_id)

    return building_query.all()




# In building_crud.py - update the delete_building function
def delete_building(db: Session, building_id: str) -> Dict:
    """Delete building with protection - check for active spaces first"""
    building = db.query(Building).filter(
        Building.id == building_id,
        Building.is_deleted == False  # Add this filter
    ).first()
    
    if not building:
        return {"success": False, "message": "Building not found"}

    # Check if building has any active (non-deleted) spaces
    active_spaces_count = db.query(Space).filter(
        Space.building_block_id == building_id,
        Space.is_deleted == False
    ).count()

    if active_spaces_count > 0:
        return {
            "success": False,
            "message": f"It contains {active_spaces_count} active space(s). Please contact administrator to delete this building.",
            "active_spaces_count": active_spaces_count
        }

    # Soft delete the building
    building.is_deleted = True
    db.commit()

    return {"success": True, "message": "Building deleted successfully"}




def get_building_by_id(db: Session, building_id: str):
    now = datetime.utcnow()

    # Subquery to calculate total_spaces and occupied per site
    space_subq = (
        db.query(
            Space.building_block_id.label("building_id"),  # Changed this
            func.count(Space.id).label("total_spaces"),
            func.count(
                case(
                    (Space.status == 'occupied', 1)
                )
            ).label("occupied_spaces")

        )
        .filter(Space.is_deleted == False)  # Add this filter
        .group_by(Space.building_block_id)  # Changed this
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
                          0).label("occupied_spaces"),
            # ADD OCCUPANCY RATE CALCULATION
            func.round(
                case(
                    (func.coalesce(space_subq.c.total_spaces, 0) > 0,
                     (func.coalesce(space_subq.c.occupied_spaces, 0) * 100.0) /
                     func.coalesce(space_subq.c.total_spaces, 1)),
                    else_=0.0
                ), 2
            ).label("occupancy_rate")
        )
        .join(Site, Building.site_id == Site.id)
        # Changed this
        .outerjoin(space_subq, Building.id == space_subq.c.building_id)
        .filter(
            Building.id == building_id,
         
        )
    )

    building = building_query.first()
    # Use _asdict() to convert Row objects to dictionaries
    
    return BuildingOut.model_validate(building._asdict())