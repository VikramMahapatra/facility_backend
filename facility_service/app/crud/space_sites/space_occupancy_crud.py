# services/space_occupancy_service.py
from datetime import datetime, time, timezone, date
import shutil
from typing import List
import uuid
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile, status
from uuid import UUID

from facility_service.app.models.leasing_tenants.leases import Lease
from facility_service.app.models.space_sites.buildings import Building
from facility_service.app.models.space_sites.sites import Site
from facility_service.app.models.space_sites.space_handover import HandoverStatus, SpaceHandover
from facility_service.app.models.space_sites.space_inspections import SpaceInspection, SpaceInspectionImage, SpaceInspectionItem
from shared.core.schemas import UserToken
from shared.utils.app_status_code import AppStatusCode
from shared.utils.enums import OwnershipStatus, UserAccountType

from ...models.space_sites.space_occupancy_events import OccupancyEventType, SpaceOccupancyEvent
from ...models.space_sites.spaces import Space
from shared.helpers.json_response_helper import error_response, success_response

from ...schemas.space_sites.space_occupany_schemas import HandoverCreate, InspectionComplete, InspectionItemCreate, MoveInRequest, MoveOutRequest, OccupancyApprovalRequest, SpaceMoveOutRequest, SpaceOccupancyRequestOut
from shared.models.users import Users

from ...models.leasing_tenants.tenant_spaces import TenantSpace
from ...models.leasing_tenants.tenants import Tenant
from ...models.space_sites.space_occupancies import OccupancyStatus, OccupantType, RequestType, SpaceOccupancy
from ...models.space_sites.space_owners import SpaceOwner
from datetime import date
from sqlalchemy import or_


def get_current_occupancy(db: Session, auth_db: Session, space_id: UUID):
    today = date.today()

    # --------------------------------------------------
    # 1️⃣ Get latest move-in (current or past)
    # --------------------------------------------------
    occ = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.space_id == space_id,
            SpaceOccupancy.request_type == RequestType.move_in,
            SpaceOccupancy.status == OccupancyStatus.active
        )
        .order_by(SpaceOccupancy.move_in_date.desc())
        .first()
    )

    if not occ:
        current_occupancy = {
            "status": "vacant",
            "can_request_move_in": True,
            "can_request_move_out": False
        }
    else:
        move_out = (
            db.query(SpaceOccupancy)
            .filter(
                SpaceOccupancy.space_id == space_id,
                SpaceOccupancy.request_type == RequestType.move_out,
                SpaceOccupancy.status.in_(
                    [OccupancyStatus.scheduled, OccupancyStatus.active]
                )
            )
            .order_by(SpaceOccupancy.move_out_date.desc())
            .first()
        )

        # Latest handover
        handover = (
            db.query(SpaceHandover)
            .filter(SpaceHandover.occupancy_id == move_out.id)
            .order_by(SpaceHandover.handover_date.desc())
            .first()
        )

        handover_completed = (
            handover and handover.status == HandoverStatus.completed
        )

        # --------------------------------------------------
        # STATUS ENGINE
        # --------------------------------------------------

        if not move_out:
            status = "occupied"

        elif move_out.move_out_date > today:
            status = "move_out_scheduled"

        elif not handover_completed:
            status = "handover_awaited"

        else:
            status = "recently_vacated"

        # --------------------------------------------------
        # Build response
        # --------------------------------------------------

        current_occupancy = {
            "status": status,
            "occupant_type": occ.occupant_type,
            "occupant_name": get_user_name(auth_db, occ.occupant_user_id),
            "move_in_date": occ.move_in_date,
            "move_out_date": move_out.move_out_date if move_out else None,
            "time_slot": occ.time_slot,
        }

        # Handover details
        if handover:
            current_occupancy["handover"] = {
                "handover_date": handover.handover_date,
                "handover_by": get_user_name(auth_db, handover.handover_by_user_id),
                "handover_to": get_user_name(auth_db, handover.handover_to_user_id)
                if handover.handover_to_user_id else None,
                "condition_notes": handover.remarks,
                "status": handover.status,
                "keys_returned": handover.keys_returned,
                "inspection_completed": handover.inspection_completed,
                "accessories_returned": handover.accessories_returned,
            }

        # --------------------------------------------------
        # Action permissions
        # --------------------------------------------------

        existing_move_in_request = db.query(SpaceOccupancy).filter(
            SpaceOccupancy.space_id == space_id,
            SpaceOccupancy.request_type == RequestType.move_in,
            SpaceOccupancy.status.in_(
                [OccupancyStatus.pending, OccupancyStatus.active]
            )
        ).first()

        existing_move_out_request = db.query(SpaceOccupancy).filter(
            SpaceOccupancy.space_id == space_id,
            SpaceOccupancy.request_type == RequestType.move_out,
            SpaceOccupancy.status.in_(
                [OccupancyStatus.pending, OccupancyStatus.active]
            )
        ).first()

        current_occupancy["can_request_move_in"] = (
            existing_move_in_request is None
            or status in ["vacant", "recently_vacated"]
        )

        current_occupancy["can_request_move_out"] = (
            status == "occupied"
            and existing_move_out_request is None
        )

    # --------------------------------------------------
    # 2️⃣ Upcoming move-ins
    # --------------------------------------------------

    upcoming = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.space_id == space_id,
            SpaceOccupancy.request_type == RequestType.move_in,
            SpaceOccupancy.status == OccupancyStatus.active,
            SpaceOccupancy.move_in_date > today
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

    # --------------------------------------------------
    # 3️⃣ History
    # --------------------------------------------------

    history = get_occupancy_timeline(db, auth_db, space_id)

    return {
        "current": current_occupancy,
        "upcoming": upcoming_list,
        "history": history
    }


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


def move_in(
    db: Session,
    current_user: UserToken,
    params: MoveInRequest
):
    try:
        # Check if space already occupied
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

        if current_user.account_type != UserAccountType.ORGANIZATION.value:
            params.occupant_user_id = current_user.id

        if params.occupant_type == "tenant":
            if not params.tenant_id:
                params.tenant_id = (
                    db.query(Tenant.id)
                    .filter(
                        Tenant.user_id == current_user.user_id,
                        SpaceOccupancy.status == OccupancyStatus.active
                    )
                    .first()
                )

            if params.tenant_id and not params.lease_id:
                lease = (
                    db.query(Lease.id)
                    .filter(
                        Lease.space_id == params.space_id,
                        Lease.tenant_id == params.tenant_id,
                        Lease.status == "active",
                        Lease.is_deleted == False
                    )
                    .first()
                )
                params.lease_id = lease.id

                if lease.start_date:
                    if params.move_in_date < lease.start_date:
                        return error_response(
                            message=f"Move-in date must be on or after lease start date ({lease.end_date})"
                        )
                    if params.move_in_date.date() > lease.end_date:
                        return error_response(
                            message=f"Move-in date cannot exceed lease end date({lease.end_date})"
                        )

        # Create occupancy
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
            request_type=RequestType.move_in,
            status=OccupancyStatus.pending
        )

        db.add(occ)

        log_occupancy_event(
            db,
            space_id=params.space_id,
            event_type=OccupancyEventType.moved_in_requested,
            occupant_type=params.occupant_type,
            occupant_user_id=params.occupant_user_id,
            source_id=params.tenant_id,
            lease_id=params.lease_id
        )

        db.commit()
        db.refresh(occ)

        if current_user.account_type == UserAccountType.ORGANIZATION.value:
            approve_move_in(db, occ.id)

        return occ
    except Exception as e:
        db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def approve_move_in(db: Session, move_in_id: UUID):
    today = datetime.combine(date.today(), time.min)
    move_in_request = db.query(SpaceOccupancy).filter(
        SpaceOccupancy.id == move_in_id,
        SpaceOccupancy.status == OccupancyStatus.pending,
        SpaceOccupancy.request_type == RequestType.move_in
    ).first()

    if not move_in_request:
        raise Exception("Move-in request not found or already processed")

    if move_in_request.move_in_date <= today:
        occ_status = OccupancyStatus.active
        occ_event = OccupancyEventType.moved_in
    else:
        occ_status = OccupancyStatus.scheduled
        occ_event = OccupancyEventType.moved_in_scheduled

    # Activate move-in
    move_in_request.status = occ_status
    db.commit()
    db.refresh(move_in_request)

    log_occupancy_event(
        db,
        space_id=move_in_request.space_id,
        event_type=occ_event,
        occupant_type=move_in_request.occupant_type,
        occupant_user_id=move_in_request.occupant_user_id,
        source_id=move_in_request.source_id,
        lease_id=move_in_request.lease_id
    )

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

    log_occupancy_event(
        db,
        space_id=move_in_request.space_id,
        event_type=OccupancyEventType.moved_in_rejected,
        occupant_type=move_in_request.occupant_type,
        occupant_user_id=move_in_request.occupant_user_id,
        source_id=move_in_request.source_id,
        lease_id=move_in_request.lease_id
    )

    return move_in_request


def request_move_out(
    db: Session,
    current_user: UserToken,
    params: SpaceMoveOutRequest
):
    # -------------------------------------------------
    # Find ACTIVE occupancy automatically
    # -------------------------------------------------
    move_in = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.space_id == params.space_id,
            SpaceOccupancy.status == OccupancyStatus.active,
            SpaceOccupancy.request_type == RequestType.move_in
        )
        .first()
    )

    if not move_in:
        return error_response(message="Active occupancy not found")

    # -------------------------------------------------
    #  Prevent duplicate move-out requests
    # -------------------------------------------------
    existing_request = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.original_occupancy_id == move_in.id,
            SpaceOccupancy.request_type == RequestType.move_out,
            SpaceOccupancy.status == OccupancyStatus.pending
        )
        .first()
    )

    if existing_request:
        return error_response(message="Move-out already requested")

    # validate lease end date
    lease = None
    if move_in.lease_id:
        lease = (
            db.query(Lease)
            .filter(
                Lease.id == move_in.lease_id,
                Lease.is_deleted == False
            )
            .first()
        )

    if lease and lease.end_date:
        if params.move_out_date.date() > lease.end_date:
            return error_response(
                message=f"Move-out date cannot exceed lease end date({lease.end_date})"
            )
        elif params.move_out_date.date() < lease.start_date:
            return error_response(
                message=f"Move-out date cannot be before lease start date({lease.start_date})"
            )

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

    log_occupancy_event(
        db,
        space_id=move_out_request.space_id,
        event_type=OccupancyEventType.moved_out_requested,
        occupant_type=move_out_request.occupant_type,
        occupant_user_id=move_out_request.occupant_user_id,
        source_id=move_out_request.source_id,
        lease_id=move_out_request.lease_id
    )

    if current_user.account_type == UserAccountType.ORGANIZATION.value:
        approve_move_out(db, move_out_request.id)

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

    log_occupancy_event(
        db,
        space_id=move_out_request.space_id,
        event_type=OccupancyEventType.moved_out_rejected,
        occupant_type=move_out_request.occupant_type,
        occupant_user_id=move_out_request.occupant_user_id,
        source_id=move_out_request.source_id,
        lease_id=move_out_request.lease_id
    )

    return move_out_request


def approve_move_out(db: Session, move_out_id: UUID, admin_user_id: UUID):
    today = datetime.combine(date.today(), time.min)
    move_out = db.query(SpaceOccupancy).filter(
        SpaceOccupancy.id == move_out_id,
        SpaceOccupancy.status == OccupancyStatus.pending,
        SpaceOccupancy.request_type == RequestType.move_out
    ).first()
    if not move_out:
        raise Exception("Move-out request not found")

    if move_out.move_out_date <= today:
        occ_status = OccupancyStatus.active
        occ_event = OccupancyEventType.moved_out
    else:
        occ_status = OccupancyStatus.scheduled
        occ_event = OccupancyEventType.moved_out_scheduled

    move_out.status = occ_status
    db.commit()

    log_occupancy_event(
        db,
        space_id=move_out.space_id,
        event_type=occ_event,
        occupant_type=move_out.occupant_type,
        occupant_user_id=move_out.occupant_user_id,
        source_id=move_out.source_id,
        lease_id=move_out.lease_id
    )

    # If move-out date <= today, create handover
    if move_out.move_out_date and move_out.move_out_date <= date.today():
        start_handover_process(db, move_out, admin_user_id)
    return move_out


def start_handover_process(db: Session, move_out, admin_user_id):
    handover = SpaceHandover(
        occupancy_id=move_out.id,
        handover_by_user_id=move_out.occupant_user_id,
        handover_to_user_id=admin_user_id
    )

    db.add(handover)
    db.commit()
    db.refresh(handover)

    inspection = SpaceInspection(
        occupancy_id=move_out.id,
        handover_id=handover.id,
        status="pending"
    )

    db.add(inspection)
    db.commit()

    return handover


def complete_handover(
    db: Session,
    handover_id: UUID,
):
    handover = db.query(SpaceHandover).filter(
        SpaceHandover.id == handover_id).first()
    if not handover:
        raise Exception("Handover not found")

    if not handover:
        raise HTTPException(404, "Handover not found")

    if not handover.inspection_completed:
        raise HTTPException(400, "Inspection required")

    if not handover.keys_returned:
        raise HTTPException(400, "Keys not returned")

    if not handover.accessories_returned:
        raise HTTPException(400, "Accessories not returned")

    handover.status = HandoverStatus.completed
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


def get_inspection(db: Session, inspection_id: UUID):
    inspection = db.query(SpaceInspection).filter(
        SpaceInspection.id == inspection_id
    ).first()

    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    return inspection


def add_inspection_items(
    db: Session,
    inspection_id: UUID,
    items: List[InspectionItemCreate],

):
    for item in items:
        db.add(SpaceInspectionItem(
            inspection_id=inspection_id,
            item_name=item.item_name,
            condition=item.condition,
            remarks=item.remarks
        ))

    db.commit()

    return {"message": "Inspection items saved"}


def upload_inspection_image(
    db: Session,
    inspection_id: UUID,
    file: UploadFile,
    current_user: UserToken
):
    file_location = f"uploads/inspections/{uuid.uuid4()}_{file.filename}"

    with open(file_location, "wb") as f:
        shutil.copyfileobj(file.file, f)

    image = SpaceInspectionImage(
        inspection_id=inspection_id,
        image_url=file_location,
        uploaded_by=current_user.user_id
    )

    db.add(image)
    db.commit()

    return {"image_url": file_location}


def complete_inspection(
    db: Session,
    inspection_id: UUID,
    payload: InspectionComplete,
    current_user: UserToken
):
    inspection = db.query(SpaceInspection).filter(
        SpaceInspection.id == inspection_id
    ).first()

    if not inspection:
        raise HTTPException(404, "Inspection not found")

    inspection.walls_condition = payload.walls_condition
    inspection.flooring_condition = payload.flooring_condition
    inspection.electrical_condition = payload.electrical_condition
    inspection.plumbing_condition = payload.plumbing_condition
    inspection.damage_found = payload.damage_found
    inspection.damage_notes = payload.damage_notes

    handover = db.query(SpaceHandover).filter(
        SpaceHandover.id == inspection.handover_id
    ).first()

    if not handover:
        raise HTTPException(404, "Handover not found")

    # -------------------------
    # Mark inspection completed
    # -------------------------
    handover.inspection_completed = True

    # If admin performing inspection
    if not handover.handover_to_user_id:
        handover.handover_to_user_id = current_user.user_id

    # -------------------------
    # Check if handover complete
    # -------------------------
    if (
        handover.inspection_completed
        and handover.keys_returned
        and handover.accessories_returned
    ):
        complete_handover(db, handover.id)

    db.commit()

    return {
        "message": "Inspection completed",
        "handover_status": handover.status
    }


def update_handover_checklist(db: Session, occupancy_id: UUID, item: str):
    handover = db.query(SpaceHandover).filter(
        SpaceHandover.occupancy_id == occupancy_id
    ).first()

    if not handover:
        raise HTTPException(status_code=404, detail="Handover not found")

    if item == "keys":
        handover.keys_returned = True
    elif item == "accesories":
        handover.accessories_returned = True
    db.commit()

    return {"message": "Keys returned"}


# VALIDATION METHODS

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
