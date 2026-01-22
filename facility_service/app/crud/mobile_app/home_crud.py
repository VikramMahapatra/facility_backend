from operator import or_
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, and_, distinct, case
from sqlalchemy.dialects.postgresql import UUID
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional

from facility_service.app.enum.space_sites_enum import OwnershipType
from facility_service.app.models.space_sites.owner_maintenances import OwnerMaintenanceCharge
from facility_service.app.models.space_sites.space_owners import SpaceOwner
from facility_service.app.schemas.mobile_app.home_schemas import HomeDetailsWithSpacesResponse, LeaseContractDetail, MaintenanceDetail, Period, SpaceDetailsResponse

from ...models.leasing_tenants.tenant_spaces import TenantSpace

from ...models.leasing_tenants.commercial_partners import CommercialPartner

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
    sites = []
    account_type = user.account_type.lower()

    if account_type in (UserAccountType.TENANT, UserAccountType.FLAT_OWNER):
        tenant = (
            db.query(Tenant)
            .options(
                joinedload(Tenant.tenant_spaces)
                .joinedload(TenantSpace.space)
                .joinedload(Space.site)
                .joinedload(Site.org)
            )
            .filter(Tenant.user_id == user.user_id, Tenant.is_deleted == False)
            .first()
        )

        if not tenant:
            return {
                "sites": []
               
            }

        seen_site_ids = set()

        # 1️⃣ Registered space
        for ts in tenant.tenant_spaces:
            if ts.is_deleted or not ts.space or not ts.space.site:
                continue

            site = ts.space.site
            if site.id in seen_site_ids:
                continue
            
            # Check if site has any space with primary active space owner
            has_primary_owner = db.query(SpaceOwner).join(
                Space, SpaceOwner.space_id == Space.id
            ).filter(
                Space.site_id == site.id,
                SpaceOwner.ownership_type == OwnershipType.PRIMARY,
                SpaceOwner.is_active == True
            ).first() is not None

            sites.append({
                "site_id": site.id,
                "site_name": site.name,
                "is_primary": has_primary_owner,
                "org_id": site.org_id,
                "org_name": site.org.name if site.org else None,
                "address": site.address,
            })

            seen_site_ids.add(site.id)

    elif account_type == UserAccountType.STAFF:
        staff_sites = (
            db.query(StaffSite)
            .filter(StaffSite.user_id == user.user_id)
            .all()
        )
        for staff_site in staff_sites:
            site = staff_site.site
            # Check if site has any space with primary active space owner
            has_primary_owner = db.query(SpaceOwner).join(
                Space, SpaceOwner.space_id == Space.id
            ).filter(
                Space.site_id == site.id,
                SpaceOwner.ownership_type == OwnershipType.PRIMARY,
                SpaceOwner.is_active == True
            ).first() is not None
            sites.append({
                "site_id": site.id,
                "site_name": site.name, 
                "is_primary": has_primary_owner,
                "org_id": site.org_id,
                "org_name": site.org.name if site.org else None,
                "address": site.address,
                }
            )

    else:
        sites_records = (
            db.query(Site)
            .filter(Site.org_id == user.org_id)
            .all()
        )
        for site in sites_records:
            # Check if site has any space with primary active space owner
            has_primary_owner = db.query(SpaceOwner).join(
                Space, SpaceOwner.space_id == Space.id
            ).filter(
                Space.site_id == site.id,
                SpaceOwner.ownership_type == OwnershipType.PRIMARY,
                SpaceOwner.is_active == True
            ).first() is not None
            sites.append({
                "site_id": site.id,
                "site_name": site.name,
                "is_primary": has_primary_owner,
                "org_id": site.org_id,
                "org_name": site.org.name if site.org else None,
                "address": site.address,
                })

    return {
        "sites": sites,
    }


def get_home_details(db: Session, params: MasterQueryParams, user: UserToken):
    """
    Get comprehensive home details for a specific space
    """
    now = datetime.now(timezone.utc)
    account_type = user.account_type.lower()
    tenant_type = user.tenant_type.lower() if user.tenant_type else None
    period_end = date.today()
    period_start = period_end - timedelta(days=30)
    spaces_response = []
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

    lease_contract_exist = False

    # ------------------------------
    # Tenant or Flat Owner flow
    # ------------------------
    if account_type in (UserAccountType.TENANT, UserAccountType.FLAT_OWNER):
        print("Tenant Type :", tenant_type)
        
        # Get all spaces for the site
        spaces_query = db.query(Space).filter(
            Space.site_id == params.site_id,
            Space.is_deleted == False
        ).options(
            joinedload(Space.building)
        )
        
        spaces = spaces_query.all()
        
        # Get tenant record
        tenant = db.query(Tenant).filter(
            Tenant.user_id == user.user_id,
            Tenant.is_deleted == False
        ).first()
        
        # Process each space
        for space in spaces:
            # Initialize space-specific variables
            space_is_owner = False
            space_lease_contract_exist = False
            space_lease_contract_detail = LeaseContractDetail()
            space_maintenance_detail = MaintenanceDetail()
            
            # 1. CHECK IF USER IS SPACE OWNER
            space_owner = db.query(SpaceOwner).filter(
                SpaceOwner.space_id == space.id,
                SpaceOwner.owner_user_id == user.user_id,
                SpaceOwner.is_active == True
            ).first()
            
            if space_owner:
                space_is_owner = True
                
                # Get maintenance details from OwnerMaintenanceCharge
                owner_maint_query = db.query(OwnerMaintenanceCharge).filter(
                    OwnerMaintenanceCharge.space_owner_id == space_owner.id,
                    OwnerMaintenanceCharge.is_deleted == False
                ).order_by(OwnerMaintenanceCharge.period_end.desc())
                
                owner_maint_charges = owner_maint_query.all()
                
                # Calculate total maintenance paid
                total_maint_paid = sum(
                    c.amount for c in owner_maint_charges if c.status == "paid"
                ) if owner_maint_charges else 0.0
                
                # Find current/latest maintenance period
                current_date = date.today()
                for charge in owner_maint_charges:
                    if charge.period_start <= current_date <= charge.period_end:
                        space_maintenance_detail = MaintenanceDetail(
                            last_paid=charge.period_start if charge.status == "paid" else None,
                            next_due_date=charge.period_end,
                            next_maintenance_amount=float(charge.amount or 0),
                            total_maintenance_paid=float(total_maint_paid)
                        )
                        break
                    elif charge.period_end < current_date and charge.status == "paid":
                        space_maintenance_detail = MaintenanceDetail(
                            last_paid=charge.period_end,
                            next_due_date=None,
                            next_maintenance_amount=0.0,
                            total_maintenance_paid=float(total_maint_paid)
                        )
                        break
                
                # If no current period found, use default with total paid
                if space_maintenance_detail.total_maintenance_paid == 0:
                    space_maintenance_detail.total_maintenance_paid = float(total_maint_paid)
            
            # 2. CHECK IF USER IS TENANT (for lease contract)
            if tenant:
                # Check if tenant has access to this space
                tenant_space = db.query(TenantSpace).filter(
                    TenantSpace.tenant_id == tenant.id,
                    TenantSpace.space_id == space.id,
                    TenantSpace.is_deleted == False
                ).first()
                
                if tenant_space:
                    # Get lease for this space
                    lease_query = db.query(Lease).filter(
                        Lease.space_id == space.id,
                        Lease.tenant_id == tenant.id,
                        Lease.is_deleted == False,
                        Lease.end_date >= date.today()
                    )
                    
                    lease = lease_query.order_by(Lease.end_date.desc()).first()
                    
                    # Fallback to most recent if no active lease
                    if not lease:
                        lease_query = db.query(Lease).filter(
                            Lease.space_id == space.id,
                            Lease.tenant_id == tenant.id,
                            Lease.is_deleted == False
                        )
                        lease = lease_query.order_by(Lease.end_date.desc()).first()
                    
                    if lease:
                        space_lease_contract_exist = True
                        
                        # Get rent payments
                        rent_query = db.query(LeaseCharge).filter(
                            LeaseCharge.lease_id == lease.id,
                            LeaseCharge.is_deleted == False,
                            LeaseCharge.charge_code.has(code="RENT")
                        )
                        
                        rent_charges = rent_query.all()
                        total_rent_paid = sum(
                            c.amount for c in rent_charges
                        ) if rent_charges else 0.0
                        
                        # Find current rent period
                        current_date = date.today()
                        all_rent_periods = rent_query.order_by(
                            LeaseCharge.period_end.desc()
                        ).all()
                        
                        last_rent_paid, next_rent_due = None, None
                        for period in all_rent_periods:
                            if period.period_start <= current_date <= period.period_end:
                                last_rent_paid = period.period_start
                                next_rent_due = period.period_end + timedelta(days=1)
                                break
                            elif period.period_end <= current_date:
                                last_rent_paid = period.period_end
                                next_rent_due = period.period_end + timedelta(days=1)
                                break
                        
                        space_lease_contract_detail = LeaseContractDetail(
                            start_date=lease.start_date,
                            expiry_date=lease.end_date,
                            rent_amount=float(lease.rent_amount or 0),
                            total_rent_paid=float(total_rent_paid),
                            rent_frequency=lease.frequency,
                            last_paid_date=last_rent_paid,
                            next_due_date=next_rent_due
                        )
                        
                        # If user is NOT owner, get maintenance from lease charges
                        if not space_is_owner:
                            # Get maintenance from lease charges
                            maint_query = db.query(LeaseCharge).filter(
                                LeaseCharge.lease_id == lease.id,
                                LeaseCharge.is_deleted == False,
                                LeaseCharge.charge_code.has(code="MAINTENANCE")
                            )
                            
                            maint_charges = maint_query.all()
                            total_maint_paid = sum(
                                c.amount for c in maint_charges
                            ) if maint_charges else 0.0
                            
                            all_maint_periods = maint_query.order_by(
                                LeaseCharge.period_end.desc()
                            ).all()
                            
                            last_paid, next_due, next_amount = None, None, None
                            for period in all_maint_periods:
                                if period.period_start <= current_date <= period.period_end:
                                    last_paid = period.period_start
                                    next_due = period.period_end + timedelta(days=1)
                                    next_amount = period.amount
                                    break
                                elif period.period_end <= current_date:
                                    last_paid = period.period_end
                                    next_due = period.period_end + timedelta(days=1)
                                    next_amount = period.amount
                                    break
                            
                            space_maintenance_detail = MaintenanceDetail(
                                last_paid=last_paid,
                                next_due_date=next_due,
                                total_maintenance_paid=float(total_maint_paid),
                                next_maintenance_amount=float(next_amount or 0)
                            )
            
            # Add space to response
            spaces_response.append(SpaceDetailsResponse(
                space_id=space.id,
                space_name=space.name,
                building_id=space.building_id,
                building_name=space.building.name if space.building else None,
                is_owner=space_is_owner,
                lease_contract_exist=space_lease_contract_exist,
                lease_contract_detail=space_lease_contract_detail,
                maintenance_detail=space_maintenance_detail
            ))
        
        # Set ticket filters for tenant
        tenant_id = tenant.id if tenant else None
        ticket_filters = [Ticket.tenant_id == tenant_id] if tenant_id else []
    # ------------------------------
    # Staff / Organisation flow
    
    else:
        # For staff/org users, show all spaces in site without owner/tenant details
        spaces_query = db.query(Space).filter(
            Space.site_id == params.site_id,
            Space.is_deleted == False
        ).options(
            joinedload(Space.building)
        )
        
        spaces = spaces_query.all()
        
        for space in spaces:
            spaces_response.append(SpaceDetailsResponse(
                space_id=space.id,
                space_name=space.name,
                building_id=space.building_block_id,
                building_name=space.building.name if space.building else None,
                is_owner=False,
                lease_contract_exist=False,
                lease_contract_detail=LeaseContractDetail(),
                maintenance_detail=MaintenanceDetail()
            ))
        
        ticket_filters = [Ticket.org_id == user.org_id]

        if account_type == UserAccountType.STAFF:
            ticket_filters.append(Ticket.assigned_to == user.user_id)
    # ------------------------------
    # Ticket filters
    # ------------------------------
    if params.site_id:
        ticket_filters.append(Ticket.site_id == params.site_id)
    if params.site_id and user.account_type != UserAccountType.STAFF:
        ticket_filters.append(Ticket.site_id == params.site_id)

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
        "period": Period(start=period_start, end=period_end)
    }

    notifications = (
        db.query(Notification)
        .filter(and_(Notification.user_id == user.user_id, Notification.read == False))
        .order_by(Notification.posted_date.desc())
        .limit(5)
        .all()
    )

    notification_list = [NotificationOut(**n.__dict__) for n in notifications]

    #  No chance of UnboundLocalError now
    return HomeDetailsWithSpacesResponse(
        spaces=spaces_response,
        statistics=statistics,
        notifications=notification_list or []
    )
