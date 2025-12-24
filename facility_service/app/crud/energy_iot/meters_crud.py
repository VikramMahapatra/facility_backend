from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from uuid import UUID
from datetime import datetime

from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response

from ...models.maintenance_assets.assets import Asset

from ...models.energy_iot.meters import Meter
from ...models.energy_iot.meter_readings import MeterReading
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space

from ...schemas.energy_iot.meters_schemas import BulkMeterRequest, BulkUploadError, MeterCreate, MeterImport, MeterRequest, MeterUpdate, MeterOut, MeterListResponse

from sqlalchemy import and_, func
from fastapi import HTTPException, status


def get_list(db: Session, org_id: UUID, params: MeterRequest, is_export: bool = False) -> MeterListResponse:
    query = (
        db.query(Meter)
        .options(
            joinedload(Meter.site).load_only(Site.id, Site.name),
            joinedload(Meter.space).load_only(Space.id, Space.name),
            joinedload(Meter.asset).load_only(Asset.id, Asset.name),
        )
        .filter(Meter.org_id == org_id, Meter.is_deleted == False)
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
        .filter(Meter.id == meter_id, Meter.is_deleted == False)
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
        obj = db.query(Meter).filter(Meter.code == m.code,
                                     Meter.is_deleted == False).first()

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
                db.add(meter_data)
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
    # Case-insensitive validation: Check for duplicate meter code in same org + space
    existing_meter = db.query(Meter).filter(
        and_(
            Meter.org_id == payload.org_id,
            Meter.space_id == payload.space_id,  # Same space
            func.lower(Meter.code) == func.lower(
                payload.code),  # Case-insensitive
            Meter.is_deleted == False
        )
    ).first()

    if existing_meter:
        return error_response(
            message=f"Meter with code '{payload.code}' already exists in this space",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )

    obj = Meter(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)

    # Use your Pydantic model for serialization
    return MeterOut.model_validate(obj)


def update(db: Session, payload: MeterUpdate) -> Optional[Meter]:
    obj = db.query(Meter).filter(Meter.id == payload.id,
                                 Meter.is_deleted == False).first()
    if not obj:
        return None

    # Get target space_id (use new value if provided, otherwise keep current)
    target_space_id = getattr(payload, 'space_id', obj.space_id)
    target_code = getattr(payload, 'code', obj.code)

    # Check if code OR space is being changed (case-insensitive)
    code_changed = hasattr(
        payload, 'code') and payload.code is not None and payload.code.lower() != obj.code.lower()
    space_changed = hasattr(
        payload, 'space_id') and payload.space_id is not None and payload.space_id != obj.space_id

    # If either code or space is changing, check for duplicates in the TARGET space
    if code_changed or space_changed:
        existing_meter = db.query(Meter).filter(
            and_(
                Meter.org_id == obj.org_id,
                Meter.space_id == target_space_id,  # Check in TARGET space
                func.lower(Meter.code) == func.lower(
                    target_code),  # Check TARGET code
                Meter.id != payload.id,  # Exclude current meter
                Meter.is_deleted == False
            )
        ).first()

        if existing_meter:
            return error_response(
                message=f"Meter with code '{target_code}' already exists in this space",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )

    # Update fields
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)

    db.commit()

    obj = (
        db.query(Meter)
        .options(
            joinedload(Meter.site).load_only(Site.name),
            joinedload(Meter.space).load_only(Space.name),
            joinedload(Meter.asset).load_only(Asset.name),
        )
        .filter(Meter.id == payload.id)
        .first()
    )

    return MeterOut.model_validate(
        {
            **obj.__dict__,
            "site_name": obj.site.name if obj.site else None,
            "space_name": obj.space.name if obj.space else None,
            "asset_name": obj.asset.name if obj.asset else None,
        }
    )



def delete(db: Session, meter_id: UUID) -> Optional[Meter]:
    obj = db.query(Meter).filter(Meter.id == meter_id,
                                 Meter.is_deleted == False).first()
    if not obj:
        return None

    # SOFT DELETE - Change from hard delete to soft delete
    obj.is_deleted = True
    db.commit()

    return obj
