from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from uuid import UUID
from datetime import date

from facility_service.app.models.parking_access.parking_zones import ParkingZone

from ...enum.parking_passes_enum import ParkingPassStatus
from shared.core.schemas import Lookup

from ...models.parking_access.parking_pass import ParkingPass
from ...schemas.parking_access.parking_pass_schemas import (
    ParkingPassCreate,
    ParkingPassUpdate,
    ParkingPassRequest,
)


# ---------------- FILTER BUILDER ----------------
def build_pass_filters(org_id: UUID, params: ParkingPassRequest):
    filters = [
        ParkingPass.org_id == org_id,
        ParkingPass.is_deleted == False
    ]

    if params.site_id and params.site_id != "all":
        filters.append(ParkingPass.site_id == params.site_id)

    if params.zone_id:
        filters.append(ParkingPass.zone_id == params.zone_id)

    if params.status:
        filters.append(func.lower(ParkingPass.status) == func.lower(params.status))

    if params.search:
        filters.append(ParkingPass.vehicle_no.ilike(f"%{params.search}%"))

    return filters


# ---------------- LIST ----------------
def get_parking_passes(db: Session, org_id: UUID, params: ParkingPassRequest):
    filters = build_pass_filters(org_id, params)

    base_query = db.query(ParkingPass).filter(*filters)

    total = base_query.with_entities(func.count(ParkingPass.id)).scalar()

    results = (
        base_query
        .order_by(ParkingPass.valid_to.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    return {"passes": results, "total": total}


# ---------------- GET BY ID ----------------
def get_parking_pass_by_id(db: Session, pass_id: UUID):
    return (
        db.query(ParkingPass)
        .filter(ParkingPass.id == pass_id, ParkingPass.is_deleted == False)
        .first()
    )


# ---------------- CREATE ----------------
def create_parking_pass(db: Session, data: ParkingPassCreate):
    db_pass = ParkingPass(**data.model_dump())
    db.add(db_pass)
    db.commit()
    db.refresh(db_pass)
    return db_pass


# ---------------- UPDATE ----------------
def update_parking_pass(db: Session, data: ParkingPassUpdate):
    db_pass = get_parking_pass_by_id(db, data.id)
    if not db_pass:
        return None

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(db_pass, k, v)

    db.commit()
    db.refresh(db_pass)
    return db_pass


# ---------------- SOFT DELETE ----------------
def delete_parking_pass(db: Session, pass_id: UUID):
    db_pass = get_parking_pass_by_id(db, pass_id)
    if not db_pass:
        return None

    db_pass.is_deleted = True
    db.commit()
    return True

def get_parking_pass_overview(db: Session, org_id):
    today = date.today()

    total_passes = (
        db.query(func.count(ParkingPass.id))
        .filter(
            ParkingPass.org_id == org_id,
            ParkingPass.is_deleted == False
        )
        .scalar()
    )

    active_passes = (
        db.query(func.count(ParkingPass.id))
        .filter(
            ParkingPass.org_id == org_id,
            func.lower(ParkingPass.status) == "active",  # Case-insensitive
            ParkingPass.valid_to >= today,
            ParkingPass.is_deleted == False
        )
        .scalar()
    )

    expired_passes = (
        db.query(func.count(ParkingPass.id))
        .filter(
            ParkingPass.org_id == org_id,
            ParkingPass.is_deleted == False,
            ParkingPass.valid_to < today
        )
        .scalar()
    )

    blocked_passes = (
        db.query(func.count(ParkingPass.id))
        .filter(
            ParkingPass.org_id == org_id,
            func.lower(ParkingPass.status) == "blocked",  # Case-insensitive
            ParkingPass.is_deleted == False
        )
        .scalar()
    )

    return {
        "totalPasses": total_passes or 0,
        "activePasses": active_passes or 0,
        "expiredPasses": expired_passes or 0,
        "blockedPasses": blocked_passes or 0,
    }


def parkking_pass_status_lookup(db: Session, org_id: UUID):
    return [
        Lookup(id=status.value, name=status.capitalize())
        for status in ParkingPassStatus
    ]

def parking_pass_status_filter(db: Session, org_id: str):
   rows=(
       db.query(
              func.lower(ParkingPass.status).label("id"),
              func.initcap(ParkingPass.status).label("name")
              )
        .filter(ParkingPass.org_id == org_id,ParkingPass.is_deleted == False)
        .distinct()
        .order_by(func.lower(ParkingPass.status).asc())
        .all()
    )
   return [Lookup(id=row.id, name=row.name) for row in rows]
    
        
def parking_pass_zone_filter(db: Session, org_id: str): 
    rows=(
         db.query(
                  ParkingPass.zone_id.label("id"),
                  ParkingZone.name.label("name")
                )
            .join(ParkingZone, ParkingPass.zone_id == ParkingZone.id)
          .filter(ParkingPass.org_id == org_id,ParkingPass.is_deleted == False)
          .distinct()
          .order_by(ParkingPass.zone_id.asc())
          .all()
     )
    return [Lookup(id=row.id, name=row.name) for row in rows] 

