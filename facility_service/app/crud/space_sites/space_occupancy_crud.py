# services/space_occupancy_service.py
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from uuid import UUID

from ...schemas.space_sites.space_occupany_schemas import MoveInRequest
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
            SpaceOccupancy.status == "active"
        )
        .first()
    )

    if not occ:
        return {"status": "vacant"}

    current_occupany = {
        "status": "occupied",
        "occupant_type": occ.occupant_type,
        "occupant_name": get_user_name(auth_db, occ.occupant_user_id),
        "move_in_date": occ.move_in_date,
        "reference_no": str(occ.source_id) if occ.source_id else None,
    }

    return {
        "current": current_occupany,
        "history": get_occupancy_history(db, space_id)
    }


def move_in(
    db: Session,
    params: MoveInRequest
):
    # 1️⃣ Check if space already occupied
    active = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.space_id == params.space_id,
            SpaceOccupancy.status == "active"
        )
        .first()
    )

    if active:
        raise HTTPException(
            status_code=400,
            detail="Space is already occupied"
        )

    # 2️⃣ Create occupancy
    occ = SpaceOccupancy(
        space_id=params.space_id,
        occupant_type=params.occupant_type,
        occupant_user_id=params.occupant_user_id,
        lease_id=params.lease_id,
        source_id=params.tenant_id,
        move_in_date=func.now(),
        status="active"
    )

    db.add(occ)

    # 3️⃣ Optional: sync related tables
    if params.occupant_type == "tenant" and params.tenant_id:
        db.query(TenantSpace).filter(
            TenantSpace.tenant_id == params.tenant_id,
            TenantSpace.space_id == params.space_id,
        ).update({
            "status": "occupied"
        })

    db.commit()
    db.refresh(occ)

    return occ


def move_out(db: Session, space_id: UUID):
    occ = db.query(SpaceOccupancy).filter(
        SpaceOccupancy.space_id == space_id,
        SpaceOccupancy.status == "active"
    ).first()

    if not occ:
        raise HTTPException(400, "Space already vacant")

    occ.status = "moved_out"
    occ.move_out_at = func.now()
    db.commit()


def get_occupancy_history(db: Session, space_id: UUID):
    return (
        db.query(SpaceOccupancy)
        .filter(SpaceOccupancy.space_id == space_id)
        .order_by(SpaceOccupancy.move_in_date.desc())
        .all()
    )


def get_user_name(auth_db: Session, user_id: UUID) -> str:
    if not user_id:
        return "Unknown User"

    user = auth_db.query(Users.full_name).filter(
        Users.id == user_id, Users.is_deleted == False).first()
    return user.full_name if user else "Unknown User"
