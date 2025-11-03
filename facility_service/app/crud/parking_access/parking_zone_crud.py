import uuid
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, or_, case, literal, Numeric, and_
from dateutil.relativedelta import relativedelta
from sqlalchemy.dialects.postgresql import UUID

from shared.app_status_code import AppStatusCode
from shared.json_response_helper import error_response

from ...models.space_sites.sites import Site
from ...models.parking_access.parking_zones import ParkingZone
from ...schemas.parking_access.parking_zone_schemas import ParkingZoneCreate, ParkingZoneOut, ParkingZoneRequest, ParkingZoneUpdate, ParkingZonesResponse
from sqlalchemy import and_
from fastapi import HTTPException, status

# ----------------------------------------------------------------------
# CRUD OPERATIONS
# ----------------------------------------------------------------------

def build_parking_zone_filters(org_id: UUID, params: ParkingZoneRequest):
    # Add soft delete filter - only show non-deleted zones
    filters = [ParkingZone.org_id == org_id, ParkingZone.is_deleted == False]

    if params.site_id and params.site_id != "all":
        filters.append(ParkingZone.site_id == params.site_id)

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(ParkingZone.name.ilike(search_term))

    return filters


def get_parking_zone_query(db: Session, org_id: UUID, params: ParkingZoneRequest):
    filters = build_parking_zone_filters(org_id, params)
    return db.query(ParkingZone).filter(*filters)


def get_parking_zone_overview(db: Session, org_id: UUID):
    # Add soft delete filter for overview
    zone_fields = db.query(
        func.count(ParkingZone.id).label("total_zones"),
        func.coalesce(func.sum(ParkingZone.capacity),
                      0).label("total_capacity"),
    ).filter(ParkingZone.org_id == org_id, ParkingZone.is_deleted == False).one()

    if zone_fields.total_zones > 0:
        avg_capacity = zone_fields.total_capacity / zone_fields.total_zones
    else:
        avg_capacity = 0

    return {
        "totalZones": int(zone_fields.total_zones or 0),
        "totalCapacity": int(zone_fields.total_capacity or 0),
        "avgCapacity": round(avg_capacity , 2),
    }


def get_parking_zones(db: Session, org_id: UUID, params: ParkingZoneRequest) -> ParkingZonesResponse:
    base_query = get_parking_zone_query(db, org_id, params)
    total = base_query.with_entities(func.count(ParkingZone.id)).scalar()

    results = (
        base_query
        .order_by(ParkingZone.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    zones = []
    for zone in results:
        site_name = (
            db.query(Site.name)
            .filter(Site.id == zone.site_id)
            .scalar()
        )
        zones.append(ParkingZoneOut.model_validate({
            **zone.__dict__,
            "site_name": site_name
        }))

    return {"zones": zones, "total": total}


def get_zone_by_id(db: Session, zone_id: str):
    # Add soft delete filter - only return non-deleted zones
    return db.query(ParkingZone).filter(ParkingZone.id == zone_id, ParkingZone.is_deleted == False).first()


def create_parking_zone(db: Session, zone: ParkingZoneCreate):
    # Case-insensitive validation: Check for duplicate name in same site (only non-deleted zones)
    existing_zone = db.query(ParkingZone).filter(
        and_(
            ParkingZone.org_id == zone.org_id,
            ParkingZone.site_id == zone.site_id,
            func.lower(ParkingZone.name) == func.lower(zone.name),
            ParkingZone.is_deleted == False  # Only check non-deleted zones
        )
    ).first()
    
    if existing_zone:
        return error_response(
            message=f"Parking zone with name '{zone.name}' already exists in this site",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )
    
    db_zone = ParkingZone(**zone.model_dump())
    db.add(db_zone)
    db.commit()
    db.refresh(db_zone)
    
    # Fetch with site name join
    result = (
        db.query(ParkingZone, Site.name.label('site_name'))
        .join(Site, ParkingZone.site_id == Site.id)
        .filter(ParkingZone.id == db_zone.id, ParkingZone.is_deleted == False)
        .first()
    )
    
    if result:
        zone, site_name = result
        zone_data = zone.__dict__.copy()
        zone_data["site_name"] = site_name
        return ParkingZoneOut.model_validate(zone_data)
    
    # Fallback without site_name
    zone_data = db_zone.__dict__.copy()
    zone_data["site_name"] = None
    return ParkingZoneOut.model_validate(zone_data)


def update_parking_zone(db: Session, zone_update: ParkingZoneUpdate):  # ✅ Changed parameter
    # Only allow updates on non-deleted zones
    db_zone = db.query(ParkingZone).filter(ParkingZone.id == zone_update.id, ParkingZone.is_deleted == False).first()  # ✅ Get ID from zone_update
    if not db_zone:
        return error_response(
            message="Parking zone not found",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=404
        )
    
    # Case-insensitive validation: Check if name is being updated and if it causes duplicates (only non-deleted zones)
    if hasattr(zone_update, 'name') and zone_update.name is not None and zone_update.name.lower() != db_zone.name.lower():
        existing_zone = db.query(ParkingZone).filter(
            and_(
                ParkingZone.org_id == db_zone.org_id,
                ParkingZone.site_id == db_zone.site_id,
                func.lower(ParkingZone.name) == func.lower(zone_update.name),
                ParkingZone.id != zone_update.id,  # Exclude current zone from check
                ParkingZone.is_deleted == False  # Only check non-deleted zones
            )
        ).first()
        
        if existing_zone:
            return error_response(
                message=f"Parking zone with name '{zone_update.name}' already exists in this site",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )
    
    # Update fields
    update_data = zone_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_zone, field, value)
    
    db.commit()
    db.refresh(db_zone)
    
    # Fetch with site name join
    result = (
        db.query(ParkingZone, Site.name.label('site_name'))
        .join(Site, ParkingZone.site_id == Site.id)
        .filter(ParkingZone.id == zone_update.id, ParkingZone.is_deleted == False)  # ✅ Use zone_update.id
        .first()
    )
    
    if result:
        zone, site_name = result
        zone_data = zone.__dict__.copy()
        zone_data["site_name"] = site_name
        return ParkingZoneOut.model_validate(zone_data)
    
    # Fallback without site_name
    zone_data = db_zone.__dict__.copy()
    zone_data["site_name"] = None
    return ParkingZoneOut.model_validate(zone_data)


def delete_parking_zone(db: Session, zone_id: str):
    # Soft delete implementation - mark as deleted instead of actual deletion
    db_zone = db.query(ParkingZone).filter(ParkingZone.id == zone_id, ParkingZone.is_deleted == False).first()
    if not db_zone:
        return None
    
    # Perform soft delete by setting is_deleted to True
    db_zone.is_deleted = True
    db_zone.updated_at = func.now()  # Update timestamp
    db.commit()
    
    return True