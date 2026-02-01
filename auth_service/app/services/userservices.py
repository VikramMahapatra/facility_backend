import os
import shutil
from fastapi import HTTPException, UploadFile, status, Request
from requests import Session
from sqlalchemy import func, and_

from shared.utils.enums import OwnershipStatus
from ..models.space_owners_safe import SpaceOwnerSafe
from ..models.user_organizations import UserOrganization
from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response

from shared.models.user_login_session import LoginPlatform, UserLoginSession
from ..schemas.authschema import AuthenticationResponse
from ..models.sites_safe import SiteSafe
from ..models.tenant_spaces_safe import TenantSpaceSafe
from ..models.tenants_safe import TenantSafe
from shared.core import auth
from ..models.orgs_safe import OrgSafe
from ..models.roles import Roles
from ..models.userroles import UserRoles
from shared.models.users import Users
from ..schemas.userschema import RoleOut, UserCreate, UserOrganizationOut
from shared.core.config import settings
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
# profile_pic_path = None

# if file:
#     file_location = os.path.join(settings.UPLOAD_DIR, file.filename)
#     with open(file_location, "wb") as buffer:
#         shutil.copyfileobj(file.file, buffer)
#     profile_pic_path = file_location


def create_user(
        request: Request,
        db: Session,
        facility_db: Session,
        user: UserCreate):
    try:
        now = datetime.utcnow()

        # ✅ Build full name
        full_name = (user.name or "").strip()
        if not full_name:
            first = (user.first_name or "").strip()
            last = (user.last_name or "").strip()
            full_name = f"{first} {last}".strip()

        if not full_name:
            return error_response(
                message="User name is required.",
                status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
                http_status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Check duplicate email
        if user.email:
            if db.query(Users).filter(Users.email == user.email).first():
                return error_response(
                    message=f"Email '{user.email}' is already registered.",
                    status_code=str(AppStatusCode.USER_USERNAME_IS_UNIQUE),
                    http_status=status.HTTP_400_BAD_REQUEST
                )

        # ✅ Check duplicate phone
        if user.phone:
            if db.query(Users).filter(Users.phone == user.phone).first():
                return error_response(
                    message=f"Phone number '{user.phone}' is already registered.",
                    status_code=str(AppStatusCode.INVALID_INPUT),
                    http_status=status.HTTP_400_BAD_REQUEST
                )

        # ✅ Create base user
        user_instance = Users(
            full_name=full_name,
            email=user.email,
            username=user.email,
            phone=user.phone,
            picture_url=str(user.pictureUrl) if user.pictureUrl else None,
            status="pending_approval"
        )

        if user.password:
            user_instance.set_password(user.password)

        db.add(user_instance)
        db.flush()

        # ✅ Commit All OR Rollback All
        user_org = UserOrganization(
            user_id=user_instance.id,
            org_id=org_id,
            account_type=user.account_type.lower(),
            status="pending",
            is_default=True
        )
        db.add(user_org)

        # ✅ ACCOUNT TYPE: ORGANIZATION
        if user.account_type.lower() == "organization":
            if not user.organizationName:
                return error_response(
                    message="Organization name required",
                    status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
                    http_status=status.HTTP_400_BAD_REQUEST
                )

            org_instance = OrgSafe(name=user.organizationName)
            facility_db.add(org_instance)
            facility_db.flush()  # ✅ ensure id generated

            org_id = org_instance.id

        # ✅ ACCOUNT TYPE: TENANT
        elif user.account_type.lower() == "tenant":
            # ✅ Find site
            site = facility_db.query(SiteSafe).filter(
                SiteSafe.id == user.site_id).first()
            if not site:
                return error_response(
                    message="Invalid site selected",
                    status_code=str(AppStatusCode.INVALID_INPUT),
                )

            org_id = site.org_id

            if not user.space_id:
                return error_response(
                    message="Space required for tenant",
                    status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
                )

            existing_tenant = facility_db.query(TenantSpaceSafe).filter(
                and_(
                    TenantSpaceSafe.space_id == user.space_id,
                    TenantSpaceSafe.status == "leased",
                    TenantSpaceSafe.is_deleted == False)
            ).first()

            if existing_tenant:
                return error_response(
                    message="Tenant already registered for selected space",
                    status_code=str(AppStatusCode.USER_ALREADY_REGISTERED),
                )

            tenant_obj = TenantSafe(
                # site_id=user.site_id,
                # space_id=user.space_id,
                name=full_name,
                email=user.email,
                phone=user.phone,
                status="inactive",
                kind="residential" if user.tenant_type == "individual" else "commercial",
                commercial_type="merchant" if user.tenant_type == "commercial" else None,
                legal_name=full_name if user.tenant_type == "commercial" else None,
                contact={
                    "name": full_name,
                    "phone": user.phone,
                    "email": user.email
                } if user.tenant_type == "commercial" else None,
                user_id=user_instance.id
            )
            facility_db.add(tenant_obj)
            facility_db.flush()  # ✅ ensure id generated

            # ✅ Create space tenant link
            space_tenant_link = TenantSpaceSafe(
                site_id=user.site_id,
                space_id=user.space_id,
                tenant_id=tenant_obj.id,
                status=OwnershipStatus.pending
            )
            facility_db.add(space_tenant_link)

        elif user.account_type.lower() == "owner":
            # ✅ Find site
            site = facility_db.query(SiteSafe).filter(
                SiteSafe.id == user.site_id).first()
            if not site:
                return error_response(
                    message="Invalid site selected",
                    status_code=str(AppStatusCode.INVALID_INPUT),
                )

            org_id = site.org_id

            if not user.space_id:
                return error_response(
                    message="Space required for tenant",
                    status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
                )

            now = datetime.utcnow()

            # ➕ Insert new
            facility_db.add(
                SpaceOwnerSafe(
                    owner_user_id=user_instance.id,
                    space_id=user.space_id,
                    owner_org_id=org_id,
                    is_active=True,
                    start_date=now,
                    status=OwnershipStatus.pending
                )
            )

        db.commit()
        facility_db.commit()

    except HTTPException:
        db.rollback()
        facility_db.rollback()
        return error_response(message="Something went wrong")

    except SQLAlchemyError as e:
        db.rollback()
        facility_db.rollback()
        print("DB Error:", e)
        return error_response(message="Internal server error while creating user")

    return get_user_token(request, db, facility_db, user_instance)


def get_user_token(request: Request, auth_db: Session, facility_db: Session, user: Users):

    ip = request.client.host
    ua = request.headers.get("user-agent")

    if "dart" in ua or "flutter" in ua:
        platform = "mobile"
    else:
        platform = "portal"

    session = UserLoginSession(
        user_id=user.id,
        platform=platform,
        ip_address=ip,
        user_agent=ua,
    )
    auth_db.add(session)
    auth_db.commit()
    auth_db.refresh(session)

    user_org = (
        auth_db.query(UserOrganization)
        .filter(
            UserOrganization.user_id == user.id,
            UserOrganization.is_deleted == False
        )
        .order_by(
            UserOrganization.is_default.desc(),
            UserOrganization.joined_at.asc()
        )
        .first()
    )

    roles = []
    if user_org.roles:
        roles = [str(role.id) for role in user_org.roles]

    tenant = facility_db.query(TenantSafe).filter(
        TenantSafe.user_id == user.id,
        TenantSafe.is_deleted == False
    ).first()

    tenant_type = tenant.kind if tenant else None
    is_mobile = platform == "mobile"

    token_data = {
        "user_id": str(user.id),
        "session_id": str(session.id),
        "org_id": str(user_org.org_id),
        "account_type": user_org.account_type,
        "tenant_type": tenant_type,
        "role_ids": roles or []
    }

    token = auth.create_access_token(token_data, is_mobile)

    refresh_token = None

    if session.platform == LoginPlatform.portal:
        refresh_token = auth.create_refresh_token(auth_db, session.id)

    user_data = get_user_by_id(facility_db, auth_db, user)

    return AuthenticationResponse(
        needs_registration=False,
        access_token=token,
        refresh_token=refresh_token.token if refresh_token else None,
        token_type="bearer",
        user=user_data
    )


def get_user_by_id(facility_db: Session, auth_db: Session, user_data: Users):

    user_orgs = (
        auth_db.query(UserOrganization)
        .filter(
            UserOrganization.user_id == user_data.id,
            UserOrganization.is_deleted == False
        )
        .order_by(
            UserOrganization.is_default.desc(),
            UserOrganization.joined_at.asc()
        )
        .all()
    )

    default_org = user_orgs[0] if user_orgs else None

    user_org_data = facility_db.query(OrgSafe).filter(
        OrgSafe.id == default_org.org_id).first()

    # ✅ Extract unique role policies
    role_policies = []
    for role in default_org.roles:
        for policy in role.policies:
            role_policies.append({
                "resource": policy.resource,
                "action": policy.action
            })

    # ✅ Remove duplicates (optional)
    role_policies = [dict(t)
                     for t in {tuple(d.items()) for d in role_policies}]

    org_ids = [org.org_id for org in user_orgs]

    org_map = {
        org.id: org.name
        for org in facility_db.query(OrgSafe)
        .filter(OrgSafe.id.in_(org_ids))
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

    user_dict = {
        "id": str(user_data.id),
        "name": user_data.full_name,
        "email": user_data.email,
        "phone": user_data.phone,
        "account_types": account_types,
        "default_account_type": default_org.account_type if default_org else None,
        "default_organization_name": user_org_data.name if user_org_data else None,
        "status": user_data.status,
        "is_authenticated": True if user_data.status == "active" else False,
        "roles": [RoleOut.model_validate(role) for role in default_org.roles],
        "role_policies": role_policies
    }

    return user_dict
