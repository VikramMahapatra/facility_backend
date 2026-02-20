# services/space_occupancy_service.py
from datetime import datetime, timezone, date
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from uuid import UUID

from facility_service.app.models.leasing_tenants.leases import Lease
from facility_service.app.models.space_sites.buildings import Building
from facility_service.app.models.space_sites.sites import Site
from facility_service.app.models.space_sites.space_handover import HandoverStatus, SpaceHandover
from shared.utils.app_status_code import AppStatusCode
from shared.utils.enums import OwnershipStatus

from ...models.space_sites.space_occupancy_events import OccupancyEventType, SpaceOccupancyEvent
from ...models.space_sites.spaces import Space
from shared.helpers.json_response_helper import error_response, success_response

from ...schemas.space_sites.space_occupany_schemas import MoveInRequest, MoveOutRequest, OccupancyApprovalRequest, SpaceMoveOutRequest, SpaceOccupancyRequestOut
from shared.models.users import Users

from ...models.leasing_tenants.tenant_spaces import TenantSpace
from ...models.leasing_tenants.tenants import Tenant
from ...models.space_sites.space_occupancies import OccupancyStatus, OccupantType, RequestType, SpaceOccupancy
from ...models.space_sites.space_owners import SpaceOwner
from datetime import date
from sqlalchemy import or_


def get_current_occupancy(db: Session, auth_db: Session, space_id: UUID):
    today = date.today()

    # ---------------------------
    # 1️⃣ Current active occupancy
    # ---------------------------
    occ = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.space_id == space_id,
            SpaceOccupancy.status == "active",
            SpaceOccupancy.move_in_date <= today,  # Already started
            or_(
                SpaceOccupancy.move_out_date == None,
                SpaceOccupancy.move_out_date > today  # Not yet moved out
            )
        )
        .first()
    )

    # If no current occupant
    if not occ:
        current_occupancy = {"status": "vacant"}
    else:
        current_occupancy = {
            "status": "occupied",
            "occupant_type": occ.occupant_type,
            "occupant_name": get_user_name(auth_db, occ.occupant_user_id),
            "move_in_date": occ.move_in_date,
            "move_out_date": occ.move_out_date,
            "time_slot": occ.time_slot,
            "heavy_items": occ.heavy_items,
            "elevator_required": occ.elevator_required,
            "parking_required": occ.parking_required,
            "reference_no": str(occ.source_id) if occ.source_id else None,
        }

        # Check if a handover exists for this occupancy
        handover = db.query(SpaceHandover).filter(
            SpaceHandover.occupancy_id == occ.id
        ).order_by(SpaceHandover.handover_date.desc()).first()

        if handover:
            current_occupancy["handover"] = {
                "handover_date": handover.handover_date,
                "handover_by": get_user_name(auth_db, handover.handover_by_user_id),
                "handover_to": get_user_name(auth_db, handover.handover_to_user_id) if handover.handover_to_user_id else None,
                "condition_notes": handover.condition_notes,
            }

    # ---------------------------
    # 2️⃣ Upcoming move-ins
    # ---------------------------
    upcoming = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.space_id == space_id,
            SpaceOccupancy.status == "active",
            SpaceOccupancy.move_in_date > today,  # Future move-ins
        )
        .order_by(SpaceOccupancy.move_in_date.asc())
        .all()
    )

    upcoming_list = [
        {
            "occupant_type": u.occupant_type,
            "occupant_name": get_user_name(auth_db, u.occupant_user_id),
            "move_in_date": u.move_in_date,
            "move_out_date": u.move_out_date,
            "time_slot": u.time_slot,
            "heavy_items": u.heavy_items,
            "elevator_required": u.elevator_required,
            "parking_required": u.parking_required,
            "reference_no": str(u.source_id) if u.source_id else None,
        }
        for u in upcoming
    ]

    # ---------------------------
    # 3️⃣ Occupancy history
    # ---------------------------
    history = get_occupancy_timeline(db, auth_db, space_id)

    return {
        "current": current_occupancy,
        "upcoming": upcoming_list,
        "history": history
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
                SpaceOccupancy.status == OccupancyStatus.active
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
                        SpaceOccupancy.status == OccupancyStatus.active
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
            move_in_date=params.move_in_date,
            heavy_items=params.heavy_items,
            elevator_required=params.elevator_required,
            parking_required=params.parking_required,
            status=params.status,
            request_type=RequestType.move_in
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


def move_out(db: Session, params: MoveOutRequest):
    try:
        now = datetime.now(timezone.utc)
        occ = db.query(SpaceOccupancy).filter(
            SpaceOccupancy.space_id == params.space_id,
            SpaceOccupancy.status == "active"
        ).first()

        if not occ:
            return error_response(message="Space already vacant")

        occ.status = "moved_out"
        occ.move_out_date = func.now()

        db.query(Space).filter(
            Space.id == params.space_id,
        ).update({
            "status": "available"
        })

        # 3️⃣ Create handover record
        handover = SpaceHandover(
            occupancy_id=occ.id,
            handover_by=occ.occupant_user_id,
            keys_returned=params.keys_returned,
            accessories_returned=params.accessories_returned,
            damage_checked=params.damage_checked,
            remarks=params.remarks,
            status=HandoverStatus.completed
            if (
                params.keys_returned
                and params.damage_checked
                and params.accessories_returned
            )
            else HandoverStatus.pending
        )

        db.add(handover)

        if occ.occupant_type == OccupantType.tenant:
            # End active lease
            lease = db.query(Lease).filter(
                Lease.id == occ.lease_id,
                Lease.is_deleted == False,
                Lease.status == "active"
            ).first()

            if lease:
                lease.status = "terminated"   # or "terminated"
                lease.termination_date = now
                lease.end_date = now

            # End tenant-space mapping
            db.query(TenantSpace).join(
                Tenant, Tenant.id == TenantSpace.tenant_id, Tenant.is_deleted == False
            ).filter(
                TenantSpace.space_id == params.space_id,
                Tenant.user_id == occ.occupant_user_id,
                TenantSpace.is_deleted == False,
                TenantSpace.status == OwnershipStatus.leased
            ).update({
                "status": OwnershipStatus.ended,
                "updated_at": now
            })

        log_occupancy_event(
            db,
            space_id=params.space_id,
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

# APPROVAL PAGE


def get_space_occupancy_requests(
    db: Session,
    auth_db: Session,
    org_id: UUID,
    params: OccupancyApprovalRequest
):
    query = (
        db.query(
            SpaceOccupancy.id,
            SpaceOccupancy.request_type,
            SpaceOccupancy.space_id,
            Space.name.label("space_name"),
            Site.name.label("site_name"),
            Building.name.label("building_name"),
            SpaceOccupancy.occupant_name,
            SpaceOccupancy.occupant_type,
            SpaceOccupancy.created_at,
            SpaceOccupancy.move_in_date,
            SpaceOccupancy.move_out_date,
            SpaceOccupancy.status,
        )
        .join(Space, Space.id == SpaceOccupancy.space_id)
        .join(Building, Building.id == Space.building_id)
        .join(Site, Site.id == Building.site_id)
        .filter(
            Space.org_id == org_id,
            SpaceOccupancy.request_type.isnot_(None)
        )
    )

    if params.request_type is not None:
        query = query.filter(
            SpaceOccupancy.request_type == RequestType(params.request_type)
        )

    if params.search:
        query = query.filter(
            (Space.name.ilike(f"%{params.search}%"))
        )

    if params.status:
        query = query.filter(SpaceOccupancy.status ==
                             OccupancyStatus(params.status))

    total = query.count()

    rows = query.offset(params.skip).limit(params.limit).all()

    result = []

    user_ids = [r.occupant_user_id for r in rows]

    users = (
        auth_db.query(Users.id, Users.full_name)
        .filter(Users.id.in_(user_ids))
        .all()
    )
    user_map = {u.id: u.full_name for u in users}

    result = [
        SpaceOccupancyRequestOut(
            id=r.id,
            request_type=r.request_type.value,
            space_id=r.space_id,
            space_name=r.space_name,
            site_name=r.site_name,
            building_name=r.building_name,
            occupant_name=user_map.get(r.occupant_user_id),
            occupant_type=r.occupant_type.value,
            requested_at=r.created_at,
            move_in_date=r.move_in_date,
            move_out_date=r.move_out_date,
            status=r.status.value,
        )
        for r in rows
    ]

    return {"requests": result, "total": total}


def approve_move_in(db: Session, move_in_id: UUID):
    move_in_request = db.query(SpaceOccupancy).filter(
        SpaceOccupancy.id == move_in_id,
        SpaceOccupancy.status == OccupancyStatus.pending,
        SpaceOccupancy.request_type == RequestType.move_in
    ).first()

    if not move_in_request:
        raise Exception("Move-in request not found or already processed")

    # Activate move-in
    move_in_request.status = OccupancyStatus.active
    db.commit()
    db.refresh(move_in_request)
    return move_in_request


def reject_move_in(db: Session, move_in_id: UUID):
    move_in_request = db.query(SpaceOccupancy).filter(
        SpaceOccupancy.id == move_in_id,
        SpaceOccupancy.status == OccupancyStatus.pending,
        SpaceOccupancy.request_type == RequestType.move_in
    ).first()

    if not move_in_request:
        raise Exception("Move-in request not found or already processed")

    move_in_request.status = OccupancyStatus.rejected
    db.commit()
    db.refresh(move_in_request)
    return move_in_request


def request_move_out(
    db: Session,
    user_id: UUID,
    params: SpaceMoveOutRequest
):

    # -------------------------------------------------
    # 1️⃣ Find ACTIVE occupancy automatically
    # -------------------------------------------------
    move_in = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.space_id == params.space_id,
            SpaceOccupancy.occupant_user_id == user_id,
            SpaceOccupancy.status == OccupancyStatus.active,
            SpaceOccupancy.request_type == RequestType.move_in
        )
        .first()
    )

    if not move_in:
        raise Exception("Active occupancy not found")

    # -------------------------------------------------
    # 2️⃣ Prevent duplicate move-out requests
    # -------------------------------------------------
    existing_request = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.original_occupancy_id == params.move_in.id,
            SpaceOccupancy.request_type == RequestType.move_out,
            SpaceOccupancy.status == OccupancyStatus.pending
        )
        .first()
    )

    if existing_request:
        raise Exception("Move-out already requested")

    # -------------------------------------------------
    # 3️⃣ Create move-out request
    # -------------------------------------------------
    move_out_request = SpaceOccupancy(
        space_id=move_in.space_id,
        occupant_user_id=move_in.occupant_user_id,
        occupant_type=move_in.occupant_type,
        source_id=move_in.source_id,
        lease_id=move_in.lease_id,

        request_type=RequestType.move_out,
        status=OccupancyStatus.pending,

        move_in_date=move_in.move_in_date,
        move_out_date=params.move_out_date,

        heavy_items=move_in.heavy_items,
        elevator_required=move_in.elevator_required,
        parking_required=move_in.parking_required,
        time_slot=move_in.time_slot,

        original_occupancy_id=move_in.id
    )

    db.add(move_out_request)
    db.commit()
    db.refresh(move_out_request)

    return move_out_request


def reject_move_out(db: Session, move_out_id: UUID):
    move_out_request = db.query(SpaceOccupancy).filter(
        SpaceOccupancy.id == move_out_id,
        SpaceOccupancy.status == OccupancyStatus.pending,
        SpaceOccupancy.request_type == RequestType.move_out
    ).first()

    if not move_out_request:
        raise Exception("Move-out request not found or already processed")

    move_out_request.status = OccupancyStatus.rejected
    db.commit()
    db.refresh(move_out_request)
    return move_out_request


def approve_move_out(db: Session, move_out_id: UUID, admin_user_id: UUID):
    move_out = db.query(SpaceOccupancy).filter(
        SpaceOccupancy.id == move_out_id,
        SpaceOccupancy.status == OccupancyStatus.pending,
        SpaceOccupancy.request_type == RequestType.move_out
    ).first()
    if not move_out:
        raise Exception("Move-out request not found")

    move_out.status = OccupancyStatus.active  # approved
    db.commit()

    # If move-out date <= today, create handover
    if move_out.move_out_date and move_out.move_out_date <= date.today():
        handover = SpaceHandover(
            occupancy_id=move_out.id,
            handover_date=datetime.now(),
            handover_by_user_id=move_out.occupant_user_id,
            handover_to_user_id=admin_user_id
        )
        db.add(handover)
        db.commit()
        db.refresh(handover)
        return handover
    return move_out


def complete_handover(
    db: Session,
    handover_id: UUID,
    keys_returned=False,
    accessories_returned=False,
    damage_checked=False,
    remarks: str | None = None
):

    handover = db.query(SpaceHandover).filter(
        SpaceHandover.id == handover_id).first()
    if not handover:
        raise Exception("Handover not found")

    handover.keys_returned = keys_returned
    handover.accessories_returned = accessories_returned
    handover.damage_checked = damage_checked
    handover.remarks = remarks
    db.commit()

    # Update original move-in record to moved_out
    move_out = db.query(SpaceOccupancy).filter(
        SpaceOccupancy.id == handover.occupancy_id).first()
    if move_out:
        original_move_in = db.query(SpaceOccupancy).filter(
            SpaceOccupancy.id == move_out.original_occupancy_id
        ).first()
        if original_move_in:
            original_move_in.status = OccupancyStatus.moved_out
            db.commit()
    return handover


def validate_space_available_for_assignment(db: Session, space_id: UUID):

    last_occupancy = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.space_id == space_id,
            SpaceOccupancy.status == OccupancyStatus.moved_out
        )
        .order_by(SpaceOccupancy.updated_at.desc())
        .first()
    )

    if not last_occupancy:
        return True

    handover = (
        db.query(SpaceHandover)
        .filter(SpaceHandover.occupancy_id == last_occupancy.id)
        .first()
    )

    if not handover or handover.status != HandoverStatus.completed:
        raise HTTPException(
            status_code=400,
            detail="Handover process not completed. Space cannot be assigned."
        )

    return True


def has_pending_moveout_request(db: Session, occupancy_id: UUID):

    return db.query(SpaceOccupancy).filter(
        SpaceOccupancy.original_occupancy_id == occupancy_id,
        SpaceOccupancy.request_type == RequestType.move_out,
        SpaceOccupancy.status.in_([
            OccupancyStatus.pending,
            OccupancyStatus.active
        ])
    ).first() is not None
