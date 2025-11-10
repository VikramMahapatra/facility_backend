import os
import shutil
from fastapi import HTTPException, UploadFile, status, Request
from requests import Session
from sqlalchemy import func

from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response

from ..models.user_login_session import LoginPlatform, UserLoginSession
from ..schemas.authchemas import AuthenticationResponse
from ..models.sites_safe import SiteSafe
from ..models.commercial_partner_safe import CommercialPartnerSafe
from ..models.tenants_safe import TenantSafe
from shared.core import auth
from ..models.orgs_safe import OrgSafe
from ..models.roles import Roles
from ..models.userroles import UserRoles
from ..models.users import Users
from ..schemas.userschema import RoleOut, UserCreate
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
            phone=user.phone,
            picture_url=str(user.pictureUrl) if user.pictureUrl else None,
            account_type=user.accountType.lower(),
            status="pending_approval"
        )
        db.add(user_instance)
        db.flush()

        # ✅ Assign Role
        role_name = ("admin" if user.accountType.lower() ==
                     "organization" else user.accountType.lower())
        role_obj = db.query(Roles).filter(
            func.lower(Roles.name) == role_name).first()

        if not role_obj:
            return error_response(
                message=f"Role '{role_name}' not found",
                status_code=str(AppStatusCode.INVALID_INPUT),
                http_status=status.HTTP_400_BAD_REQUEST
            )

        user_instance.roles.append(role_obj)

        # ✅ ACCOUNT TYPE: ORGANIZATION
        if user.accountType.lower() == "organization":
            if not user.organizationName:
                return error_response(
                    message="Organization name required",
                    status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
                    http_status=status.HTTP_400_BAD_REQUEST
                )

            org_instance = OrgSafe(name=user.organizationName)
            facility_db.add(org_instance)
            facility_db.flush()  # ✅ ensure id generated

            user_instance.org_id = org_instance.id

        # ✅ ACCOUNT TYPE: TENANT
        elif user.accountType.lower() == "tenant":
            # ✅ Find site
            site = facility_db.query(SiteSafe).filter(
                SiteSafe.id == user.site_id).first()
            if not site:
                return error_response(
                    message="Invalid site selected",
                    status_code=str(AppStatusCode.INVALID_INPUT),
                    http_status=status.HTTP_400_BAD_REQUEST
                )

            user_instance.org_id = site.org_id

            if not user_instance.org_id:
                return error_response(
                    message="Selected site has no organization assigned",
                    status_code=str(AppStatusCode.INVALID_INPUT),
                    http_status=status.HTTP_400_BAD_REQUEST
                )

            if user.tenant_type == "individual":
                if not user.space_id:
                    return error_response(
                        message="space_id required for individual tenant",
                        status_code=str(
                            AppStatusCode.REQUIRED_VALIDATION_ERROR),
                        http_status=status.HTTP_400_BAD_REQUEST
                    )

                tenant_obj = TenantSafe(
                    site_id=user.site_id,
                    space_id=user.space_id,
                    name=full_name,
                    email=user.email,
                    phone=user.phone,
                    status="inactive",
                    user_id=user_instance.id
                )
                facility_db.add(tenant_obj)

            elif user.tenant_type == "commercial":
                partner_obj = CommercialPartnerSafe(
                    site_id=user.site_id,
                    type="merchant",
                    legal_name=full_name,
                    contact={"name": full_name,
                             "phone": user.phone, "email": user.email},
                    status="inactive",
                    user_id=user_instance.id
                )
                facility_db.add(partner_obj)
            else:
                return error_response(
                    message="Invalid tenant type",
                    status_code=str(AppStatusCode.INVALID_INPUT),
                    http_status=status.HTTP_400_BAD_REQUEST
                )

        # ✅ Commit All OR Rollback All
        db.commit()
        facility_db.commit()
        db.refresh(user_instance)

    except HTTPException:
        db.rollback()
        facility_db.rollback()
        raise

    except SQLAlchemyError as e:
        db.rollback()
        facility_db.rollback()
        print("DB Error:", e)
        raise HTTPException(500, "Internal server error while creating user")

    return get_user_token(request, db, facility_db, user_instance)


def get_user_token(request: Request, auth_db: Session, facility_db: Session, user: Users):
    roles = [str(r.id) for r in user.roles]
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

    token = auth.create_access_token({
        "user_id": str(user.id),
        "session_id": str(session.id),
        "org_id": str(user.org_id),
        "account_type": user.account_type,
        "role_ids": roles})

    refresh_token = None

    if session.platform == LoginPlatform.portal:
        refresh_token = auth.create_refresh_token(auth_db, session.id)

    user_data = get_user_by_id(facility_db, user)

    return AuthenticationResponse(
        needs_registration=False,
        access_token=token,
        refresh_token=refresh_token.token if refresh_token else None,
        token_type="bearer",
        user=user_data
    )


def get_user_by_id(facility_db: Session, user_data: Users):
    user_org_data = facility_db.query(OrgSafe).filter(
        OrgSafe.id == user_data.org_id).first()

    # ✅ Extract unique role policies
    role_policies = []
    for role in user_data.roles:
        for policy in role.policies:
            role_policies.append({
                "resource": policy.resource,
                "action": policy.action
            })

    # ✅ Remove duplicates (optional)
    role_policies = [dict(t)
                     for t in {tuple(d.items()) for d in role_policies}]

    user_dict = {
        "id": str(user_data.id),
        "name": user_data.full_name,
        "email": user_data.email,
        "phone": user_data.phone,
        "account_type": user_data.account_type,
        "organization_name": user_org_data.name if user_org_data else None,
        "status": user_data.status,
        "is_authenticated": True if user_data.status == "active" else False,
        "roles": [RoleOut.model_validate(role) for role in user_data.roles],
        "role_policies": role_policies
    }

    return user_dict
