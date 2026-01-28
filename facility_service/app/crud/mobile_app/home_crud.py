from operator import or_
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, and_, distinct, case
from sqlalchemy.dialects.postgresql import UUID
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional

from auth_service.app.models.user_organizations import UserOrganization
from facility_service.app.models.space_sites.user_sites import UserSite
from facility_service.app.schemas.mobile_app.user_profile_schemas import MySpacesResponse
from shared.helpers.json_response_helper import error_response
from shared.utils.app_status_code import AppStatusCode
from ...schemas.access_control.user_management_schemas import UserOrganizationOut
from shared.models.users import Users
from ...enum.space_sites_enum import OwnershipType
from ...models.space_sites.owner_maintenances import OwnerMaintenanceCharge
from ...models.space_sites.orgs import Org
from ...models.space_sites.space_owners import SpaceOwner
from ...schemas.mobile_app.home_schemas import AddSpaceRequest, HomeDetailsWithSpacesResponse, LeaseContractDetail, MaintenanceDetail, Period, SpaceDetailsResponse

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
from shared.utils.enums import OwnershipStatus, UserAccountType


def get_home_sites(db: Session, auth_db: Session, user: UserToken):
    sites = []
    account_type = user.account_type.lower()

    if account_type in (UserAccountType.TENANT, UserAccountType.FLAT_OWNER):

        sites = []

        user_sites = (
            db.query(UserSite)
            .join(Site, UserSite.site_id == Site.id)
            .options(
                joinedload(UserSite.site)
                .joinedload(Site.org)
            )
            .filter(
                UserSite.user_id == user.user_id
            )
            .all()
        )

        for us in user_sites:
            site = us.site
            if not site:
                continue

            sites.append({
                "site_id": site.id,
                "site_name": site.name,
                "is_primary": us.is_primary,
                "org_id": site.org_id,
                "org_name": site.org.name if site.org else None,
                "address": site.address
            })

    elif account_type == UserAccountType.STAFF:
        staff_sites = (
            db.query(StaffSite, UserSite.is_primary)
            .join(
                UserSite,
                (UserSite.user_id == StaffSite.user_id) &
                (UserSite.site_id == StaffSite.site_id)
            )
            .options(
                joinedload(StaffSite.site)
                .joinedload(Site.org)
            )
            .filter(StaffSite.user_id == user.user_id)
            .all()
        )
        for staff_site, is_primary in staff_sites:
            site = staff_site.site

            sites.append({
                "site_id": site.id,
                "site_name": site.name,
                "is_primary": is_primary,   # ✅ from user_sites
                "org_id": site.org_id,
                "org_name": site.org.name if site.org else None,
                "address": site.address,
            })

    else:
        sites_records = (
            db.query(Site)
            .filter(Site.org_id == user.org_id)
            .all()
        )
        for idx, staff_site in enumerate(sites_records):
            sites.append({
                "site_id": site.id,
                "site_name": site.name,
                "is_primary": idx == 0,
                "org_id": site.org_id,
                "org_name": site.org.name if site.org else None,
                "address": site.address,
            })

    user_orgs = (
        auth_db.query(UserOrganization)
        .filter(
            UserOrganization.user_id == user.user_id,
            UserOrganization.is_deleted == False
        )
        .order_by(
            UserOrganization.is_default.desc(),
            UserOrganization.joined_at.asc()
        )
        .all()
    )

    default_user_org = user_orgs[0] if user_orgs else None

    current_user = (
        auth_db.query(Users)
        .filter(
            Users.id == user.user_id,
            Users.is_deleted == False
        )
        .first()
    )

    org_ids = [org.org_id for org in user_orgs]

    org_map = {
        org.id: org.name
        for org in db.query(Org)
        .filter(Org.id.in_(org_ids))
        .all()
    }

    account_types = [
        UserOrganizationOut.model_validate({
            "user_org_id": org.id,
            "org_id": org.org_id,
            "account_type": org.account_type,
            "organization_name": org_map.get(org.org_id),
            "is_default": org.is_default,
            "status": org.status
        })
        for org in user_orgs
    ]

    return {
        "sites": sites,
        "default_account_type": default_user_org.account_type,
        "status": current_user.status,
        "account_types": account_types
    }


def get_home_details(db: Session, auth_db: Session, params: MasterQueryParams, user: UserToken):
    """
    Get comprehensive home details for a specific space
    """
    now = datetime.now(timezone.utc)
    account_type = user.account_type.lower()
    tenant_type = user.tenant_type.lower() if user.tenant_type else None
    period_end = date.today()

    user_record = auth_db.query(Users).filter(
        Users.id == user.user_id,
        Users.is_deleted == False
    ).first()
    if user_record and user_record.created_at:
        period_start = user_record.created_at.date()

    # make the current site as primary
    with db.begin():
        db.query(UserSite).filter(
            UserSite.user_id == user.user_id,
            UserSite.is_primary == True
        ).update(
            {"is_primary": False},
            synchronize_session=False
        )

        db.query(UserSite).filter(
            UserSite.user_id == user.user_id,
            UserSite.site_id == params.site_id
        ).update(
            {"is_primary": True},
            synchronize_session=False
        )

    spaces_response = []

    # ------------------------------
    # Tenant or Flat Owner flow
    # ------------------------
    if account_type in (UserAccountType.TENANT, UserAccountType.FLAT_OWNER):
        print("Tenant Type :", tenant_type)

        # Get all spaces for the site
        tenant_spaces_query = db.query(Space).join(
            TenantSpace, TenantSpace.space_id == Space.id
        ).join(Tenant, TenantSpace.tenant_id == Tenant.id).filter(
            TenantSpace.site_id == params.site_id,
            TenantSpace.is_deleted == False,
            Tenant.user_id == user.user_id,
            TenantSpace.status.in_(["occupied", "pending"])
        ).options(
            joinedload(Space.building),
            joinedload(Space.site)
        )
        owner_spaces_query = db.query(Space).join(
            SpaceOwner, SpaceOwner.space_id == Space.id
        ).filter(
            Space.site_id == params.site_id,
            SpaceOwner.is_active == True,
            SpaceOwner.owner_user_id == user.user_id
        ).options(
            joinedload(Space.building),
            joinedload(Space.site)
        )
        tenant_spaces = tenant_spaces_query.all()
        owner_spaces = owner_spaces_query.all()
        spaces = tenant_spaces + owner_spaces

        # Get tenant record
        tenant = db.query(Tenant).filter(
            Tenant.user_id == user.user_id,
            Tenant.is_deleted == False
        ).first()

        # Process each space
        for space in spaces:
            space_detail = get_space_detail(db, user, space)

            # Add space to response
            spaces_response.append(space_detail)

        # Set ticket filters for tenant/owner
        tenant_id = tenant.id if tenant else None
        if tenant_id:
            ticket_filters = [Ticket.tenant_id == tenant_id]
        elif account_type == UserAccountType.FLAT_OWNER:
            # For FLAT_OWNER, show tickets for spaces they own
            owned_space_ids = [
                s.space_id for s in spaces_response if s.is_owner]
            if owned_space_ids:
                ticket_filters = [Ticket.space_id.in_(owned_space_ids)]
            else:
                ticket_filters = []  # No spaces owned, no tickets
        else:
            ticket_filters = []

    # ------------------------------
    # Staff / Organisation flow

    else:
        # For staff/org users, show all spaces in site without owner/tenant details
        spaces_query = db.query(Space).filter(
            Space.site_id == params.site_id,
            Space.is_deleted == False
        ).options(
            joinedload(Space.building)
            .joinedload(Space.site)
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


def register_space(
        params: AddSpaceRequest,
        facility_db: Session,
        user: UserToken):

    now = datetime.utcnow()

    # ✅ Find site
    site = facility_db.query(Site).filter(
        Site.id == params.site_id).first()
    if not site:
        return error_response(
            message="Invalid site selected",
            status_code=str(AppStatusCode.INVALID_INPUT),
        )

    if not params.space_id:
        return error_response(
            message="Space required for tenant",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
        )

    space = facility_db.query(Space).filter(
        Space.id == params.space_id,
        Space.is_deleted == False
    ).options(
        joinedload(Space.building),
        joinedload(Space.site)
    ).first()

    if params.account_type.lower() == "owner":
        # ➕ Insert new
        facility_db.add(
            SpaceOwner(
                owner_user_id=user.user_id,
                space_id=user.space_id,
                owner_org_id=site.org_id,
                ownership_type="primary",
                status=OwnershipStatus.requested,
                is_active=False,
                start_date=now
            )
        )

    elif params.account_type.lower() == "tenant":

        existing_tenant = facility_db.query(TenantSpace).filter(
            and_(
                TenantSpace.space_id == user.space_id,
                TenantSpace.status == "occupied",
                TenantSpace.is_deleted == False)
        ).first()

        if existing_tenant:
            return error_response(
                message="Tenant already registered for selected space",
                status_code=str(AppStatusCode.USER_ALREADY_REGISTERED),
            )

        tenant_obj = (
            facility_db.query(Tenant)
            .filter(Tenant.user_id == user.user_id, Tenant.is_deleted == False)
            .first()
        )

        # ✅ Create space tenant link
        space_tenant_link = TenantSpace(
            site_id=params.site_id,
            space_id=params.space_id,
            tenant_id=tenant_obj.id,
            status="pending"
        )
        facility_db.add(space_tenant_link)

    facility_db.commit()

    # RESPONSE
    space_is_owner = False
    space_lease_contract_exist = False

    # 1. CHECK IF USER IS SPACE OWNER
    space_owner = facility_db.query(SpaceOwner).filter(
        SpaceOwner.space_id == space.id,
        SpaceOwner.owner_user_id == user.user_id,
        SpaceOwner.is_active == True
    ).first()

    if space_owner:
        space_is_owner = True

        # 2. CHECK IF USER IS TENANT (for lease contract)
    if tenant_obj and not space_is_owner:
        # Check if tenant has access to this space
        tenant_space = facility_db.query(TenantSpace).filter(
            TenantSpace.tenant_id == tenant_obj.id,
            TenantSpace.space_id == space.id,
            TenantSpace.is_deleted == False
        ).first()

        if tenant_space:
            # Get lease for this space
            lease_query = facility_db.query(Lease).filter(
                Lease.space_id == space.id,
                Lease.tenant_id == tenant_obj.id,
                Lease.is_deleted == False,
                Lease.end_date >= date.today()
            )

            lease = lease_query.order_by(Lease.end_date.desc()).first()

            # Fallback to most recent if no active lease
            if not lease:
                lease_query = facility_db.query(Lease).filter(
                    Lease.space_id == space.id,
                    Lease.tenant_id == tenant_obj.id,
                    Lease.is_deleted == False
                )
                lease = lease_query.order_by(
                    Lease.end_date.desc()).first()

            if lease:
                space_lease_contract_exist = True

        # Add space to response
    return MySpacesResponse(
        space_id=space.id,
        space_name=space.name,
        site_id=space.site.id,
        site_name=space.site.name,
        building_id=space.building_block_id,
        status=space.status,
        building_name=space.building.name if space.building else None,
        is_owner=space_is_owner,
        lease_contract_exist=space_lease_contract_exist,
    )


def get_space_detail(
    db: Session,
    user: UserToken,
    space: Space
):
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

    tenant = db.query(Tenant).filter(
        Tenant.user_id == user.user_id,
        Tenant.is_deleted == False
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
            space_maintenance_detail.total_maintenance_paid = float(
                total_maint_paid)

        # 2. CHECK IF USER IS TENANT (for lease contract)
    if tenant and not space_is_owner:
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
                lease = lease_query.order_by(
                    Lease.end_date.desc()).first()

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
                        next_rent_due = period.period_end + \
                            timedelta(days=1)
                        break
                    elif period.period_end <= current_date:
                        last_rent_paid = period.period_end
                        next_rent_due = period.period_end + \
                            timedelta(days=1)
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

        # Add space to response
    return SpaceDetailsResponse(
        space_id=space.id,
        space_name=space.name,
        building_id=space.building_block_id,
        status=space_owner.status if space_is_owner else tenant_space.status,
        building_name=space.building.name if space.building else None,
        is_owner=space_is_owner,
        lease_contract_exist=space_lease_contract_exist,
        lease_contract_detail=space_lease_contract_detail,
        maintenance_detail=space_maintenance_detail
    )
