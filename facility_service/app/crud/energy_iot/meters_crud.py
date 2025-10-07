from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_
from uuid import UUID
from datetime import datetime

from ...models.maintenance_assets.assets import Asset

from ...models.energy_iot.meters import Meter
from ...models.energy_iot.meter_readings import MeterReading
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space

from ...schemas.energy_iot.meters_schemas import MeterCreate, MeterUpdate, MeterOut, MeterListResponse


def get_list(db: Session, org_id: UUID, site_id: Optional[UUID] = None) -> MeterListResponse:
    """Return all meters with site, space, and last reading info."""
    query = (
        db.query(Meter)
        .options(
            joinedload(Meter.site).load_only(Site.id, Site.name),
            joinedload(Meter.space).load_only(Space.id, Space.name),
            joinedload(Meter.asset).load_only(Asset.id, Asset.name),
        )
        .filter(Meter.org_id == org_id)
    )

    if site_id and str(site_id).lower() != "all":
        query = query.filter(Meter.site_id == site_id)

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
                    "siteName": m.site.name if m.site else None,
                    "spaceName": m.space.name if m.space else None,
                    "assetName": m.asset.name if m.asset else None,
                    "status": "active",  # example static, replace with real logic if available
                    "lastReading": float(last_read.reading) if last_read else None,
                    "lastReadingDate": last_read.ts.isoformat() if last_read else None,
                }
            )
        )

    return {"meters": result, "total": len(result)}


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
