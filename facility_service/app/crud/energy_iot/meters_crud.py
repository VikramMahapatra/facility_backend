from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from uuid import UUID
from datetime import datetime

from ...models.maintenance_assets.assets import Asset

from ...models.energy_iot.meters import Meter
from ...models.energy_iot.meter_readings import MeterReading
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space

from ...schemas.energy_iot.meters_schemas import BulkMeterRequest, BulkUploadError, MeterCreate, MeterImport, MeterRequest, MeterUpdate, MeterOut, MeterListResponse


def get_list(db: Session, org_id: UUID, params: MeterRequest, is_export: bool = False) -> MeterListResponse:
    query = (
        db.query(Meter)
        .options(
            joinedload(Meter.site).load_only(Site.id, Site.name),
            joinedload(Meter.space).load_only(Space.id, Space.name),
            joinedload(Meter.asset).load_only(Asset.id, Asset.name),
        )
        .filter(Meter.org_id == org_id)
    )

    if params.search:
        search_term = f"%{params.search}%"
        query.filter(
            or_(
                Meter.code.ilike(search_term),
                Meter.kind.ilike(search_term),
                Meter.site.name.ilike(search_term)
            )
        )

    total = None
    if not is_export:
        total = query.with_entities(func.count(Meter.id)).scalar()

    if not is_export:
        query = (
            query
            .order_by(Meter.code.asc())
            .offset(params.skip)
            .limit(params.limit)
        )
    else:
        query = query.order_by(Meter.code.asc())

    meters = query.all()

    result = []
    for m in meters:
        # fetch last reading
        last_read = (
            db.query(MeterReading)
            .filter(MeterReading.meter_id == m.id)
            .order_by(MeterReading.ts.desc())
            .first()
        )

        result.append(
            MeterOut.model_validate(
                {
                    **m.__dict__,
                    "site_name": m.site.name if m.site else None,
                    "space_name": m.space.name if m.space else None,
                    "asset_name": m.asset.name if m.asset else None,
                    "status": "active",  # example static, replace with real logic if available
                    "last_reading": float(last_read.reading) if last_read else None,
                    "last_reading_date": last_read.ts.isoformat() if last_read else None,
                }
            )
        )

    if is_export:
        return {"meters": result}

    return {"meters": result, "total": total}


def get_by_id(db: Session, meter_id: UUID) -> Optional[MeterOut]:
    m = (
        db.query(Meter)
        .options(
            joinedload(Meter.site).load_only(Site.name),
            joinedload(Meter.space).load_only(Space.name),
            joinedload(Meter.asset).load_only(Asset.name),
        )
        .filter(Meter.id == meter_id)
        .first()
    )
    if not m:
        return None

    last_read = (
        db.query(MeterReading)
        .filter(MeterReading.meter_id == m.id)
        .order_by(MeterReading.ts.desc())
        .first()
    )

    return MeterOut.model_validate(
        {
            **m.__dict__,
            "siteName": m.site.name if m.site else None,
            "spaceName": m.space.name if m.space else None,
            "assetName": m.asset.name if m.asset else None,
            "status": "active",
            "lastReading": float(last_read.reading) if last_read else None,
            "lastReadingDate": last_read.ts.isoformat() if last_read else None,
        }
    )


def bulk_update_meters(db: Session, request: BulkMeterRequest):
    inserted, updated = 0, 0
    rowHeaderIndex = 2
    bulk_error_list = []
    for m in request.meters:
        errors = []
        obj = db.query(Meter).filter(Meter.code == m.code).first()

        site_id = db.query(Site.id).filter(
            Site.name == m.siteName).scalar()
        space_id = db.query(Space.id).filter(
            Space.name == m.spaceName).scalar()

        if not site_id:
            errors.append("Site doesn't exist in the system")

        if not space_id:
            errors.append("Space doesn't exist in the system")

        if not errors:
            m.site_id = site_id
            m.space_id = space_id

            if not obj:
                # create meter
                meter_data = Meter(
                    **m.model_dump(exclude={"siteName", "spaceName"}))
                db.add(obj)
                inserted += 1

            else:
                # update meter
                data = m.model_dump(exclude_unset=True, exclude={
                                    "siteName", "spaceName"})
                for k, v in data.items():
                    setattr(obj, k, v)

                updated += 1
        else:
            row_error = BulkUploadError(row=rowHeaderIndex, errors=errors)
            bulk_error_list.append(row_error)

        rowHeaderIndex += 1

    db.commit()
    return {"inserted": inserted, "validations": bulk_error_list}


def create(db: Session, payload: MeterCreate) -> Meter:
    obj = Meter(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update(db: Session, payload: MeterUpdate) -> Optional[Meter]:
    obj = db.query(Meter).filter(Meter.id == payload.id).first()
    if not obj:
        return None

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)

    db.commit()
    db.refresh(obj)
    return obj


def delete(db: Session, meter_id: UUID) -> Optional[Meter]:
    obj = db.query(Meter).filter(Meter.id == meter_id).first()
    if not obj:
        return None
    db.delete(obj)
    db.commit()
    return obj
