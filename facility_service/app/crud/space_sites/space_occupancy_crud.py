# services/space_occupancy_service.py
from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from uuid import UUID

from facility_service.app.models.leasing_tenants.leases import Lease
from shared.utils.app_status_code import AppStatusCode
from shared.utils.enums import OwnershipStatus

from ...models.space_sites.space_occupancy_events import OccupancyEventType, SpaceOccupancyEvent
from ...models.space_sites.spaces import Space
from shared.helpers.json_response_helper import error_response

from ...schemas.space_sites.space_occupany_schemas import MoveInRequest
from shared.models.users import Users

from ...models.leasing_tenants.tenant_spaces import TenantSpace
from ...models.leasing_tenants.tenants import Tenant
from ...models.space_sites.space_occupancies import OccupancyStatus, OccupantType, SpaceOccupancy
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
        return {
            "status": "vacant",
            "history": get_occupancy_timeline(db, auth_db, space_id)
        }

    current_occupany = {
        "status": "occupied",
        "occupant_type": occ.occupant_type,
        "occupant_name": get_user_name(auth_db, occ.occupant_user_id),
        "move_in_date": occ.move_in_date,
        "reference_no": str(occ.source_id) if occ.source_id else None,
    }

    return {
        "current": current_occupany,
        "history": get_occupancy_timeline(db, auth_db, space_id)
    }


def move_in(
    db: Session,
    user_id: UUID,
    params: MoveInRequest
):
    try:
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
            return error_response(message="Space is already occupied")

        if params.occupant_type == "tenant":
            if not params.tenant_id:
                params.tenant_id = (
                    db.query(Tenant.id)
                    .filter(
                        Tenant.user_id == user_id,
                        SpaceOccupancy.status == "active"
                    )
                    .first()
                )

            if params.tenant_id and not params.lease_id:
                params.lease_id = (
                    db.query(Lease.id)
                    .filter(
                        Lease.space_id == params.space_id,
                        Lease.tenant_id == params.tenant_id,
                        Lease.status == "active",
                        Lease.is_deleted == False
                    )
                    .first()
                )

        # 2️⃣ Create occupancy
        occ = SpaceOccupancy(
            space_id=params.space_id,
            occupant_type=params.occupant_type,
            occupant_user_id=params.occupant_user_id,
            lease_id=params.lease_id,
            source_id=params.tenant_id,
            move_in_date=func.now(),
            heavy_items=params.heavy_items,
            elevator_required=params.elevator_required,
            parking_required=params.parking_required,
            status=params.status
        )

        db.add(occ)

        # 3️⃣ Optional: sync related tables
        db.query(Space).filter(
            Space.id == params.space_id,
        ).update({
            "status": "occupied"
        })

        log_occupancy_event(
            db,
            space_id=params.space_id,
            event_type=OccupancyEventType.moved_in,
            occupant_type=params.occupant_type,
            occupant_user_id=params.occupant_user_id,
            source_id=params.tenant_id,
            lease_id=params.lease_id
        )

        db.commit()
        db.refresh(occ)

        return occ
    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def move_out(db: Session, space_id: UUID):
    try:
        now = datetime.now(timezone.utc)
        occ = db.query(SpaceOccupancy).filter(
            SpaceOccupancy.space_id == space_id,
            SpaceOccupancy.status == "active"
        ).first()

        if not occ:
            return error_response(message="Space already vacant")

        occ.status = "moved_out"
        occ.move_out_date = func.now()

        db.query(Space).filter(
            Space.id == space_id,
        ).update({
            "status": "available"
        })

        if occ.occupant_type == OccupantType.tenant:
            # End active lease
            lease = db.query(Lease).filter(
                Lease.id == occ.lease_id,
                Lease.is_deleted == False,
                Lease.status == "active"
            ).first()

            if lease:
                lease.status = "terminated"   # or "terminated"
                lease.end_date = now

            # End tenant-space mapping
            db.query(TenantSpace).join(
                Tenant, Tenant.id == TenantSpace.tenant_id, Tenant.is_deleted == False
            ).filter(
                TenantSpace.space_id == space_id,
                Tenant.user_id == occ.occupant_user_id,
                TenantSpace.is_deleted == False,
                TenantSpace.status == OwnershipStatus.leased
            ).update({
                "status": OwnershipStatus.ended,
                "updated_at": now
            })

        log_occupancy_event(
            db,
            space_id=space_id,
            event_type=OccupancyEventType.moved_out,
            occupant_type=occ.occupant_type,
            occupant_user_id=occ.occupant_user_id,
            source_id=occ.source_id,
            lease_id=occ.lease_id
        )

        db.commit()
    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def get_occupancy_history(db: Session, space_id: UUID):
    return (
        db.query(SpaceOccupancy)
        .filter(SpaceOccupancy.space_id == space_id)
        .order_by(SpaceOccupancy.move_in_date.desc())
        .all()
    )


def get_occupancy_timeline(
    db: Session,
    auth_db: Session,
    space_id: UUID
):
    events = (
        db.query(SpaceOccupancyEvent)
        .filter(SpaceOccupancyEvent.space_id == space_id)
        .order_by(SpaceOccupancyEvent.event_date.asc())
        .all()
    )

    timeline = []

    for e in events:
        occupant_name = get_user_name(
            auth_db,
            e.occupant_user_id
        )

        timeline.append({
            "event": e.event_type,
            "occupant_type": e.occupant_type,
            "occupant_user_id": e.occupant_user_id,
            "occupant_name": occupant_name,
            "date": e.event_date,
            "notes": e.notes,
        })

    return timeline


def get_user_name(auth_db: Session, user_id: UUID) -> str:
    if not user_id:
        return None

    user = auth_db.query(Users.full_name).filter(
        Users.id == user_id, Users.is_deleted == False).first()
    return user.full_name if user else None


def log_occupancy_event(
    db: Session,
    space_id: UUID,
    event_type: OccupancyEventType,
    occupant_type: OccupantType | None = None,
    occupant_user_id: UUID | None = None,
    source_id: UUID | None = None,
    lease_id: UUID | None = None,
    notes: str | None = None
):
    event = SpaceOccupancyEvent(
        space_id=space_id,
        event_type=event_type,
        occupant_type=occupant_type,
        occupant_user_id=occupant_user_id,
        source_id=source_id,
        lease_id=lease_id,
        notes=notes
    )
    db.add(event)
    db.commit()
