from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, distinct, func, or_
from uuid import UUID

from ...schemas.energy_iot.meters_schemas import MeterRequest

from ...models.energy_iot.meter_readings import MeterReading
from ...models.energy_iot.meters import Meter
from ...schemas.energy_iot.meter_readings_schemas import (
    MeterReadingCreate, MeterReadingOut, MeterReadingListResponse, MeterReadingUpdate
)


def get_meter_readings_overview(db: Session, org_id: UUID):
    # Total meters
    total_meters = (
        db.query(func.count(Meter.id))
        .filter(Meter.org_id == org_id)
        .scalar()
    ) or 0

    # Active meters
    active_meters = (
        db.query(func.count(Meter.id))
        .filter(Meter.org_id == org_id, Meter.status == "active")
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
        .filter(Meter.org_id == org_id)
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
            MeterReading.source == "iot"
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


def get_list(db: Session, org_id: UUID, params: MeterRequest) -> MeterReadingListResponse:
    """Return all readings, optionally filtered by meter."""
    q = db.query(MeterReading).join(Meter)

    if params.search:
        search_term = f"%{params.search}%"
        q.filter(
            or_(
                Meter.code.ilike(search_term),
                Meter.kind.ilike(search_term)
            )
        )

    total = q.with_entities(func.count(MeterReading.id)).scalar()

    meter_readings = (
        q
        .order_by(MeterReading.ts.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

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

    return {"readings": readings, "total": len(readings)}


def create(db: Session, payload: MeterReadingCreate) -> MeterReading:
    obj = MeterReading(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update(db: Session, payload: MeterReadingUpdate) -> Optional[Meter]:
    obj = db.query(MeterReading).filter(MeterReading.id == payload.id).first()
    if not obj:
        return None

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)

    db.commit()
    db.refresh(obj)
    return obj


def delete(db: Session, meter_reading_id: UUID) -> Optional[Meter]:
    obj = db.query(MeterReading).filter(
        MeterReading.id == meter_reading_id).first()
    if not obj:
        return None
    db.delete(obj)
    db.commit()
    return obj
