import uuid
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, or_, case, literal, Numeric, and_
from dateutil.relativedelta import relativedelta
from sqlalchemy.dialects.postgresql import UUID

from ...models.space_sites.sites import Site
from ...models.parking_access.parking_zones import ParkingZone
from ...schemas.parking_access.parking_zone_schemas import ParkingZoneCreate, ParkingZoneOut, ParkingZoneRequest, ParkingZoneUpdate, ParkingZonesResponse


# ----------------------------------------------------------------------
# CRUD OPERATIONS
# ----------------------------------------------------------------------

def build_parking_zone_filters(org_id: UUID, params: ParkingZoneRequest):
    filters = [ParkingZone.org_id == org_id]

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

    zone_fields = db.query(
        func.count(ParkingZone.id).label("total_zones"),
        func.coalesce(func.sum(ParkingZone.capacity),
                      0).label("total_capacity"),
    ).filter(ParkingZone.org_id == org_id).one()

    if zone_fields.total_zones > 0:
        avg_capacity = zone_fields.total_capacity / zone_fields.total_zones
    else:
        avg_capacity = 0

    return {
        "totalZones": int(zone_fields.total_zones or 0),
        "totalCapacity": int(zone_fields.total_capacity or 0),
        "avgCapacity": float(avg_capacity or 0),
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
    return db.query(ParkingZone).filter(ParkingZone.id == zone_id).first()


def create_parking_zone(db: Session, zone: ParkingZoneCreate):
    db_zone = ParkingZone(**zone.model_dump())
    db.add(db_zone)
    db.commit()
    db.refresh(db_zone)
    return db_zone


def update_parking_zone(db: Session, zone: ParkingZoneUpdate):
    db_zone = get_zone_by_id(db, zone.id)
    if not db_zone:
        return None
    for k, v in zone.dict(exclude_unset=True).items():
        setattr(db_zone, k, v)
    db.commit()
    db.refresh(db_zone)
    return db_zone


def delete_parking_zone(db: Session, zone_id: str):
    db_zone = get_zone_by_id(db, zone_id)
    if not db_zone:
        return None
    db.delete(db_zone)
    db.commit()
    return True
