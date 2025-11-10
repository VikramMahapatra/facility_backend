from operator import or_
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, and_, distinct, case
from sqlalchemy.dialects.postgresql import UUID
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional

from ...models.space_sites.sites import Site

from ...models.common.staff_sites import StaffSite

from ...enum.ticket_service_enum import TicketStatus
from ...models.service_ticket.sla_policy import SlaPolicy
from ...models.service_ticket.tickets import Ticket
from ...models.service_ticket.tickets_category import TicketCategory

from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.system.notifications import Notification
from ...schemas.system.notifications_schemas import NotificationOut

from ...models.leasing_tenants.leases import Lease
from shared.core.schemas import MasterQueryParams, UserToken

from ...models.leasing_tenants.tenants import Tenant
from ...models.space_sites.spaces import Space
from sqlalchemy.orm import joinedload
from shared.utils.enums import UserAccountType


def get_home_spaces(db: Session, user: UserToken):
    results = []

    account_type = user.account_type.lower()

    if account_type in (UserAccountType.TENANT, UserAccountType.FLAT_OWNER):
        tenant = (
            db.query(Tenant)
            .options(
                joinedload(Tenant.space).joinedload(Space.site),
                joinedload(Tenant.space).joinedload(Space.building),
                joinedload(Tenant.leases).joinedload(
                    Lease.space).joinedload(Space.site),
                joinedload(Tenant.leases).joinedload(
                    Lease.space).joinedload(Space.building),
            )
            .filter(Tenant.user_id == user.user_id)
            .first()
        )

        if not tenant:
            return {
                "spaces": [],
                "account_type": user.account_type,
                "status": user.status,
            }

        seen_space_ids = set()

        # 1️⃣ Registered space
        if tenant.space:
            results.append({
                "tenant_id": tenant.id,
                "space_id": tenant.space.id,
                "is_primary": True,
                "space_name": tenant.space.name,
                "site_id": tenant.site_id,
                "site_name": tenant.space.site.name if tenant.space.site else None,
                "building_name": tenant.space.building.name if tenant.space.building else None
            })
            seen_space_ids.add(tenant.space.id)

        # 2️⃣ Leased spaces
        for lease in tenant.leases:
            space = lease.space
            if space and space.id not in seen_space_ids:
                results.append({
                    "tenant_id": tenant.id,
                    "space_id": space.id,
                    "is_primary": False,
                    "space_name": space.name,
                    "site_id": space.site_id,
                    "site_name": space.site.name if space.site else None,
                    "building_name": space.building.name if space.building else None
                })
                seen_space_ids.add(space.id)

    elif account_type == UserAccountType.STAFF:
        sites = (
            db.query(StaffSite)
            .filter(StaffSite.user_id == user.user_id)
            .all()
        )
        results = [
            {"site_id": s.site_id, "site_name": s.site.name, "is_primary": True}
            for s in sites
        ]

    else:
        sites = (
            db.query(Site)
            .filter(Site.org_id == user.org_id)
            .all()
        )
        results = [
            {"site_id": s.id, "site_name": s.name, "is_primary": True}
            for s in sites
        ]

    return {
        "spaces": results,
        "account_type": user.account_type,
        "status": user.status,
    }


def get_home_details(db: Session, params: MasterQueryParams, user: UserToken):
    """
    Get comprehensive home details for a specific space
    """
    now = datetime.now(timezone.utc)
    account_type = user.account_type.lower()

    # ✅ Always define placeholders at top level
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

    # ------------------------------
    # Tenant or Flat Owner flow
    # ------------------------------
    if account_type in (UserAccountType.TENANT, UserAccountType.FLAT_OWNER):
        lease = (
            db.query(Lease)
            .filter(
                and_(
                    Lease.space_id == params.space_id,
                    Lease.is_deleted == False,
                    Lease.end_date >= date.today()
                )
            )
            .order_by(Lease.end_date.desc())
            .first()
        )

        # If no active lease, fallback to most recent
        if not lease:
            lease = (
                db.query(Lease)
                .filter(
                    and_(
                        Lease.space_id == params.space_id,
                        Lease.is_deleted == False
                    )
                )
                .order_by(Lease.end_date.desc())
                .first()
            )

        if lease:
            lease_contract_detail.update({
                "start_date": lease.start_date,
                "expiry_date": lease.end_date,
                "rent_amount": float(lease.rent_amount or 0),
                "rent_frequency": lease.frequency,
            })

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
                c.amount for c in rent_charges) if rent_charges else 0.0
            all_rent_periods = rent_query.order_by(
                LeaseCharge.period_end.desc()).all()

            current_date = date.today()
            last_rent_paid, next_rent_due = None, None

            for period in all_rent_periods:
                if period.period_start <= current_date <= period.period_end:
                    last_rent_paid = period.period_start
                    next_rent_due = period.period_end + timedelta(days=1)
                    break

            lease_contract_detail.update({
                "total_rent_paid": float(total_rent_paid),
                "last_paid_date": last_rent_paid,
                "next_due_date": next_rent_due
            })

            # ✅ Maintenance details
            maint_query = (
                db.query(LeaseCharge)
                .filter(
                    and_(
                        LeaseCharge.lease_id == lease.id,
                        LeaseCharge.is_deleted == False,
                        LeaseCharge.charge_code == "MAINT"
                    )
                )
            )

            maint_charges = maint_query.all()
            total_maint_paid = sum(
                c.amount for c in maint_charges) if maint_charges else 0.0
            all_periods = maint_query.order_by(
                LeaseCharge.period_end.desc()).all()

            last_paid, next_due, next_amount = None, None, None
            for period in all_periods:
                if period.period_start <= current_date <= period.period_end:
                    last_paid = period.period_start
                    next_due = period.period_end + timedelta(days=1)
                    next_amount = period.amount
                    break

            maintenance_detail.update({
                "last_paid": last_paid,
                "next_due_date": next_due,
                "total_maintenance_paid": float(total_maint_paid),
                "next_maintenance_amount": float(next_amount or 0)
            })

        tenant_id = db.query(Tenant.id).filter(
            and_(Tenant.user_id == user.user_id, Tenant.is_deleted == False)
        ).scalar()

        ticket_filters = [Ticket.tenant_id == tenant_id]

    # ------------------------------
    # Staff / Organisation flow
    # ------------------------------
    else:
        ticket_filters = [Ticket.org_id == user.org_id]

        if account_type == UserAccountType.STAFF:
            ticket_filters.append(Ticket.assigned_to == user.user_id)

    # ------------------------------
    # Ticket filters
    # ------------------------------
    if params.site_id:
        ticket_filters.append(Ticket.site_id == params.site_id)
    if params.space_id and user.account_type != UserAccountType.STAFF:
        ticket_filters.append(Ticket.space_id == params.space_id)

    ticket_query = db.query(Ticket).filter(*ticket_filters)

    total_tickets = ticket_query.count()
    closed_tickets = ticket_query.filter(
        Ticket.status == TicketStatus.CLOSED).count()
    open_tickets = ticket_query.filter(
        Ticket.status == TicketStatus.OPEN).count()

    overdue_tickets = (
        ticket_query
        .join(Ticket.category)
        .join(TicketCategory.sla_policy)
        .filter(
            Ticket.status != TicketStatus.CLOSED,
            func.extract("epoch", now - Ticket.created_at) / 60 >
            func.coalesce(SlaPolicy.resolution_time_mins, 0)
        )
        .count()
    )

    statistics = {
        "total_tickets": total_tickets,
        "closed_tickets": closed_tickets,
        "open_tickets": open_tickets,
        "overdue_tickets": overdue_tickets,
    }

    notifications = (
        db.query(Notification)
        .filter(and_(Notification.user_id == user.user_id, Notification.read == False))
        .order_by(Notification.posted_date.desc())
        .limit(5)
        .all()
    )

    notification_list = [NotificationOut(**n.__dict__) for n in notifications]

    # ✅ No chance of UnboundLocalError now
    return {
        "lease_contract_detail": lease_contract_detail,
        "maintenance_detail": maintenance_detail,
        "statistics": statistics,
        "notifications": notification_list or [],
    }
