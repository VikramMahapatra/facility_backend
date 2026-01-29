# services/space_occupancy_service.py
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from uuid import UUID

from shared.models.users import Users

from ...models.leasing_tenants.tenant_spaces import TenantSpace
from ...models.leasing_tenants.tenants import Tenant
from ...models.space_sites.space_occupancies import OccupancyStatus, SpaceOccupancy
from ...models.space_sites.space_owners import SpaceOwner


def get_current_occupancy(db: Session, auth_db: Session, space_id: UUID):
    occ = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.space_id == space_id,
            SpaceOccupancy.is_active == True
        )
        .first()
    )

    if not occ:
        return {"status": "vacant"}

    return {
        "status": "occupied",
        "occupant_type": occ.occupant_type,
        "occupant_name": get_user_name(auth_db, occ.occupant_user_id),
        "move_in_at": occ.move_in_at,
        "reference_no": str(occ.reference_id) if occ.reference_id else None,
    }


def move_in(db: Session, space_id: UUID, occupant_type: str):
    active = db.query(SpaceOccupancy).filter(
        SpaceOccupancy.space_id == space_id,
        SpaceOccupancy.is_active == True
    ).first()

    if active:
        raise HTTPException(400, "Space already occupied")

    occ = SpaceOccupancy(
        space_id=space_id,
        occupant_type=occupant_type,
        is_active=True
    )
    db.add(occ)
    db.commit()


def move_out(db: Session, space_id: UUID):
    occ = db.query(SpaceOccupancy).filter(
        SpaceOccupancy.space_id == space_id,
        SpaceOccupancy.is_active == True
    ).first()

    if not occ:
        raise HTTPException(400, "Space already vacant")

    occ.is_active = False
    occ.move_out_at = func.now()
    db.commit()


def get_occupancy_history(db: Session, space_id: UUID):
    return (
        db.query(SpaceOccupancy)
        .filter(SpaceOccupancy.space_id == space_id)
        .order_by(SpaceOccupancy.move_in_at.desc())
        .all()
    )


def get_user_name(auth_db: Session, user_id: UUID) -> str:
    if not user_id:
        return "Unknown User"

    user = auth_db.query(Users.full_name).filter(
        Users.id == user_id, Users.is_deleted == False).first()
    return user.full_name if user else "Unknown User"
