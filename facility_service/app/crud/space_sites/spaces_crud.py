from sqlite3 import IntegrityError
import uuid
from typing import List, Optional
from datetime import date, datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, cast, or_, case, literal
from sqlalchemy.dialects.postgresql import UUID

from auth_service.app.models.user_organizations import UserOrganization
from facility_service.app.crud.space_sites.space_occupancy_crud import log_occupancy_event
from facility_service.app.models.space_sites.space_occupancies import OccupantType
from facility_service.app.models.space_sites.space_occupancy_events import OccupancyEventType
from ...crud.access_control.user_management_crud import handle_account_type_update, upsert_user_sites_preserve_primary
from ...schemas.access_control.user_management_schemas import UserAccountCreate, UserTenantSpace
from ...models.space_sites.space_owners import OwnershipStatus, SpaceOwner
from shared.models.users import Users

from ...models.leasing_tenants.tenant_spaces import TenantSpace
from shared.core.schemas import CommonQueryParams, UserToken
from shared.helpers.property_helper import get_allowed_spaces
from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response, success_response
from shared.utils.enums import UserAccountType

from ...models.leasing_tenants.tenants import Tenant
from ...models.space_sites.buildings import Building
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...models.leasing_tenants.leases import Lease
from ...schemas.space_sites.spaces_schemas import ActiveOwnerResponse, AssignSpaceOwnerIn, AssignSpaceOwnerOut, AssignSpaceTenantIn, OwnershipHistoryOut, SpaceCreate, SpaceListResponse, SpaceOut, SpaceRequest, SpaceUpdate, TenantHistoryOut

# ----------------------------------------------------------------------
# CRUD OPERATIONS
# ----------------------------------------------------------------------


def build_space_filters(org_id: UUID, params: SpaceRequest):
    # Always filter out deleted spaces
    filters = [Space.org_id == org_id,
               Space.is_deleted == False]  # Updated filter

    if params.site_id and params.site_id.lower() != "all":
        filters.append(Space.site_id == params.site_id)

    if params.kind and params.kind.lower() != "all":
        filters.append(Space.kind == params.kind)

    if params.status and params.status.lower() != "all":
        filters.append(Space.status == params.status)

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(Space.name.ilike(search_term),
                       Space.code.ilike(search_term)))

    return filters


def get_space_query(db: Session, org_id: UUID, params: SpaceRequest):
    filters = build_space_filters(org_id, params)
    return db.query(Space).filter(*filters)


def get_spaces_overview(db: Session, user: UserToken, params: SpaceRequest):
    filters = build_space_filters(user.org_id, params)

    allowed_space_ids = None
    if user.account_type.lower() == UserAccountType.TENANT:
        allowed_spaces = get_allowed_spaces(db, user)
        allowed_space_ids = [s["space_id"] for s in allowed_spaces]

        if not allowed_space_ids:
            return {
                "totalSpaces": 0,
                "availableSpaces": 0,
                "occupiedSpaces": 0,
                "outOfServices": 0
            }
    counts = (
        db.query(
            func.count(Space.id).label("total_spaces"),
            func.count(case((Space.status == "available", 1))
                       ).label("available_spaces"),
            func.count(case((Space.status == "occupied", 1))
                       ).label("occupied_spaces"),
            func.count(case((Space.status == "out_of_service", 1))
                       ).label("out_of_service"),
        )
        .filter(*filters)
    )
    if allowed_space_ids is not None:
        counts = counts.filter(Space.id.in_(allowed_space_ids))

    counts = counts.one()

    return {
        "totalSpaces": counts.total_spaces,
        "availableSpaces": counts.available_spaces,
        "occupiedSpaces": counts.occupied_spaces,
        "outOfServices": counts.out_of_service
    }


def get_spaces(db: Session, user: UserToken, params: SpaceRequest) -> SpaceListResponse:
    allowed_space_ids = None

    if user.account_type.lower() == UserAccountType.TENANT.value or user.account_type.lower() == UserAccountType.FLAT_OWNER.value:
        allowed_spaces = get_allowed_spaces(db, user)
        allowed_space_ids = [s["space_id"] for s in allowed_spaces]

        if not allowed_space_ids:
            return {"spaces": [], "total": 0}

    base_query = get_space_query(db, user.org_id, params)

    # APPLY TENANT FILTER HERE
    if allowed_space_ids is not None:
        base_query = base_query.filter(Space.id.in_(allowed_space_ids))

    query = (
        base_query
        .join(Site, Space.site_id == Site.id)
        .outerjoin(Building, Space.building_block_id == Building.id)
        .add_columns(Building.name.label("building_block_name"), Site.name.label("site_name"))
    )
    total = db.query(func.count()).select_from(query.subquery()).scalar()

    spaces = (
        query
        .order_by(Space.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    results = []
    for row in spaces:
        space = row[0]                     # Space object
        building_name = row.building_block_name  # Joined building name
        site_name = row.site_name              # Joined site name

        data = {
            **space.__dict__,
            "building_block": building_name,
            "site_name": site_name
        }
        results.append(SpaceOut.model_validate(data))

    return {"spaces": results, "total": total}


def get_space_by_id(db: Session, space_id: str) -> Optional[Space]:
    # Updated filter
    return db.query(Space).filter(Space.id == space_id, Space.is_deleted == False).first()


def create_space(db: Session, space: SpaceCreate):
    try:
        # Check for duplicate space code within the same building (case-insensitive)
        if space.building_block_id:
            existing_space = db.query(Space).filter(
                and_(Space.building_block_id == space.building_block_id,
                     Space.is_deleted == False,
                     # Case-insensitive code within same building
                     or_(func.lower(Space.code) == func.lower(space.code),
                         func.lower(Space.name) == func.lower(space.name))
                     )).first()

        else:
            existing_space = db.query(Space).filter(
                and_(or_(func.lower(Space.name) == func.lower(space.name),
                         func.lower(Space.code) == func.lower(space.code)),
                     Space.is_deleted == False,
                     )).first()

        if existing_space:
            return error_response(
                message=f"Space with code/name already exists ",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )

        # Create space - exclude building_block
        space.building_block_id = space.building_block_id if space.building_block_id else None
        space_data = space.model_dump(exclude={"building_block"})
        db_space = Space(**space_data)
        db.add(db_space)
        db.commit()
        db.refresh(db_space)
        return db_space
    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def update_space(db: Session, space: SpaceUpdate):
    db_space = get_space_by_id(db, space.id)
    if not db_space:
        return error_response(
            message="Space not found",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=404
        )

    update_data = space.model_dump(
        exclude_unset=True, exclude={"building_block"})
    # Convert empty UUID strings to None---------------------changed
    for field in ["building_block_id"]:
        if update_data.get(field) == "":
            update_data[field] = None
    # Check if trying to update site or building when tenants/leases exist
    site_changed = (
        "site_id" in update_data
        and update_data["site_id"] != db_space.site_id
    )

    building_changed = (
        "building_block_id" in update_data
        and db_space.building_block_id is not None
        and update_data["building_block_id"] != db_space.building_block_id
    )

    if site_changed or building_changed:
        # Check if space has any active tenants
        has_tenants = (
            db.query(TenantSpace).filter(
                TenantSpace.space_id == space.id,
                TenantSpace.status == 'current',
                TenantSpace.is_deleted == False
            ).first()
        )

        # Check if space has any active leases
        has_leases = db.query(Lease).filter(
            Lease.space_id == space.id,
            Lease.is_deleted == False,
            func.lower(Lease.status) == func.lower('active')
        ).first()

        if has_tenants or has_leases:
            return error_response(
                message="Cannot update site or building for a space that has tenants or leases"
            )
    building_id = update_data.get(
        "building_block_id", db_space.building_block_id)

    if building_id:
        existing_space = db.query(Space).filter(
            and_(Space.building_block_id == building_id,
                 Space.is_deleted == False,
                 Space.id != space.id,
                 or_(
                     func.lower(Space.code) == func.lower(
                         update_data.get("code", "")),
                     func.lower(Space.name) == func.lower(
                         update_data.get("name", ""))
                 )
                 )).first()

    else:
        existing_space = db.query(Space).filter(
            and_(
                or_(
                    func.lower(Space.code) == func.lower(
                        update_data.get("code", "")),
                    func.lower(Space.name) == func.lower(
                        update_data.get("name", ""))
                ),
                Space.is_deleted == False,
                Space.id != space.id
            )
        ).first()

    if existing_space:
        return error_response(
            message=f"Space with code/name already exists ",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )

    # Update space
    for key, value in update_data.items():
        setattr(db_space, key, value)

    try:
        db.commit()
        db.refresh(db_space)

        # Joined building name ------changed
        building_name = db_space.building.name if db_space.building_block_id else None
        site_name = db_space.site.name if db_space.site_id else None
        data = {
            **db_space.__dict__,
            "building_block": building_name,
            "site_name": site_name
        }

        return SpaceOut.model_validate(data)
    except IntegrityError as e:
        db.rollback()
        return error_response(
            message="Error updating space",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def get_space_details_by_id(
        db: Session,
        space_id: str) -> Optional[SpaceOut]:
    db_space = (
        db.query(Space)
        .join(Site, Space.site_id == Site.id)
        .outerjoin(Building, Space.building_block_id == Building.id)
        .add_columns(Building.name.label("building_block_name"), Site.name.label("site_name"))
        .filter(Space.id == space_id, Space.is_deleted == False)
        .first()
    )

    if not db_space:
        return None

    space = db_space[0]  # Space object
    building_name = db_space.building_block_name  # Joined building name
    site_name = db_space.site_name  # Joined site name

    data = {
        **space.__dict__,
        "building_block": building_name,
        "site_name": site_name
    }

    return SpaceOut.model_validate(data)


def delete_space(db: Session, space_id: str) -> Optional[Space]:
    try:
        db_space = get_space_by_id(db, space_id)
        if not db_space:
            return None

        # Check if there are any ACTIVE tenants associated with this space
        active_tenants = (
            db.query(TenantSpace)
            .filter(
                TenantSpace.space_id == space_id,
                TenantSpace.is_deleted == False,
                TenantSpace.status == "current"  # Active status tenants
            )
            .first()
        )

        # Check if there are any ACTIVE leases associated with this space
        active_leases = (
            db.query(Lease)
            .filter(
                Lease.space_id == space_id,
                Lease.is_deleted == False,
                Lease.status.in_(["active", "pending"])  # Active status leases
            )
            .first()
        )

        if active_tenants or active_leases:
            raise error_response(
                message="Cannot delete space that has active tenants or leases associated with it."
            )

        # Soft delete - set is_deleted to True instead of actually deleting
        db_space.is_deleted = True
        db_space.updated_at = func.now()
        db.commit()
        db.refresh(db_space)
        return db_space
    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def get_space_lookup(db: Session, site_id: str, building_id: str, user: UserToken):
    allowed_space_ids = None

    if user.account_type.lower() == UserAccountType.TENANT:
        allowed_spaces = get_allowed_spaces(db, user)
        allowed_space_ids = [s["space_id"] for s in allowed_spaces]

        if not allowed_space_ids:
            return {"spaces": [], "total": 0}
    space_query = (
        db.query(
            Space.id,
            Space.name
        )
        .join(Site, Space.site_id == Site.id)
        .outerjoin(Building, Space.building_block_id == Building.id)
        .filter(
            Space.is_deleted == False,
            Site.is_deleted == False,
            Site.status == "active"
        )
        .order_by(Space.name.asc())
    )

    if allowed_space_ids is not None:
        space_query = space_query.filter(Space.id.in_(allowed_space_ids))
    else:
        space_query = space_query.filter(Space.org_id == user.org_id)

    if site_id and site_id.lower() != "all":
        space_query = space_query.filter(Space.site_id == site_id)

    if building_id and building_id.lower() != "all":
        space_query = space_query.filter(
            Space.building_block_id == building_id)

    return space_query.all()


def get_space_with_building_lookup(db: Session, site_id: str, org_id: str):
    space_query = (
        db.query(
            Space.id,
            func.concat(Building.name, literal(
                " - "), Space.name).label("name")
        )
        .join(Site, Space.site_id == Site.id)
        .outerjoin(Building, Space.building_block_id == Building.id)
        # Updated filter
        .filter(Site.is_deleted == False, Site.status == "active",
                Space.org_id == org_id, Space.is_deleted == False,
                Building.is_deleted == False, Building.status == "active")
        .order_by(Space.name.asc())
    )

    if site_id and site_id.lower() != "all":
        space_query = space_query.filter(Space.site_id == site_id)

    return space_query.all()


def get_space_master_lookup(db: Session, site_id: str, building_id: str):
    space_query = (
        db.query(
            Space.id,
            Space.name
        )
        .join(Site, Space.site_id == Site.id)
        .outerjoin(Building, Space.building_block_id == Building.id)
        .filter(Space.is_deleted == False,
                Site.is_deleted == False,
                Site.status == "active",
                Building.is_deleted == False,
                Building.status == "active"
                )
        .order_by(Space.name.asc())
    )

    if site_id and site_id.lower() != "all":
        space_query = space_query.filter(Space.site_id == site_id)

    if building_id and building_id.lower() != "all":
        space_query = space_query.filter(
            Space.building_block_id == building_id)

    return space_query.all()


def get_active_owners(
    db: Session,
    auth_db: Session,
    space_id: UUID
):
    owners = (
        db.query(SpaceOwner)
        .filter(
            SpaceOwner.space_id == space_id,
            SpaceOwner.is_active == True,
            SpaceOwner.status == OwnershipStatus.approved
        )
        .all()
    )

    user_ids = [
        o.owner_user_id
        for o in owners
        if o.owner_user_id
    ]

    users_map = {}
    if user_ids:
        users = (
            auth_db.query(Users.id, Users.full_name)
            .filter(Users.id.in_(user_ids))
            .all()
        )
        users_map = {
            u.id: u.full_name or ""
            for u in users
        }

    result = []

    for o in owners:
        if o.owner_user_id:
            result.append(
                ActiveOwnerResponse(
                    id=o.id,
                    owner_type="user",
                    user_id=o.owner_user_id,
                    full_name=users_map.get(o.owner_user_id, ""),
                    ownership_percentage=o.ownership_percentage,
                    start_date=o.start_date,
                )
            )

    return result


def assign_space_owner(
    db: Session,
    auth_db: Session,
    org_id: UUID,
    payload: AssignSpaceOwnerIn
):
    try:
        #  Validate space
        space = (
            db.query(Space)
            .filter(
                Space.id == payload.space_id,
                Space.org_id == org_id,
                Space.is_deleted == False
            )
            .first()
        )

        if not space:
            raise error_response(message="Space not found")

        user = auth_db.query(Users).filter(
            Users.id == payload.owner_user_id,
            Users.is_deleted == False
        ).first()

        if not user:
            raise error_response(message="User not found")

        # ADD THIS: CREATE / REVIVE USER_ORGANIZATION OWNER ENTRY
        user_org = auth_db.query(UserOrganization).filter(
            UserOrganization.user_id == payload.owner_user_id,
            UserOrganization.org_id == org_id,
            UserOrganization.account_type == UserAccountType.FLAT_OWNER.value
        ).first()

        if user_org:
            user_org.status = "active"
            user_org.is_deleted = False
        else:
            user_org = UserOrganization(
                user_id=payload.owner_user_id,
                org_id=org_id,
                status="inactive",
                account_type=UserAccountType.FLAT_OWNER.value,
                is_deleted=False
            )

        owner_spaces = []
        owner_spaces.append(
            UserTenantSpace(
                site_id=space.site_id,
                space_id=payload.space_id
            )
        )

        user_account = UserAccountCreate(
            user_id=payload.owner_user_id,
            status="active",
            account_type=UserAccountType.FLAT_OWNER.value,
            owner_spaces=owner_spaces
        )

        error = handle_account_type_update(
            facility_db=db,
            db_user=user,
            user_account=user_account,
            org_id=org_id
        )

        if error:
            return error

        db.commit()
        auth_db.add(user_org)
        auth_db.commit()

        return success_response(data=None, message="request submitted successfully")
    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        auth_db.rollback
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def assign_space_tenant(
    db: Session,
    auth_db: Session,
    org_id: UUID,
    payload: AssignSpaceTenantIn
):
    try:
        now = datetime.utcnow()
        #  Validate space
        space = (
            db.query(Space)
            .filter(
                Space.id == payload.space_id,
                Space.org_id == org_id,
                Space.is_deleted == False
            )
            .first()
        )

        if not space:
            raise error_response(message="Space not found")

        tenant_space_owner = (
            db.query(SpaceOwner)
            .filter(
                SpaceOwner.space_id == payload.space_id,
                SpaceOwner.owner_user_id == payload.tenant_user_id,
                SpaceOwner.status == OwnershipStatus.approved
            )
            .first()
        )

        if tenant_space_owner:
            raise error_response(
                message="Space owner cannot be assigned as tenant.")

        user = auth_db.query(Users).filter(
            Users.id == payload.tenant_user_id,
            Users.is_deleted == False
        ).first()

        if not user:
            raise error_response(message="User not found")

        # ADD THIS: CREATE / REVIVE USER_ORGANIZATION OWNER ENTRY
        user_org = auth_db.query(UserOrganization).filter(
            UserOrganization.user_id == payload.tenant_user_id,
            UserOrganization.org_id == org_id,
            UserOrganization.account_type == UserAccountType.TENANT.value
        ).first()

        if user_org:
            user_org.status = "active"
            user_org.is_deleted = False
        else:
            user_org = UserOrganization(
                user_id=payload.tenant_user_id,
                org_id=org_id,
                status="inactive",
                account_type=UserAccountType.TENANT.value,
                is_deleted=False
            )

        tenant_spaces = []
        tenant_spaces.append(
            UserTenantSpace(
                site_id=space.site_id,
                space_id=payload.space_id
            )
        )

        user_account = UserAccountCreate(
            user_id=payload.tenant_user_id,
            status="active",
            account_type=UserAccountType.TENANT.value,
            tenant_spaces=tenant_spaces
        )

        error = handle_account_type_update(
            facility_db=db,
            db_user=user,
            user_account=user_account,
            org_id=org_id
        )

        if error:
            return error

        db.commit()
        auth_db.add(user_org)
        auth_db.commit()

        return success_response(data=None, message="request submitted successfully")
    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        auth_db.rollback
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def get_space_ownership_history(
    db: Session,
    auth_db: Session,
    space_id: UUID,
    org_id: UUID
):
    # Validate space
    space = (
        db.query(Space)
        .filter(
            Space.id == space_id,
            Space.org_id == org_id,
            Space.is_deleted == False
        )
        .first()
    )

    if not space:
        return error_response(message="Space not found")

    owners = (
        db.query(SpaceOwner)
        .filter(SpaceOwner.space_id == space_id, SpaceOwner.is_active == True)
        .order_by(SpaceOwner.start_date.desc())
        .all()
    )

    response = []

    for owner in owners:
        owner_name = None

        if owner.owner_user_id:
            user = (
                auth_db.query(Users)
                .filter(Users.id == owner.owner_user_id)
                .first()
            )
            owner_name = user.full_name if user else None

        response.append(
            OwnershipHistoryOut(
                id=owner.id,
                owner_user_id=owner.owner_user_id,
                owner_name=owner_name,
                ownership_type=owner.ownership_type,
                ownership_percentage=owner.ownership_percentage,
                start_date=owner.start_date,
                end_date=owner.end_date,
                is_active=owner.is_active,
                status=owner.status
            )
        )

    return response


def get_space_tenant_history(
    db: Session,
    auth_db: Session,
    space_id: UUID,
    org_id: UUID
):
    # Validate space
    space = (
        db.query(Space)
        .filter(
            Space.id == space_id,
            Space.org_id == org_id,
            Space.is_deleted == False
        )
        .first()
    )

    if not space:
        return error_response(message="Space not found")

    space_tenants = (
        db.query(
            TenantSpace,
            Lease.lease_number,
            Lease.status.label("lease_status")
        )
        .outerjoin(
            Lease,
            and_(
                Lease.space_id == TenantSpace.space_id,
                Lease.tenant_id == TenantSpace.tenant_id,
                Lease.is_deleted == False
            )
        )
        .filter(
            TenantSpace.space_id == space_id,
            TenantSpace.is_deleted == False
        )
        .order_by(TenantSpace.created_at.desc())
        .all()
    )

    response = []

    for tenant_space, lease_no, lease_status in space_tenants:
        if lease_status == "active":
            response.append(
                TenantHistoryOut(
                    id=tenant_space.id,
                    tenant_user_id=tenant_space.tenant.user_id,
                    tenant_name=tenant_space.tenant.name,
                    start_date=tenant_space.created_at.date() if tenant_space.created_at else None,
                    lease_no=lease_no,
                    is_active=True if tenant_space.tenant.status == "active" else False,
                    status=tenant_space.status
                )
            )

    return response


def get_pending_space_owner_requests(
    db: Session,
    auth_db: Session,
    org_id: UUID,
    params: CommonQueryParams
):
    base_query = (
        db.query(SpaceOwner)
        .join(Space, SpaceOwner.space_id == Space.id)
        .filter(
            SpaceOwner.owner_org_id == org_id,
            SpaceOwner.status == OwnershipStatus.pending
        )
    )
    if params.search:
        search_term = f"%{params.search}%"
        base_query.filter(or_(Space.name.ilike(search_term),
                              Space.code.ilike(search_term)))

    total = base_query.count()

    requests = (
        base_query
        .order_by(SpaceOwner.requested_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    response = []

    for owner in requests:
        owner_name = None

        if owner.owner_user_id:
            user = (
                auth_db.query(Users)
                .filter(Users.id == owner.owner_user_id)
                .first()
            )
            owner_name = user.full_name if user else None

        response.append(
            OwnershipHistoryOut(
                id=owner.id,
                owner_user_id=owner.owner_user_id,
                owner_name=owner_name,
                ownership_type=owner.ownership_type,
                ownership_percentage=owner.ownership_percentage,
                start_date=owner.start_date,
                end_date=owner.end_date,
                is_active=owner.is_active,
                space_id=owner.space.id,
                space_name=owner.space.name,
                status=owner.status
            )
        )

    return {
        "requests": response,
        "total": total
    }


def update_space_owner_approval(
    db: Session,
    auth_db: Session,
    request_id: UUID,
    action: OwnershipStatus,
    org_id: UUID
):
    try:
        owner = (
            db.query(SpaceOwner)
            .filter(
                SpaceOwner.id == request_id
            )
            .first()
        )

        if not owner:
            return error_response(message="Ownership request not found")

        space = db.query(Space).filter(
            Space.id == owner.space_id,
            Space.is_deleted == False
        ).first()

        if action == OwnershipStatus.approved:
            existing_assignments = db.query(SpaceOwner).filter(
                SpaceOwner.space_id == owner.space_id,
                SpaceOwner.is_active == True
            ).all()

            #  DIFFERENT OWNER → CLOSE PREVIOUS ENTRY
            for ts in existing_assignments:
                if ts.owner_user_id != owner.owner_user_id:
                    ts.is_active = False
                    ts.end_date = date.today()

                    other_spaces_count = (
                        db.query(SpaceOwner)
                        .filter(
                            SpaceOwner.space_id != ts.space_id,
                            SpaceOwner.owner_user_id == ts.owner_user_id,
                            SpaceOwner.owner_org_id == org_id,
                            SpaceOwner.is_active == True
                        )
                        .count()
                    )

                    #  SOFT DELETE OLD OWNER ACCOUNT ORG ENTRY
                    if other_spaces_count == 0:
                        old_user_org = auth_db.query(UserOrganization).filter(
                            UserOrganization.user_id == ts.owner_user_id,
                            UserOrganization.org_id == org_id,
                            UserOrganization.account_type == "owner",
                            UserOrganization.is_deleted == False
                        ).first()

                        if old_user_org:
                            old_user_org.is_deleted = True
                            old_user_org.status = "inactive"

            # Ensure only one primary owner
            if owner.ownership_type == "primary":
                db.query(SpaceOwner).filter(
                    SpaceOwner.space_id == owner.space_id,
                    SpaceOwner.ownership_type == "primary",
                    SpaceOwner.is_active == True,
                    SpaceOwner.id != owner.id
                ).update({
                    SpaceOwner.is_active: False,
                    SpaceOwner.status: OwnershipStatus.revoked
                })

            owner.status = OwnershipStatus.approved
            owner.is_active = True

            auth_db.query(UserOrganization).filter(
                UserOrganization.user_id == owner.owner_user_id,
                UserOrganization.org_id == org_id,
                UserOrganization.account_type == "owner",
                UserOrganization.is_deleted == False
            ).update({
                UserOrganization.status: "active"
            })

            site_ids = [space.site_id]

            log_occupancy_event(
                db=db,
                space_id=owner.space_id,
                occupant_type=OccupantType.owner,
                occupant_user_id=owner.owner_user_id,
                event_type=OccupancyEventType.owner_approved,
                source_id=owner.owner_user_id,
                notes="Owner request for the space was approved"
            )

            upsert_user_sites_preserve_primary(
                db=db,
                user_id=owner.owner_user_id,
                site_ids=site_ids
            )

        else:
            owner.status = OwnershipStatus.rejected
            owner.is_active = False
            owner.end_date = date.today()

        auth_db.commit()
        db.commit()
        db.refresh(owner)

        user = (
            auth_db.query(Users)
            .filter(Users.id == owner.owner_user_id)
            .first()
        )
        owner_name = user.full_name if user else None

        return OwnershipHistoryOut(
            id=owner.id,
            owner_user_id=owner.owner_user_id,
            owner_name=owner_name,
            ownership_type=owner.ownership_type,
            ownership_percentage=owner.ownership_percentage,
            start_date=owner.start_date,
            end_date=owner.end_date,
            is_active=owner.is_active,
            status=owner.status
        )
    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        auth_db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )
