from uuid import UUID
from facility_service.app.models.parking_access.parking_slots import ParkingSlot
from sqlalchemy import func, case
from sqlalchemy.orm import Session
from shared.core.schemas import UserToken
from shared.helpers.json_response_helper import error_response


def get_parking_slots(db: Session, org_id: UUID, params):

    query = db.query(ParkingSlot).filter(
        ParkingSlot.org_id == org_id,
        ParkingSlot.is_deleted == False
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

    slots = (
        query.order_by(ParkingSlot.created_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
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
                (ParkingSlot.status == "available", 1),
                else_=0
            )
        ).label("available_slots"),
        func.sum(
            case(
                (ParkingSlot.status == "assigned", 1),
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


def create_parking_slot(db: Session, org_id: UUID, data):

    slot = ParkingSlot(
        org_id=org_id,
        **data.model_dump()
    )

    db.add(slot)
    db.commit()
    db.refresh(slot)

    return slot


def update_parking_slot(db: Session, org_id: UUID, data):

    slot = db.query(ParkingSlot).filter(
        ParkingSlot.id == data.id,
        ParkingSlot.org_id == org_id,
        ParkingSlot.is_deleted == False
    ).first()

    if not slot:
        return error_response(message="Parking slot not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(slot, key, value)

    db.commit()
    db.refresh(slot)

    return slot


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
