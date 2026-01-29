from datetime import date, datetime
from facility_service.app.models.leasing_tenants.tenant_spaces import TenantSpace
from facility_service.app.models.space_sites.space_owners import SpaceOwner
from facility_service.app.models.space_sites.user_sites import UserSite
from shared.models.users import Users
from shared.utils.enums import UserAccountType
from ...models.leasing_tenants.tenants import Tenant
from ...models.space_sites.spaces import Space
from ...models.space_sites.buildings import Building
# ✅ Import the Lease model (not Document)
from ...models.leasing_tenants.leases import Lease
from ...schemas.mobile_app.user_profile_schemas import MySpacesResponse, UserProfileResponse

from sqlalchemy.orm import Session, joinedload
from typing import Optional
from shared.core.schemas import UserToken


def get_user_profile_data(
    auth_db: Session,
    facility_db: Session,
    user: UserToken
) -> Optional[UserProfileResponse]:
    """
    Fetch and combine user profile information from Auth DB and Facility DB.
    Returns:
        UserProfileResponse with:
        - Personal details (from Auth DB)
        - Spaces (tenant + spaces + buildings)
        - Family members, vehicles, pets, and documents (from leases table)
    """

    # Fetch user from Auth DB
    user_data = (
        auth_db.query(Users)
        .filter(
            Users.id == user.user_id,
            Users.status == "active",
            Users.is_deleted == False
        )
        .first()
    )
    if not user_data:
        return None

    # Fetch tenant data from Facility DB
    tenants = (
        facility_db.query(Tenant)
        .filter(
            Tenant.user_id == user.user_id,
            Tenant.is_deleted == False,
            Tenant.status == 'active'
        )
        .all()
    )

    # Split user name
    full_name_parts = user_data.full_name.split(' ', 1)
    first_name = full_name_parts[0]
    last_name = full_name_parts[1] if len(full_name_parts) > 1 else ""

    # Prepare spaces list
    spaces = []
    for tenant in tenants:
        if not tenant.space_id:
            continue

        space = (
            facility_db.query(Space)
            .options(joinedload(Space.building))
            .filter(Space.id == tenant.space_id, Space.is_deleted == False)
            .first()
        )
        if not space:
            continue

        building_name = space.building.name if space.building else "Unknown Building"

        spaces.append({
            "space_id": str(space.id),
            "flat_number": tenant.flat_number or space.code or space.floor,
            "building": building_name,
        })

    # Prepare family members
    family_members = []
    for tenant in tenants:
        if tenant.family_info:
            if isinstance(tenant.family_info, dict):
                family_members.append(tenant.family_info)
            elif isinstance(tenant.family_info, list):
                family_members.extend(tenant.family_info)

    # Prepare vehicle details
    vehicle_details = []
    for tenant in tenants:
        if tenant.vehicle_info:
            if isinstance(tenant.vehicle_info, dict):
                vehicle_details.append(tenant.vehicle_info)
            elif isinstance(tenant.vehicle_info, list):
                vehicle_details.extend(tenant.vehicle_info)

    # ✅ Fetch documents from leases table (documents JSON column)
    lease_documents = (
        facility_db.query(Lease.documents)
        .filter(
            Lease.tenant_id.in_([tenant.id for tenant in tenants]),
            Lease.is_deleted == False
        )
        .all()
    )

    # Flatten list of JSON documents
    document_list = []
    for lease_doc in lease_documents:
        if lease_doc.documents:
            if isinstance(lease_doc.documents, dict):
                document_list.append(lease_doc.documents)
            elif isinstance(lease_doc.documents, list):
                document_list.extend(lease_doc.documents)

    # Construct final response
    return UserProfileResponse(
        first_name=first_name,
        last_name=last_name,
        picture_url=user_data.picture_url,
        phone=user_data.phone,
        email=user_data.email,
        spaces=spaces,
        family_members=family_members,
        vehicle_details=vehicle_details,
        pet_details=[],
        documents=document_list  # ✅ now fetched from leases table
    )


def get_my_spaces(db: Session, auth_db: Session, user: UserToken):
    """
    Get comprehensive home details for a specific space
    """
    account_type = user.account_type.lower()

    user_record = auth_db.query(Users).filter(
        Users.id == user.user_id,
        Users.is_deleted == False
    ).first()
    if user_record and user_record.created_at:
        period_start = user_record.created_at.date()

    spaces_response = []

    # ------------------------------
    # Tenant or Flat Owner flow
    # ------------------------
    if account_type in (UserAccountType.TENANT, UserAccountType.FLAT_OWNER):

        # Get all spaces for the site
        tenant_spaces_query = db.query(Space).join(
            TenantSpace, TenantSpace.space_id == Space.id
        ).join(Tenant, TenantSpace.tenant_id == Tenant.id).filter(
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

    # ------------------------------
    # Staff / Organisation flow

    else:
        # For staff/org users, show all spaces in site without owner/tenant details
        spaces_query = db.query(Space).filter(
            Space.is_deleted == False
        ).options(
            joinedload(Space.building)
            .joinedload(Space.site)
        )

        spaces = spaces_query.all()

        for space in spaces:
            spaces_response.append(MySpacesResponse(
                space_id=space.id,
                space_name=space.name,
                building_id=space.building_block_id,
                building_name=space.building.name if space.building else None,
                is_owner=False,
                lease_contract_exist=False,
                site_id=space.site.id,
                site_name=space.site.name,
            ))

    return spaces_response


def get_space_detail(
    db: Session,
    user: UserToken,
    space: Space
):
    space_is_owner = False
    space_lease_contract_exist = False

    # 1. CHECK IF USER IS SPACE OWNER
    space_owner = db.query(SpaceOwner).filter(
        SpaceOwner.space_id == space.id,
        SpaceOwner.owner_user_id == user.user_id
    ).first()

    tenant = db.query(Tenant).filter(
        Tenant.user_id == user.user_id,
        Tenant.is_deleted == False
    ).first()

    if space_owner:
        space_is_owner = True

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

        # Add space to response
    return MySpacesResponse(
        space_id=space.id,
        space_name=space.name,
        site_id=space.site.id,
        site_name=space.site.name,
        building_id=space.building_block_id,
        status=space_owner.status if space_is_owner else tenant_space.status,
        building_name=space.building.name if space.building else None,
        is_owner=space_is_owner,
        lease_contract_exist=space_lease_contract_exist,
    )
