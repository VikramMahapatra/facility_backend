from datetime import date

from sqlalchemy.orm import Session

from facility_service.app.crud.space_sites.space_occupancy_crud import start_handover_process
from facility_service.app.models.leasing_tenants.leases import Lease
from facility_service.app.models.leasing_tenants.tenant_spaces import TenantSpace
from facility_service.app.models.space_sites.space_handover import HandoverStatus, SpaceHandover
from facility_service.app.models.space_sites.space_occupancies import OccupancyStatus, RequestType, SpaceOccupancy
from facility_service.app.models.space_sites.spaces import Space
from shared.utils.enums import OwnershipStatus


def process_scheduled_occupancies(db: Session):
    today = date.today()

    try:
        # =====================================================
        # 1️⃣ ACTIVATE SCHEDULED MOVE-INS
        # =====================================================
        move_ins = (
            db.query(SpaceOccupancy)
            .filter(
                SpaceOccupancy.request_type == RequestType.move_in,
                SpaceOccupancy.status == OccupancyStatus.scheduled,
                SpaceOccupancy.move_in_date <= today
            )
            .all()
        )

        for occ in move_ins:
            occ.status = OccupancyStatus.active

            # Mark space occupied
            db.query(Space).filter(
                Space.id == occ.space_id
            ).update({
                "status": "occupied"
            })

            print(f"Move-in activated: {occ.id}")

        # =====================================================
        # 2️⃣ PROCESS MOVE-OUTS
        # =====================================================
        move_outs = (
            db.query(SpaceOccupancy)
            .filter(
                SpaceOccupancy.request_type == RequestType.move_out,
                SpaceOccupancy.status == OccupancyStatus.scheduled,
                SpaceOccupancy.move_out_date <= today
            )
            .all()
        )

        for occ in move_outs:

            # Check handover completion
            handover = (
                db.query(SpaceHandover)
                .filter(
                    SpaceHandover.occupancy_id == occ.id,
                    SpaceHandover.status == HandoverStatus.completed
                )
                .first()
            )

            if not handover:
                continue

            # Mark move-out
            occ.status = OccupancyStatus.moved_out

            # Update original occupancy
            if occ.original_occupancy_id:
                original = db.query(SpaceOccupancy).filter(
                    SpaceOccupancy.id == occ.original_occupancy_id
                ).first()

                if original:
                    original.status = OccupancyStatus.moved_out

            # =====================================================
            # END LEASE
            # =====================================================
            if occ.lease_id:
                lease = db.query(Lease).filter(
                    Lease.id == occ.lease_id,
                    Lease.is_deleted == False
                ).first()

                if lease:
                    lease.status = "ended"
                    lease.termination_date = today

            # =====================================================
            # END TENANT SPACE
            # =====================================================
            if occ.source_id:  # tenant_id
                db.query(TenantSpace).filter(
                    TenantSpace.space_id == occ.space_id,
                    TenantSpace.tenant_id == occ.source_id,
                    TenantSpace.status == OwnershipStatus.approved
                ).update({
                    "status": OwnershipStatus.ended,
                    "ended_at": today
                })

            # Free the space
            db.query(Space).filter(
                Space.id == occ.space_id
            ).update({
                "status": "available"
            })

            print(f"Move-out completed: {occ.id}")

        db.commit()

    except Exception as e:
        db.rollback()
        print("Scheduler error:", str(e))

    def process_scheduled_moveouts(db: Session):
        today = date.today()

        move_outs = db.query(SpaceOccupancy).filter(
            SpaceOccupancy.request_type == RequestType.move_out,
            SpaceOccupancy.status == OccupancyStatus.scheduled,
            SpaceOccupancy.move_out_date <= today
        ).all()

        for move_out in move_outs:
            start_handover_process(db, move_out, admin_user_id=None)
            move_out.status = OccupancyStatus.moved_out

        db.commit()
        db.close()
