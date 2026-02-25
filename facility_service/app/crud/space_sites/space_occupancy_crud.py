# services/space_occupancy_service.py
from datetime import datetime, time, timezone, date
import shutil
from typing import List, Optional
import uuid
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile, status
from uuid import UUID

from facility_service.app.models.leasing_tenants.leases import Lease
from facility_service.app.models.space_sites.buildings import Building
from facility_service.app.models.space_sites.sites import Site
from facility_service.app.models.space_sites.space_handover import HandoverStatus, SpaceHandover
from facility_service.app.models.space_sites.space_inspections import InspectionStatus, SpaceInspection, SpaceInspectionImage, SpaceInspectionItem
from facility_service.app.models.space_sites.space_maintenances import SpaceMaintenance
from facility_service.app.models.space_sites.space_settlements import SpaceSettlement
from shared.core.schemas import UserToken
from shared.helpers.user_helper import get_user_name
from shared.utils.app_status_code import AppStatusCode
from shared.utils.enums import OwnershipStatus, UserAccountType

from ...models.space_sites.space_occupancy_events import OccupancyEventType, SpaceOccupancyEvent
from ...models.space_sites.spaces import Space
from shared.helpers.json_response_helper import error_response, success_response

from ...schemas.space_sites.space_occupany_schemas import HandoverCreate, HandoverUpdateSchema, InspectionComplete, InspectionItemCreate, InspectionRequest, MaintenanceComplete, MaintenanceRequest, MoveInRequest, MoveOutRequest, OccupancyApprovalRequest, SettlementComplete, SettlementRequest, SpaceMoveOutRequest, SpaceOccupancyRequestOut
from shared.models.users import Users

from ...models.leasing_tenants.tenant_spaces import TenantSpace
from ...models.leasing_tenants.tenants import Tenant
from ...models.space_sites.space_occupancies import OccupancyStatus, OccupantType, RequestType, SpaceOccupancy
from ...models.space_sites.space_owners import SpaceOwner
from datetime import date
from sqlalchemy import or_


def get_current_occupancy(db: Session, space_id: UUID):
    today = date.today()

    # --------------------------------------------------
    # 1️⃣ Get active occupancy
    # --------------------------------------------------
    occ = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.space_id == space_id,
            SpaceOccupancy.request_type == RequestType.move_in,
            SpaceOccupancy.status.in_(
                [OccupancyStatus.moved_out, OccupancyStatus.active]
            )
        )
        .order_by(SpaceOccupancy.move_in_date.desc())
        .first()
    )

    if not occ:
        return {
            "current": {
                "status": "vacant",
                "can_request_move_in": True,
                "can_request_move_out": False
            }
        }

    # --------------------------------------------------
    # Move-out request
    # --------------------------------------------------
    move_out = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.space_id == space_id,
            SpaceOccupancy.request_type == RequestType.move_out,
            SpaceOccupancy.status.notin_(
                [OccupancyStatus.rejected, OccupancyStatus.pending]
            )
        )
        .order_by(SpaceOccupancy.move_out_date.desc())
        .first()
    )

    # --------------------------------------------------
    # Handover
    # --------------------------------------------------
    handover = None
    if move_out:
        handover = (
            db.query(SpaceHandover)
            .filter(SpaceHandover.occupancy_id == move_out.id)
            .order_by(SpaceHandover.created_at.desc())
            .first()
        )

    # --------------------------------------------------
    # Inspection
    # --------------------------------------------------
    inspection = None
    if handover:
        inspection = (
            db.query(SpaceInspection)
            .filter(SpaceInspection.handover_id == handover.id)
            .order_by(SpaceInspection.created_at.desc())
            .first()
        )

    # --------------------------------------------------
    # Maintenance
    # --------------------------------------------------
    maintenance = None
    if inspection:
        maintenance = (
            db.query(SpaceMaintenance)
            .filter(SpaceMaintenance.inspection_id == inspection.id)
            .order_by(SpaceMaintenance.created_at.desc())
            .first()
        )

    # --------------------------------------------------
    # Settlement
    # --------------------------------------------------
    settlement = None
    if maintenance:
        settlement = (
            db.query(SpaceSettlement)
            .filter(SpaceSettlement.occupancy_id == move_out.id)
            .order_by(SpaceSettlement.created_at.desc())
            .first()
        )

    # --------------------------------------------------
    # STATUS ENGINE
    # --------------------------------------------------
    if not move_out:
        status = "occupied"
    elif move_out.move_out_date and move_out.move_out_date > today:
        status = "move_out_scheduled"
    elif not handover:
        status = "handover_pending"
    elif handover.status != HandoverStatus.completed:
        status = "handover_in_progress"
    elif not inspection:
        status = "inspection_pending"
    elif inspection.status != InspectionStatus.completed:
        status = "inspection_scheduled"
    elif not maintenance or (maintenance and not maintenance.completed):
        status = "maintenance_pending"
    elif not settlement or (settlement and not settlement.settled):
        status = "settlement_pending"
    elif settlement and settlement.settled:
        status = "completed"
    else:
        status = "recently_vacated"

    # --------------------------------------------------
    # Build response
    # --------------------------------------------------
    current_occupancy = {
        "id": occ.id,
        "move_out_id": move_out.id if move_out else None,
        "status": status,
        "occupant_type": occ.occupant_type,
        "occupant_name": get_user_name(occ.occupant_user_id),
        "move_in_date": occ.move_in_date,
        "move_out_date": move_out.move_out_date if move_out else None,
        "time_slot": occ.time_slot,
    }

    # --------------------------------------------------
    # Handover Details (Updated)
    # --------------------------------------------------
    if handover:
        current_occupancy["handover"] = {
            "id": handover.id,
            "occupancy_id": handover.occupancy_id,
            "handover_date": handover.handover_date,
            "handover_by": get_user_name(handover.handover_by_user_id),
            "handover_to_person": handover.handover_to_person,
            "handover_to_contact": handover.handover_to_contact,
            "remarks": handover.remarks,
            "status": handover.status,
            "keys_returned": handover.keys_returned,
            "number_of_keys": handover.number_of_keys,
            "accessories_returned": handover.accessories_returned,
            "access_card_returned": handover.access_card_returned,
            "number_of_access_cards": handover.number_of_access_cards,
            "parking_card_returned": handover.parking_card_returned,
            "number_of_parking_cards": handover.number_of_parking_cards,
        }

    # --------------------------------------------------
    # Inspection Details
    # --------------------------------------------------
    if inspection:
        current_occupancy["inspection"] = {
            "id": inspection.id,
            "status": inspection.status,
            "scheduled_date": inspection.scheduled_date,
            "inspection_date": inspection.inspection_date,
            "inspected_by_user_name": get_user_name(inspection.inspected_by_user_id),
            "damage_found": inspection.damage_found,
            "damage_notes": inspection.damage_notes,
            "walls_condition": inspection.walls_condition,
            "flooring_condition": inspection.flooring_condition,
            "electrical_condition": inspection.electrical_condition,
            "plumbing_condition": inspection.plumbing_condition
        }

    # --------------------------------------------------
    # Maintenance Details
    # --------------------------------------------------
    if maintenance:
        current_occupancy["maintenance"] = {
            "id": maintenance.id,
            "maintenance_required": maintenance.maintenance_required,
            "notes": maintenance.notes,
            "completed": maintenance.completed,
            "completed_at": maintenance.completed_at,
            "completed_by_name": get_user_name(maintenance.completed_by),
            "created_at": maintenance.created_at,
        }

    # --------------------------------------------------
    # Settlement Details
    # --------------------------------------------------
    if settlement:
        current_occupancy["settlement"] = {
            "id": settlement.id,
            "final_amount": settlement.final_amount,
            "settled": settlement.settled,
            "settled_at": settlement.settled_at,
            "damage_charges": settlement.damage_charges,
            "pending_dues": settlement.pending_dues,
        }

    # --------------------------------------------------
    # Permissions
    # --------------------------------------------------
    existing_move_in_request = db.query(SpaceOccupancy).filter(
        SpaceOccupancy.space_id == space_id,
        SpaceOccupancy.request_type == RequestType.move_in,
        SpaceOccupancy.status.in_(
            [OccupancyStatus.pending, OccupancyStatus.active])
    ).first()

    existing_move_out_request = db.query(SpaceOccupancy).filter(
        SpaceOccupancy.space_id == space_id,
        SpaceOccupancy.request_type == RequestType.move_out,
        SpaceOccupancy.status.in_(
            [OccupancyStatus.pending, OccupancyStatus.active])
    ).first()

    current_occupancy["can_request_move_in"] = (
        existing_move_in_request is None and status in [
            "recently_vacated", "completed"]
    )

    current_occupancy["can_request_move_out"] = (
        status == "occupied" and existing_move_out_request is None
    )

    return {
        "current": current_occupancy
    }


def get_current_occupancy_bulk(db: Session, auth_db: Session, space_ids: list[UUID]):
    today = date.today()
    result = {}

    if not space_ids:
        return result

    # --------------------------------------------------
    # 1️⃣ Latest active move-in per space
    # --------------------------------------------------
    move_ins = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.space_id.in_(space_ids),
            SpaceOccupancy.request_type == RequestType.move_in,
            SpaceOccupancy.status == OccupancyStatus.active
        )
        .order_by(SpaceOccupancy.space_id, SpaceOccupancy.move_in_date.desc())
        .all()
    )

    latest_move_in = {}
    for occ in move_ins:
        if occ.space_id not in latest_move_in:
            latest_move_in[occ.space_id] = occ

    # --------------------------------------------------
    # 2️⃣ Move-outs
    # --------------------------------------------------
    move_outs = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.space_id.in_(space_ids),
            SpaceOccupancy.request_type == RequestType.move_out,
            SpaceOccupancy.status.in_(
                [OccupancyStatus.pending, OccupancyStatus.scheduled, OccupancyStatus.active])
        )
        .order_by(SpaceOccupancy.space_id, SpaceOccupancy.move_out_date.desc())
        .all()
    )

    latest_move_out = {}
    for occ in move_outs:
        if occ.space_id not in latest_move_out:
            latest_move_out[occ.space_id] = occ

    # --------------------------------------------------
    # 3️⃣ Handovers
    # --------------------------------------------------
    occupancy_ids = [m.id for m in latest_move_out.values()]
    handovers = (
        db.query(SpaceHandover)
        .filter(SpaceHandover.occupancy_id.in_(occupancy_ids))
        .order_by(SpaceHandover.occupancy_id, SpaceHandover.created_at.desc())
        .all()
    )

    latest_handover = {}
    for h in handovers:
        if h.occupancy_id not in latest_handover:
            latest_handover[h.occupancy_id] = h

    # --------------------------------------------------
    # 4️⃣ Inspections
    # --------------------------------------------------
    handover_ids = [h.id for h in latest_handover.values()]
    inspections = (
        db.query(SpaceInspection)
        .filter(SpaceInspection.handover_id.in_(handover_ids))
        .order_by(SpaceInspection.handover_id, SpaceInspection.created_at.desc())
        .all()
    )

    latest_inspection = {}
    for i in inspections:
        if i.handover_id not in latest_inspection:
            latest_inspection[i.handover_id] = i

    # --------------------------------------------------
    # 5️⃣ Maintenance
    # --------------------------------------------------
    inspection_ids = [i.id for i in latest_inspection.values()]
    maintenances = (
        db.query(SpaceMaintenance)
        .filter(SpaceMaintenance.inspection_id.in_(inspection_ids))
        .order_by(SpaceMaintenance.inspection_id, SpaceMaintenance.created_at.desc())
        .all()
    )

    latest_maintenance = {}
    for m in maintenances:
        if m.inspection_id not in latest_maintenance:
            latest_maintenance[m.inspection_id] = m

    # --------------------------------------------------
    # 6️⃣ Settlements
    # --------------------------------------------------
    occupancy_ids_for_settlement = [occ.id for occ in latest_move_in.values()]
    settlements = (
        db.query(SpaceSettlement)
        .filter(SpaceSettlement.occupancy_id.in_(occupancy_ids_for_settlement))
        .order_by(SpaceSettlement.occupancy_id, SpaceSettlement.created_at.desc())
        .all()
    )

    latest_settlement = {}
    for s in settlements:
        if s.occupancy_id not in latest_settlement:
            latest_settlement[s.occupancy_id] = s

    # --------------------------------------------------
    # 7️⃣ Existing requests
    # --------------------------------------------------
    existing_move_ins = {
        r.space_id
        for r in db.query(SpaceOccupancy.space_id)
        .filter(
            SpaceOccupancy.space_id.in_(space_ids),
            SpaceOccupancy.request_type == RequestType.move_in,
            SpaceOccupancy.status.in_(
                [OccupancyStatus.pending, OccupancyStatus.active])
        )
    }

    existing_move_outs = {
        r.space_id
        for r in db.query(SpaceOccupancy.space_id)
        .filter(
            SpaceOccupancy.space_id.in_(space_ids),
            SpaceOccupancy.request_type == RequestType.move_out,
            SpaceOccupancy.status.in_(
                [OccupancyStatus.pending, OccupancyStatus.active])
        )
    }

    # --------------------------------------------------
    # 8️⃣ Build response per space
    # --------------------------------------------------
    for space_id in space_ids:
        occ = latest_move_in.get(space_id)
        move_out = latest_move_out.get(space_id)
        handover = latest_handover.get(move_out.id) if move_out else None
        inspection = latest_inspection.get(handover.id) if handover else None
        maintenance = latest_maintenance.get(
            inspection.id) if inspection else None
        settlement = latest_settlement.get(space_id)

        # Determine status
        if not occ:
            status = "vacant"
        elif not move_out:
            status = "occupied"
        elif move_out.move_out_date and move_out.move_out_date > today:
            status = "move_out_scheduled"
        elif not handover:
            status = "handover_pending"
        elif handover.status != HandoverStatus.completed:
            status = "handover_in_progress"
        elif not inspection:
            status = "inspection_pending"
        elif inspection.status != InspectionStatus.completed:
            status = "inspection_scheduled"
        elif maintenance and not maintenance.completed:
            status = "maintenance_pending"
        elif settlement and not settlement.settled:
            status = "settlement_pending"
        elif settlement and settlement.settled:
            status = "completed"
        else:
            status = "recently_vacated"

        # Build result
        result[space_id] = {
            "status": status,
            "can_request_move_in": space_id not in existing_move_ins or status in ["vacant", "completed"],
            "can_request_move_out": status == "occupied" and space_id not in existing_move_outs,
        }

    return result


def get_occupancy_history(db: Session, space_id: UUID):
    move_ins = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.space_id == space_id,
            SpaceOccupancy.request_type == RequestType.move_in
        )
        .order_by(SpaceOccupancy.created_at.desc())
        .all()
    )

    results = []

    for move_in in move_ins:
        move_out = (
            db.query(SpaceOccupancy)
            .filter(
                SpaceOccupancy.original_occupancy_id == move_in.id,
                SpaceOccupancy.request_type == RequestType.move_out
            )
            .first()
        )

        handover = None
        inspection = None
        maintenance = None
        settlement = None

        if move_out:
            handover = (
                db.query(SpaceHandover)
                .filter(SpaceHandover.occupancy_id == move_out.id)
                .first()
            )

            if handover:
                inspection = (
                    db.query(SpaceInspection)
                    .filter(SpaceInspection.handover_id == handover.id)
                    .first()
                )

            if inspection:
                maintenance = (
                    db.query(SpaceMaintenance)
                    .filter(SpaceMaintenance.inspection_id == inspection.id)
                    .first()
                )

            settlement = (
                db.query(SpaceSettlement)
                .filter(SpaceSettlement.occupancy_id == move_out.id)
                .first()
            )

        results.append({
            "occupancy_id": str(move_in.id),

            "occupant_name": get_user_name(move_in.occupant_user_id),
            "occupant_type": move_in.occupant_type,

            "move_in_date": move_in.move_in_date,
            "move_out_date": move_out.move_out_date if move_out else None,
            "status": move_out.status if move_out else move_in.status,

            "time_slot": move_in.time_slot,
            # or your actual reference field
            "reference_no": str(move_in.id)[:8],

            "handover": {
                "status": handover.status,
                "handover_date": handover.handover_date,
                "keys_returned": handover.keys_returned,
                "accessories_returned": handover.accessories_returned,
                "remarks": handover.remarks,
            } if handover else None,

            "inspection": {
                "status": inspection.status,
                "inspection_date": inspection.inspection_date,
                "damage_found": inspection.damage_found,
                "walls_condition": inspection.walls_condition,
                "flooring_condition": inspection.flooring_condition,
            } if inspection else None,

            "maintenance": {
                "maintenance_required": maintenance.maintenance_required,
                "completed": maintenance.completed,
                "notes": maintenance.notes,
            } if maintenance else None,

            "settlement": {
                "damage_charges": settlement.damage_charges,
                "pending_dues": settlement.pending_dues,
                "final_amount": settlement.final_amount,
                "settled": settlement.settled,
            } if settlement else None,

            "created_at": move_in.created_at
        })

    return results


def get_upcoming_moveins(db: Session, space_id: UUID):
    # --------------------------------------------------
    # Upcoming move-ins
    # --------------------------------------------------
    upcoming = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.space_id == space_id,
            SpaceOccupancy.request_type == RequestType.move_in,
            SpaceOccupancy.status == OccupancyStatus.scheduled
        )
        .order_by(SpaceOccupancy.move_in_date.asc())
        .all()
    )

    upcoming_list = [
        {
            "occupant_type": u.occupant_type,
            "occupant_name": get_user_name(u.occupant_user_id),
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

    return upcoming_list


def get_occupancy_timeline(
    db: Session,
    space_id: UUID,
    user: UserToken
):
    events = (
        db.query(SpaceOccupancyEvent)
        .filter(SpaceOccupancyEvent.space_id == space_id)
        .order_by(SpaceOccupancyEvent.event_date.asc())
    )

    if user.account_type in [UserAccountType.FLAT_OWNER, UserAccountType.TENANT]:
        events = events.filter(
            SpaceOccupancyEvent.occupant_user_id == user.user_id)

    timeline = []

    for e in events:
        occupant_name = get_user_name(
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
        # Extract date
        move_in_date = params.move_in_date.date()

        # Determine time_slot
        if params.time_slot:
            time_slot = params.time_slot
        else:
            time_slot = params.move_in_date.time()

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
                    if move_in_date < lease.start_date:
                        return error_response(
                            message=f"Move-in date must be on or after lease start date ({lease.end_date})"
                        )
                    if move_in_date > lease.end_date:
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
            move_in_date=move_in_date,
            heavy_items=params.heavy_items,
            elevator_required=params.elevator_required,
            parking_required=params.parking_required,
            time_slot=time_slot,
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
    today = date.today()
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
    # Extract date
    move_out_date = params.move_out_date.date()

    # Determine time_slot
    if params.time_slot:
        time_slot = params.time_slot
    else:
        time_slot = params.move_out_date.time()

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
        if move_out_date > lease.end_date:
            return error_response(
                message=f"Move-out date cannot exceed lease end date({lease.end_date})"
            )
        elif move_out_date < lease.start_date:
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
        move_out_date=move_out_date,

        heavy_items=move_in.heavy_items,
        elevator_required=move_in.elevator_required,
        parking_required=move_in.parking_required,
        time_slot=time_slot,

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
        approve_move_out(db, move_out_request.id, current_user.user_id)

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
    today = date.today()
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
    if move_out.move_out_date and move_out.move_out_date <= today:
        start_handover_process(db, move_out, admin_user_id)
    return move_out


def start_handover_process(db: Session, move_out, admin_user_id):
    handover = SpaceHandover(
        occupancy_id=move_out.id,
        handover_by_user_id=move_out.occupant_user_id,
    )

    db.add(handover)
    db.commit()
    db.refresh(handover)

    log_occupancy_event(
        db,
        space_id=move_out.space_id,
        event_type=OccupancyEventType.handover_awaited,
        occupant_type=move_out.occupant_type,
        occupant_user_id=move_out.occupant_user_id,
        source_id=move_out.source_id,
        lease_id=move_out.lease_id
    )

    return handover


def update_handover(
    db: Session,
    occupancy_id: UUID,
    payload: HandoverUpdateSchema
):

    handover = db.query(SpaceHandover).filter(
        SpaceHandover.occupancy_id == occupancy_id
    ).first()

    if not handover:
        raise HTTPException(status_code=404, detail="Handover not found")

    for key, value in payload.dict(exclude_unset=True).items():
        # ADD: Skip email and phone if you want to block updates
        if key == "handover_date" and isinstance(value, str):
            value = datetime.fromisoformat(value)
        setattr(handover, key, value)

    db.commit()

    if is_handover_completed(handover):
        complete_handover(db, handover.id)

    return {"message": "Handover updated successfully", "handover_id": str(handover.id)}


def is_handover_completed(handover: SpaceHandover) -> bool:
    if not handover.keys_returned or handover.number_of_keys <= 0:
        return False

    if handover.accessories_returned:
        if handover.access_card_returned and handover.number_of_access_cards <= 0:
            return False
        if handover.parking_card_returned and handover.number_of_parking_cards <= 0:
            return False

    return True


def complete_handover(
    db: Session,
    handover_id: UUID,
):
    handover = db.query(SpaceHandover).filter(
        SpaceHandover.id == handover_id
    ).first()

    if not handover:
        raise Exception("Handover not found")

    # complete handover
    handover.status = HandoverStatus.completed

    move_out = db.query(SpaceOccupancy).filter(
        SpaceOccupancy.id == handover.occupancy_id
    ).first()

    if not move_out:
        db.commit()
        return handover

    # get original move-in
    original_move_in = None
    if move_out.original_occupancy_id:
        original_move_in = db.query(SpaceOccupancy).filter(
            SpaceOccupancy.id == move_out.original_occupancy_id
        ).first()

    if original_move_in:
        original_move_in.status = OccupancyStatus.moved_out
        original_move_in.move_out_date = datetime.utcnow().date()

        # ------------------------------------------------
        # Only for TENANT
        # ------------------------------------------------
        if original_move_in.occupant_type == OccupantType.tenant:

            # Close tenant_space
            tenant_space = db.query(TenantSpace).filter(
                TenantSpace.space_id == original_move_in.space_id,
                TenantSpace.tenant_id == original_move_in.source_id,
                TenantSpace.status == OwnershipStatus.leased
            ).first()

            if tenant_space:
                tenant_space.status = OwnershipStatus.ended
                tenant_space.ended_at = datetime.utcnow()

            # Close lease
            if original_move_in.lease_id:
                lease = db.query(Lease).filter(
                    Lease.id == original_move_in.lease_id
                ).first()

                if lease and lease.status == "active":
                    lease.status = "expired"
                    lease.end_date = datetime.utcnow().date()

    db.commit()
    db.refresh(handover)

    log_occupancy_event(
        db,
        space_id=move_out.space_id,
        event_type=OccupancyEventType.handover_completed,
        occupant_type=move_out.occupant_type,
        occupant_user_id=move_out.occupant_user_id,
        source_id=move_out.source_id,
        lease_id=move_out.lease_id
    )

    return handover


def request_inspection(
    db: Session,
    params: InspectionRequest
):
    """
    Create a new inspection request linked to a completed handover.
    """
    handover = db.query(SpaceHandover).filter(
        SpaceHandover.id == params.handover_id).first()
    if not handover:
        raise HTTPException(status_code=404, detail="Handover not found")

    if handover.status != "completed":
        raise HTTPException(
            status_code=400, detail="Handover not yet completed")

    move_out = db.query(SpaceOccupancy).filter(
        SpaceOccupancy.id == handover.occupancy_id
    ).first()

    # Check if an inspection already exists
    existing = db.query(SpaceInspection).filter(
        SpaceInspection.handover_id == params.handover_id).first()
    if existing:
        raise HTTPException(
            status_code=400, detail="Inspection already requested")

    inspection = SpaceInspection(
        handover_id=params.handover_id,
        requested_by=handover.handover_by_user_id,
        inspected_by_user_id=params.inspected_by_user_id,
        scheduled_date=params.scheduled_date,
        status="requested"
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    log_occupancy_event(
        db,
        space_id=move_out.space_id,
        event_type=OccupancyEventType.inspection_requested,
        occupant_type=move_out.occupant_type,
        occupant_user_id=move_out.occupant_user_id,
        source_id=move_out.source_id,
        lease_id=move_out.lease_id
    )

    return {"message": "Inspection requested successfully", "inspection_id": str(inspection.id)}


def complete_inspection(
    db: Session,
    inspection_id: UUID,
    params: InspectionComplete
):
    """
    Complete an inspection and record condition details.
    """

    inspection = db.query(SpaceInspection).filter(
        SpaceInspection.id == inspection_id
    ).first()

    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    if inspection.status == InspectionStatus.completed:
        raise HTTPException(
            status_code=400,
            detail="Inspection already completed"
        )

    move_out = (
        db.query(SpaceOccupancy)
        .join(SpaceHandover, SpaceHandover.occupancy_id == SpaceOccupancy.id)
        .filter(
            SpaceHandover.id == inspection.handover_id
        ).first()
    )

    # Update inspection details
    inspection.status = InspectionStatus.completed
    inspection.inspection_date = params.inspection_date or datetime.utcnow()

    inspection.damage_found = params.damage_found
    inspection.damage_notes = params.damage_notes

    inspection.walls_condition = params.walls_condition
    inspection.flooring_condition = params.flooring_condition
    inspection.electrical_condition = params.electrical_condition
    inspection.plumbing_condition = params.plumbing_condition

    # Inspector
    # inspection.inspected_by_user_id = params.inspected_by_user_id

    db.commit()
    db.refresh(inspection)

    log_occupancy_event(
        db,
        space_id=move_out.space_id,
        event_type=OccupancyEventType.inspection_completed,
        occupant_type=move_out.occupant_type,
        occupant_user_id=move_out.occupant_user_id,
        source_id=move_out.source_id,
        lease_id=move_out.lease_id
    )

    return {
        "message": "Inspection completed successfully",
        "inspection_id": str(inspection.id)
    }


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


def create_maintenance(
    db: Session,
    params: MaintenanceRequest,
    user_id: UUID
):
    """
    Create a maintenance record linked to a completed inspection.
    """

    inspection = db.query(SpaceInspection).filter(
        SpaceInspection.id == params.inspection_id
    ).first()

    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    if inspection.status != InspectionStatus.completed:
        raise HTTPException(
            status_code=400,
            detail="Inspection not yet completed"
        )

    # Check if maintenance already exists
    existing = db.query(SpaceMaintenance).filter(
        SpaceMaintenance.inspection_id == params.inspection_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Maintenance already created"
        )

    move_out = (
        db.query(SpaceOccupancy)
        .join(SpaceHandover, SpaceHandover.occupancy_id == SpaceOccupancy.id)
        .filter(
            SpaceHandover.id == inspection.handover_id
        ).first()
    )

    maintenance = SpaceMaintenance(
        inspection_id=params.inspection_id,
        maintenance_required=params.maintenance_required,
        notes=params.notes
    )

    db.add(maintenance)
    db.flush()

    if not maintenance.maintenance_required:
        complete_request = MaintenanceComplete(completed_at=datetime.utcnow())
        complete_maintenance(db, maintenance.id, complete_request, user_id)
    else:
        log_occupancy_event(
            db,
            space_id=move_out.space_id,
            event_type=OccupancyEventType.maintenance_requested,
            occupant_type=move_out.occupant_type,
            occupant_user_id=move_out.occupant_user_id,
            source_id=move_out.source_id,
            lease_id=move_out.lease_id
        )

    db.commit()
    db.refresh(maintenance)

    return {
        "message": "Maintenance created successfully",
        "maintenance_id": str(maintenance.id)
    }


def complete_maintenance(
    db: Session,
    maintenance_id: UUID,
    params: MaintenanceComplete,
    user_id: UUID
):
    """
    Mark maintenance as completed.
    """

    maintenance = db.query(SpaceMaintenance).filter(
        SpaceMaintenance.id == maintenance_id
    ).first()

    if not maintenance:
        raise HTTPException(status_code=404, detail="Maintenance not found")

    if maintenance.completed:
        raise HTTPException(
            status_code=400,
            detail="Maintenance already completed"
        )

    maintenance.completed = True
    maintenance.completed_by = user_id
    maintenance.completed_at = params.completed_at or datetime.utcnow()

    db.commit()
    db.refresh(maintenance)

    occupancy_id = get_occupancy_id_from_maintenance(
        db, maintenance_id)

    move_out = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.id == occupancy_id
        ).first()
    )

    log_occupancy_event(
        db,
        space_id=move_out.space_id,
        event_type=OccupancyEventType.maintenance_requested,
        occupant_type=move_out.occupant_type,
        occupant_user_id=move_out.occupant_user_id,
        source_id=move_out.source_id,
        lease_id=move_out.lease_id
    )

    request_settlement(db, occupancy_id, user_id)

    return {
        "message": "Maintenance completed successfully",
        "maintenance_id": str(maintenance.id)
    }


def request_settlement(
    db: Session,
    occupancy_id: UUID,
    current_user_id: UUID
):
    """
    Create settlement record after maintenance completion.
    """

    existing = db.query(SpaceSettlement).filter(
        SpaceSettlement.occupancy_id == occupancy_id
    ).first()

    if existing:
        return existing

    move_out = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.id == occupancy_id
        ).first()
    )

    settlement = SpaceSettlement(
        occupancy_id=occupancy_id,
        damage_charges=0,
        pending_dues=0,
        final_amount=0,
        settled=False,
        settled_by=current_user_id
    )

    db.add(settlement)
    db.commit()
    db.refresh(settlement)

    log_occupancy_event(
        db,
        space_id=move_out.space_id,
        event_type=OccupancyEventType.settlement_pending,
        occupant_type=move_out.occupant_type,
        occupant_user_id=move_out.occupant_user_id,
        source_id=move_out.source_id,
        lease_id=move_out.lease_id
    )

    return settlement


def complete_settlement(
    db: Session,
    settlement_id: UUID,
    params: SettlementComplete,
    current_user_id: UUID
):
    settlement = db.query(SpaceSettlement).filter(
        SpaceSettlement.id == settlement_id
    ).first()

    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")

    if settlement.settled:
        raise HTTPException(
            status_code=400,
            detail="Settlement already completed"
        )

    # Update settlement
    settlement.damage_charges = params.damage_charges
    settlement.pending_dues = params.pending_dues
    settlement.final_amount = (
        (params.damage_charges or 0) +
        (params.pending_dues or 0)
    )

    settlement.settled = True
    settlement.settled_by = current_user_id
    settlement.settled_at = params.settled_at or datetime.utcnow()

    # --------------------------------------------------
    # Update occupancy & space status
    # --------------------------------------------------
    occupancy = db.query(SpaceOccupancy).filter(
        SpaceOccupancy.id == settlement.occupancy_id
    ).first()

    if occupancy:
        # mark occupancy closed if still active
        if occupancy.status == OccupancyStatus.active:
            occupancy.status = OccupancyStatus.moved_out

        # update space status
        space = db.query(Space).filter(
            Space.id == occupancy.space_id
        ).first()

        if space:
            space.status = "available"

    db.commit()
    db.refresh(settlement)

    log_occupancy_event(
        db,
        space_id=occupancy.space_id,
        event_type=OccupancyEventType.settlement_completed,
        occupant_type=occupancy.occupant_type,
        occupant_user_id=occupancy.occupant_user_id,
        source_id=occupancy.source_id,
        lease_id=occupancy.lease_id
    )

    return {
        "message": "Settlement completed successfully",
        "settlement_id": str(settlement.id)
    }
# VALIDATION METHODS


def validate_space_available_for_assignment(
    db: Session,
    space_id: UUID,
    lease_start_date: datetime
):

    now = datetime.now(timezone.utc)

    # 🔹 FUTURE LEASE → skip occupancy checks
    if lease_start_date > now:
        return True

    # 🔹 CURRENT lease requires space readiness
    last_occupancy = (
        db.query(SpaceOccupancy)
        .filter(
            SpaceOccupancy.space_id == space_id,
            SpaceOccupancy.status == OccupancyStatus.moved_out
        )
        .order_by(SpaceOccupancy.updated_at.desc())
        .first()
    )

    if last_occupancy:
        handover = (
            db.query(SpaceHandover)
            .filter(SpaceHandover.occupancy_id == last_occupancy.id)
            .first()
        )

        if not handover or handover.status != HandoverStatus.completed:
            return error_response(
                message="Handover process not completed."
            )

    space = db.query(Space).filter(
        Space.id == space_id
    ).first()

    if not space or space.status != "available":
        return error_response(
            message="Space is not available for assignment."
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


def get_occupancy_id_from_maintenance(db: Session, maintenance_id: UUID):
    result = (
        db.query(SpaceMaintenance, SpaceHandover.occupancy_id)
        .join(SpaceInspection, SpaceMaintenance.inspection_id == SpaceInspection.id)
        .join(SpaceHandover, SpaceInspection.handover_id == SpaceHandover.id)
        .filter(SpaceMaintenance.id == maintenance_id)
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="Maintenance not found")

    maintenance, occupancy_id = result
    return occupancy_id
