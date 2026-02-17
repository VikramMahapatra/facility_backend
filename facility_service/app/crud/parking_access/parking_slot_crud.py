from uuid import UUID
from facility_service.app.models.parking_access.parking_slots import ParkingSlot
from sqlalchemy import func, case
from sqlalchemy.orm import Session
from facility_service.app.models.parking_access.parking_zones import ParkingZone
from facility_service.app.models.space_sites.sites import Site
from facility_service.app.models.space_sites.spaces import Space
from facility_service.app.schemas.parking_access.parking_slot_schemas import ParkingSlotCreate, ParkingSlotOut, ParkingSlotUpdate
from shared.core.schemas import Lookup, UserToken
from shared.helpers.json_response_helper import error_response


def get_parking_slots(db: Session, org_id: UUID, params):

    query = (
        db.query(
            ParkingSlot,
            Site.name.label("site_name"),
            ParkingZone.name.label("zone_name"),
            Space.name.label("space_name")
        )
        .join(Site, ParkingSlot.site_id == Site.id)
        .join(ParkingZone, ParkingSlot.zone_id == ParkingZone.id)
        .outerjoin(Space, ParkingSlot.space_id == Space.id)  # optional
        .filter(
            ParkingSlot.org_id == org_id,
            ParkingSlot.is_deleted == False
        )
    )

    if params.search:
        query = query.filter(
            ParkingSlot.slot_no.ilike(f"%{params.search}%")
        )

    if params.site_id:
        query = query.filter(ParkingSlot.site_id == params.site_id)

    if params.zone_id:
        query = query.filter(ParkingSlot.zone_id == params.zone_id)

    total = query.count()

    rows = (
        query.order_by(ParkingSlot.created_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    slots = []

    for slot, site_name, zone_name, space_name in rows:
        slots.append(
            ParkingSlotOut.model_validate(
                {
                    **slot.__dict__,
                    "site_name": site_name,
                    "zone_name": zone_name,
                    "space_name": space_name
                }
            )
        )

    return {
        "slots": slots,
        "total": total
    }


def get_parking_slot_overview(db: Session, org_id: UUID):

    result = db.query(
        func.count(ParkingSlot.id).label("total_slots"),

        func.sum(
            case(
                (ParkingSlot.space_id == None, 1),
                else_=0
            )
        ).label("available_slots"),

        func.sum(
            case(
                (ParkingSlot.space_id != None, 1),
                else_=0
            )
        ).label("assigned_slots"),

    ).filter(
        ParkingSlot.org_id == org_id,
        ParkingSlot.is_deleted == False
    ).one()

    return {
        "totalSlots": result.total_slots or 0,
        "availableSlots": result.available_slots or 0,
        "assignedSlots": result.assigned_slots or 0
    }


def create_parking_slot(db: Session, data: ParkingSlotCreate):

    slot = ParkingSlot(
        **data.model_dump()
    )

    db.add(slot)
    db.commit()
    db.refresh(slot)

    return slot


def update_parking_slot(db: Session, data: ParkingSlotUpdate):

    slot = db.query(ParkingSlot).filter(
        ParkingSlot.id == data.id,
        ParkingSlot.org_id == data.org_id,
        ParkingSlot.is_deleted == False
    ).first()

    if not slot:
        return error_response(message="Parking slot not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(slot, key, value)

    db.commit()
    db.refresh(slot)

    return get_slot_details(db, slot.org_id, slot.id)


def get_slot_details(db: Session, org_id: UUID, slot_id: UUID):

    result = (
        db.query(
            ParkingSlot,
            Site.name.label("site_name"),
            ParkingZone.name.label("zone_name"),
            Space.name.label("space_name")
        )
        .join(Site, ParkingSlot.site_id == Site.id)
        .join(ParkingZone, ParkingSlot.zone_id == ParkingZone.id)
        .outerjoin(Space, ParkingSlot.space_id == Space.id)  # optional
        .filter(
            ParkingSlot.id == slot_id,
            ParkingSlot.org_id == org_id,
            ParkingSlot.is_deleted == False
        )
        .first()
    )

    if not result:
        return None

    slot, site_name, zone_name, space_name = result

    return ParkingSlotOut.model_validate(
        {
            **slot.__dict__,
            "site_name": site_name,
            "zone_name": zone_name,
            "space_name": space_name
        }
    )


def delete_parking_slot(db: Session, org_id: UUID, slot_id: UUID):

    slot = db.query(ParkingSlot).filter(
        ParkingSlot.id == slot_id,
        ParkingSlot.org_id == org_id
    ).first()

    if not slot:
        return error_response(message="Parking slot not found")

    slot.is_deleted = True

    db.commit()

    return {"success": True}


def available_parking_slot_lookup(db: Session, org_id: UUID, zone_id: UUID):

    slots = (
        db.query(
            ParkingSlot.id,
            ParkingSlot.slot_no
        )
        .join(Site, ParkingSlot.site_id == Site.id)
        .join(ParkingZone, ParkingSlot.zone_id == ParkingZone.id)
        .outerjoin(Space, ParkingSlot.space_id == Space.id)  # optional
        .filter(
            ParkingSlot.org_id == org_id,
            ParkingSlot.is_deleted == False,
            ParkingSlot.zone_id == zone_id,
            ParkingSlot.space_id.isnot(None)
        )
        .all()
    )

    return [
        Lookup(id=slot.id, name=slot.name)
        for slot in slots
    ]
