from operator import or_
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, and_, distinct, case
from sqlalchemy.dialects.postgresql import UUID
from datetime import date, datetime, timedelta
from typing import Dict, Optional

from facility_service.app.models.service_ticket.tickets import Ticket
from facility_service.app.models.service_ticket.tickets_work_order import TicketWorkOrder

from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.maintenance_assets.service_request import ServiceRequest
from ...models.maintenance_assets.work_order import WorkOrder
from ...models.system.notifications import Notification
from ...schemas.system.notifications_schemas import NotificationOut

from ...models.leasing_tenants.leases import Lease
from shared.schemas import UserToken

from ...models.leasing_tenants.tenants import Tenant
from ...models.space_sites.spaces import Space
from sqlalchemy.orm import joinedload


def get_home_spaces(db: Session, user: UserToken):
    tenant = (
        db.query(Tenant)
        .options(
            joinedload(Tenant.space)
            .joinedload(Space.site),
            joinedload(Tenant.space)
            .joinedload(Space.building),
            joinedload(Tenant.leases)
            .joinedload(Lease.space)
            .joinedload(Space.site),
            joinedload(Tenant.leases)
            .joinedload(Lease.space)
            .joinedload(Space.building),
        )
        .filter(Tenant.user_id == user.user_id)
        .first()
    )

    if not tenant:
        return []

    results = {}

    # ✅ 1. Registered space (always included)
    if tenant.space:
        results[tenant.space.id] = {
            "tenant_id": tenant.id,
            "space_id": tenant.space.id,
            "is_primary": True,
            "space_name": tenant.space.name,
            "site_name": tenant.space.site.name if tenant.space.site else None,
            "building_name": tenant.space.building.name if tenant.space.building else None
        }

    # ✅ 2. Leased spaces
    for lease in tenant.leases:
        space = lease.space
        if not space:
            continue
        # Avoid duplicates (registered space may also be leased)
        if space.id not in results:
            results[space.id] = {
                "tenant_id": tenant.id,
                "space_id": space.id,
                "is_primary": False,
                "space_name": space.name,
                "site_name": space.site.name if space.site else None,
                "building_name": space.building.name if space.building else None
            }

    return {
        "spaces": list(results.values()),
        "account_type": user.account_type,
        "status": user.status,
    }






def get_home_details(db: Session, space_id: UUID, user: UserToken):
    """
    Get comprehensive home details for a specific space
    """
    # Get the ACTIVE lease for this space
    lease = (
        db.query(Lease)
        .filter(
            and_(
                Lease.space_id == space_id,
                Lease.is_deleted == False,
                Lease.end_date >= date.today()
            )
        )
        .order_by(Lease.end_date.desc())
        .first()
    )

    # If no active lease, get the most recent lease
    if not lease:
        lease = (
            db.query(Lease)
            .filter(
                and_(
                    Lease.space_id == space_id,
                    Lease.is_deleted == False
                )
            )
            .order_by(Lease.end_date.desc())
            .first()
        )

    # ✅ Default placeholders
    lease_contract_detail = {
        "start_date": None,
        "expiry_date": None,
        "rent_amount": 0.0,
        "total_rent_paid": 0.0,
        "rent_frequency": None,
        "last_paid_date": None,
        "next_due_date": None
    }

    maintenance_detail = {
        "last_paid": None,
        "next_due_date": None,
        "total_maintenance_paid": 0.0,
        "next_maintenance_amount": 0.0
    }

    if lease:
        lease_contract_detail["start_date"] = lease.start_date
        lease_contract_detail["expiry_date"] = lease.end_date

        rent_amount = float(lease.rent_amount) if lease.rent_amount else 0.0

        rent_query = (
            db.query(LeaseCharge)
            .filter(
                and_(
                    LeaseCharge.lease_id == lease.id,
                    LeaseCharge.is_deleted == False,
                    LeaseCharge.charge_code == "RENT"
                )
            )
        )
        rent_charges = rent_query.all()
        total_rent_paid = sum(
            charge.amount for charge in rent_charges) if rent_charges else 0

        all_rent_periods = (
            rent_query
            .order_by(LeaseCharge.period_end.desc())
            .all()
        )

        current_date = date.today()
        last_rent_paid = None
        next_rent_due_date = None

        if all_rent_periods:
            for period in all_rent_periods:
                if period.period_start <= current_date <= period.period_end:
                    last_rent_paid = period.period_start
                    next_rent_due_date = period.period_end + timedelta(days=1)
                    break

        lease_contract_detail["total_rent_paid"] = float(total_rent_paid)
        lease_contract_detail["rent_frequency"] = lease.frequency
        lease_contract_detail["rent_amount"] = rent_amount
        lease_contract_detail["last_paid_date"] = last_rent_paid
        lease_contract_detail["next_due_date"] = next_rent_due_date

        # ✅ Maintenance details
        maintenance_query = (
            db.query(LeaseCharge)
            .filter(
                and_(
                    LeaseCharge.lease_id == lease.id,
                    LeaseCharge.is_deleted == False,
                    LeaseCharge.charge_code == "MAINT"
                )
            )
        )

        maintenance_charges = maintenance_query.all()
        maintenance_amount = sum(
            charge.amount for charge in maintenance_charges) if maintenance_charges else 0

        next_maintenance_amount = None
        all_periods = (
            maintenance_query
            .order_by(LeaseCharge.period_end.desc())
            .all()
        )

        last_paid = None
        next_due_date = None

        if all_periods:
            for period in all_periods:
                if period.period_start <= current_date <= period.period_end:
                    last_paid = period.period_start
                    next_due_date = period.period_end + timedelta(days=1)
                    next_maintenance_amount = period.amount
                    break

        maintenance_detail = {
            "last_paid": last_paid,
            "next_due_date": next_due_date,
            "total_maintenance_paid": float(maintenance_amount),
            "next_maintenance_amount": float(next_maintenance_amount or 0)
        }

    # ✅ Replace your existing “statistics” section with this:

    # ✅ Statistics (using Ticket and TicketWorkOrder)
    current_time = datetime.now()
    period_start = current_time - timedelta(days=30)
    period_end = current_time

    closed_statuses = ["closed", "completed", "resolved"]
    open_statuses = ["open", "in_progress", "in progress", "assigned", "pending", "active"]

    ticket_query = (
        db.query(Ticket)
        .filter(
            and_(
                Ticket.space_id == space_id,
                Ticket.created_at >= period_start,
                Ticket.created_at <= period_end
            )
        )
    )

    work_order_query = (
        db.query(TicketWorkOrder)
        .join(Ticket, TicketWorkOrder.ticket_id == Ticket.id)
        .filter(
            and_(
                Ticket.space_id == space_id,
                TicketWorkOrder.created_at >= period_start,
                TicketWorkOrder.created_at <= period_end
            )
        )
    )

    total_tickets = ticket_query.count()
    total_work_orders = work_order_query.count()
    total_combined = total_tickets + total_work_orders

    closed_tickets = (
        ticket_query.filter(Ticket.status.in_(closed_statuses)).count()
        + work_order_query.filter(TicketWorkOrder.status.in_(closed_statuses)).count()
    )

    open_tickets = (
        ticket_query.filter(Ticket.status.in_(open_statuses)).count()
        + work_order_query.filter(TicketWorkOrder.status.in_(open_statuses)).count()
    )

    overdue_threshold = current_time - timedelta(days=7)

    overdue_tickets = (
        ticket_query.filter(
            and_(
                Ticket.created_at < overdue_threshold,
                Ticket.status.in_(open_statuses)
            )
        ).count()
        + work_order_query.filter(
            and_(
                TicketWorkOrder.created_at < overdue_threshold,
                TicketWorkOrder.status.in_(open_statuses)
            )
        ).count()
    )

    statistics = {
        "total_tickets": total_combined,
        "closed_tickets": closed_tickets,
        "open_tickets": open_tickets,
        "overdue_tickets": overdue_tickets,
        "period": {
            "start": period_start.date(),
            "end": period_end.date()
        }
    }


    notifications = (
        db.query(Notification)
        .filter(and_(Notification.user_id == user.user_id, Notification.read == False))
        .order_by(Notification.posted_date.desc())
        .limit(5)
        .all()
    )

    notfication_list = [NotificationOut(**n.__dict__) for n in notifications]


    return {
        "lease_contract_detail": lease_contract_detail | {},
        "maintenance_detail": maintenance_detail | {},
        "statistics": statistics,
        "notifications": notfication_list or []
    }
