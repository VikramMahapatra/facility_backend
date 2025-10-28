from operator import or_
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, and_, distinct, case
from sqlalchemy.dialects.postgresql import UUID
from datetime import date, datetime, timedelta
from typing import Dict, Optional

from facility_service.app.models.leasing_tenants.lease_charges import LeaseCharge
from facility_service.app.models.maintenance_assets.service_request import ServiceRequest
from facility_service.app.models.maintenance_assets.work_order import WorkOrder

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
            "building_name": tenant.space.building.name if tenant.space.building else None,
            "account_type": user.account_type,
            "status": user.status,
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
                "building_name": space.building.name if space.building else None,
                "account_type": user.account_type,
                "status": user.status,
            }

    return list(results.values())



def get_home_details(db: Session, space_id: UUID):
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
    
    # ✅ 1. Lease Contract Details
    lease_contract_detail = {
        "start_date": None,
        "expiry_date": None, 
        "lease_amount": 0.0
    }
    
    if lease:
        lease_contract_detail["start_date"] = lease.start_date
        lease_contract_detail["expiry_date"] = lease.end_date
        
        # ✅ FIXED: Calculate TOTAL lease amount PROPERLY
        # Get base rent amount
        base_rent = float(lease.rent_amount) if lease.rent_amount else 0.0
        
        # Get sum of ALL additional charges (including maintenance)
        additional_charges_sum = (
            db.query(func.coalesce(func.sum(LeaseCharge.amount), 0))
            .filter(
                and_(
                    LeaseCharge.lease_id == lease.id,
                    LeaseCharge.is_deleted == False
                )
            )
            .scalar()
        )
        additional_charges = float(additional_charges_sum) if additional_charges_sum else 0.0
        
        # ✅ TOTAL = Base Rent + All Additional Charges
        lease_contract_detail["lease_amount"] = base_rent + additional_charges
        
        # ✅ 2. Maintenance Details - FIXED LOGIC
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
    maintenance_amount = sum(charge.amount for charge in maintenance_charges) if maintenance_charges else 0

    # ✅ FIXED: Smart date logic that handles current ongoing periods
    current_date = date.today()

    # Find the most recent maintenance period (could be ongoing or completed)
    all_periods = (
        maintenance_query
        .order_by(LeaseCharge.period_end.desc())
        .all()
    )

    last_paid = None
    next_due_date = None

    if all_periods:
        # Find the current or most recent period
        current_period = None
        for period in all_periods:
            if period.period_start <= current_date <= period.period_end:
                current_period = period
                break
        
        if current_period:
            # We're in an active maintenance period
            last_paid = current_period.period_start  # Payment due at start of period
            # Next due is end of current period + 1 day (start of next period)
            next_due_date = current_period.period_end + timedelta(days=1)
        else:
            # No current period, find the most recent completed period
            completed_periods = [p for p in all_periods if p.period_end < current_date]
            if completed_periods:
                last_completed = completed_periods[0]  # Already sorted by period_end desc
                last_paid = last_completed.period_end
                next_due_date = last_completed.period_end + timedelta(days=1)
            else:
                # Only future periods exist
                future_periods = [p for p in all_periods if p.period_start > current_date]
                if future_periods:
                    next_due_date = min(future_periods, key=lambda x: x.period_start).period_start
        
        # If we still don't have next_due_date, calculate from the last period
        if not next_due_date and all_periods:
            last_period = all_periods[0]  # Most recent period
            next_due_date = last_period.period_end + timedelta(days=1)

    maintenance_detail = {
        "last_paid": last_paid,
        "next_due_date": next_due_date,
        "maintenance_amount": float(maintenance_amount)
    }
    # ✅ 3. Statistics with Actual Period Values
    current_time = datetime.now()
    period_start = current_time - timedelta(days=30)
    period_end = current_time
    
    closed_statuses = ["closed", "completed", "resolved"]
    open_statuses = ["open", "in_progress", "in progress", "assigned", "pending", "active"]
    
    # Service Requests (Last 30 days)
    sr_query = db.query(ServiceRequest).filter(
        and_(
            ServiceRequest.space_id == space_id,
            ServiceRequest.is_deleted == False,
            ServiceRequest.created_at >= period_start,
            ServiceRequest.created_at <= period_end
        )
    )
    
    # Work Orders (Last 30 days)
    wo_query = db.query(WorkOrder).filter(
        and_(
            WorkOrder.space_id == space_id,
            WorkOrder.is_deleted == False,
            WorkOrder.created_at >= period_start,
            WorkOrder.created_at <= period_end
        )
    )
    
    # Total Tickets
    total_sr = sr_query.count()
    total_wo = wo_query.count()
    total_tickets = total_sr + total_wo
    
    # Closed Tickets
    closed_sr = sr_query.filter(ServiceRequest.status.in_(closed_statuses)).count()
    closed_wo = wo_query.filter(WorkOrder.status.in_(closed_statuses)).count()
    closed_tickets = closed_sr + closed_wo
    
    # Open Tickets
    open_sr = sr_query.filter(ServiceRequest.status.in_(open_statuses)).count()
    open_wo = wo_query.filter(WorkOrder.status.in_(open_statuses)).count()
    open_tickets = open_sr + open_wo
    
    # Overdue Tickets
    overdue_wo = wo_query.filter(
        and_(
            WorkOrder.due_at.isnot(None),
            WorkOrder.due_at < current_time,
            WorkOrder.status.in_(open_statuses)
        )
    ).count()
    
    # Service Requests older than 7 days considered overdue
    overdue_threshold = current_time - timedelta(days=7)
    overdue_sr = sr_query.filter(
        and_(
            ServiceRequest.created_at < overdue_threshold,
            ServiceRequest.status.in_(open_statuses)
        )
    ).count()
    
    overdue_tickets = overdue_wo + overdue_sr
    
    statistics = {
        "total_tickets": total_tickets,
        "closed_tickets": closed_tickets,
        "open_tickets": open_tickets,
        "overdue_tickets": overdue_tickets,
        "period": {
            "start": period_start.date(),
            "end": period_end.date()
        }
    }
    
    return {
        "lease_contract_detail": lease_contract_detail,
        "maintenance_detail": maintenance_detail,
        "statistics": statistics
    }