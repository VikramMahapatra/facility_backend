from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, distinct, func, or_, cast, Date
from uuid import UUID

from ...schemas.energy_iot.meters_schemas import BulkUploadError, MeterRequest

from ...models.energy_iot.meter_readings import MeterReading
from ...models.energy_iot.meters import Meter
from ...schemas.energy_iot.meter_readings_schemas import (
    BulkMeterReadingRequest, MeterReadingCreate, MeterReadingOut, MeterReadingListResponse, MeterReadingUpdate
)
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space


def get_meter_readings_overview(db: Session, org_id: UUID):
    # Total meters
    total_meters = (
        db.query(func.count(Meter.id))
        .filter(Meter.org_id == org_id, Meter.is_deleted == False)
        .scalar()
    ) or 0

    # Active meters
    active_meters = (
        db.query(func.count(Meter.id))
        .filter(Meter.org_id == org_id, Meter.status == "active", Meter.is_deleted == False)
        .scalar()
    ) or 0

    # Latest reading per meter
    # Get latest timestamp per meter_id
    sub_latest = (
        db.query(
            MeterReading.meter_id,
            func.max(MeterReading.ts).label("latest_ts")
        )
        .join(Meter, Meter.id == MeterReading.meter_id)
        .filter(Meter.org_id == org_id, Meter.is_deleted == False, MeterReading.is_deleted == False)
        .group_by(MeterReading.meter_id)
        .subquery()
    )

    latest_readings = db.query(func.count(sub_latest.c.meter_id)).scalar() or 0

    # IoT connected meters — meters whose latest reading source == 'iot'
    iot_connected = (
        db.query(func.count(distinct(MeterReading.meter_id)))
        .join(Meter, Meter.id == MeterReading.meter_id)
        .filter(
            Meter.org_id == org_id,
            MeterReading.source == "iot",
            Meter.is_deleted == False,
            MeterReading.is_deleted == False
        )
        .scalar()
        or 0
    )

    return {
        "totalMeters": total_meters,
        "activeMeters": active_meters,
        "latestReadings": latest_readings,
        "iotConnected": iot_connected,
    }

def get_list(db: Session, org_id: UUID, params: MeterRequest, is_export: bool = False) -> MeterReadingListResponse:
    """Return all readings, optionally filtered by meter."""
    q = db.query(MeterReading).join(Meter).filter(MeterReading.is_deleted == False, Meter.is_deleted == False)

    if params.search:
        search_term = f"%{params.search}%"
        q = q.filter(  # Note: you need to assign back to q
            or_(
                Meter.code.ilike(search_term),
                Meter.kind.ilike(search_term)
            )
        )

    total = None
    if not is_export:
        total = q.with_entities(func.count(MeterReading.id)).scalar()

    # Apply ordering, offset, and limit
    q = q.order_by(MeterReading.ts.desc())
    
    if not is_export:
        q = q.offset(params.skip).limit(params.limit)

    # Execute the query
    meter_readings = q.all()

    readings = []
    for r in meter_readings:
        readings.append(
            MeterReadingOut.model_validate(
                {
                    **r.__dict__,
                    "meter_code": r.meter.code if r.meter else None,
                    "meter_kind": r.meter.kind if r.meter else None,
                    "unit": r.meter.unit if r.meter else None,
                }
            )
        )

    if is_export:
        return {"readings": readings}

    return {"readings": readings, "total": total}  # Use the total count we calculated earlier

def create(db: Session, payload: MeterReadingCreate) -> MeterReading:
    obj = MeterReading(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update(db: Session, payload: MeterReadingUpdate) -> Optional[MeterReading]:
    obj = db.query(MeterReading).filter(MeterReading.id == payload.id, MeterReading.is_deleted == False).first()
    if not obj:
        return None

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)

    db.commit()
    db.refresh(obj)
    return obj


def delete(db: Session, meter_reading_id: UUID) -> Optional[MeterReading]:
    obj = db.query(MeterReading).filter(MeterReading.id == meter_reading_id, MeterReading.is_deleted == False).first()
    if not obj:
        return None
    
    # SOFT DELETE - Change from hard delete to soft delete
    obj.is_deleted = True
    db.commit()
    
    return obj


def meter_reading_lookup(db: Session, org_id: str):
    rows = (
        db.query(
            Meter.id.label("id"),
            # Format: "CODE - Site Name" (matches your screenshot)
            func.concat(Meter.code, ' - ', Site.name).label("name")
        )
        .join(Site, Site.id == Meter.site_id)
        .filter(Meter.org_id == org_id)
        .filter(Meter.status == 'active')
        .filter(Meter.is_deleted == False)
        .order_by(func.concat(Meter.code, ' - ', Site.name).asc())
        .all()
    )
    return [{"id": str(r.id), "name": r.name} for r in rows]


def bulk_update_readings(db: Session, request: BulkMeterReadingRequest):
    inserted, updated = 0, 0
    rowHeaderIndex = 2
    bulk_error_list = []
    for m in request.readings:
        errors = []
        meter_id = db.query(Meter.id).filter(
            Meter.code == m.meterCode, Meter.is_deleted == False).scalar()

        if not meter_id:
            errors.append("Meter code doesn't exist in the system")

        if not errors:

            obj = (
                db.query(MeterReading)
                .filter(
                    MeterReading.meter_id == meter_id,
                    cast(MeterReading.ts, Date) == m.timestamp.date(),
                    MeterReading.is_deleted == False
                ).first()
            )

            if not obj:
                # insert reading
                data = m.model_dump(exclude={"meterCode"})
                data["ts"] = data.pop("timestamp")  # ✅ rename key
                data.pop("meter_id", None)

                reading_data = MeterReading(**data, meter_id=meter_id)
                db.add(reading_data)
                inserted += 1

            else:
                # update reading
                data = m.model_dump(exclude_unset=True, exclude={"meterCode"})
                for k, v in data.items():
                    setattr(obj, k, v)
                updated += 1
        else:
            row_error = BulkUploadError(row=rowHeaderIndex, errors=errors)
            bulk_error_list.append(row_error)

        rowHeaderIndex += 1

    db.commit()
    return {"inserted": inserted, "validations": bulk_error_list}