from auth_service.app.models.users import Users as AuthUser
from ...models.leasing_tenants.tenants import Tenant
from ...models.space_sites.spaces import Space
from ...models.space_sites.buildings import Building
from ...models.leasing_tenants.leases import Lease  # ✅ Import the Lease model (not Document)
from ...schemas.mobile_app.user_profile_schemas import UserProfileResponse

from sqlalchemy.orm import Session, joinedload
from typing import Optional
from shared.schemas import UserToken


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
        auth_db.query(AuthUser)
        .filter(
            AuthUser.id == user.user_id,
            AuthUser.status == "active",
            AuthUser.is_deleted == False
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
            "is_primary": False
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
