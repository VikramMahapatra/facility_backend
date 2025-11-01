import os
import shutil
from fastapi import HTTPException, UploadFile, status
from requests import Session
from sqlalchemy import func

from auth_service.app.schemas import authchemas

from ..models.sites_safe import SiteSafe
from ..models.commercial_partner_safe import CommercialPartnerSafe
from ..models.tenants_safe import TenantSafe
from shared import auth
from ..models.orgs_safe import OrgSafe
from ..models.roles import Roles
from ..models.userroles import UserRoles
from ..models.users import Users
from ..schemas.userschema import RoleOut, UserCreate
from shared.config import settings
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

# profile_pic_path = None

# if file:
#     file_location = os.path.join(settings.UPLOAD_DIR, file.filename)
#     with open(file_location, "wb") as buffer:
#         shutil.copyfileobj(file.file, buffer)
#     profile_pic_path = file_location


def create_user(db: Session, facility_db: Session, user: UserCreate):
    try:
        now = datetime.utcnow()

        # ✅ Build full name
        full_name = (user.name or "").strip()
        if not full_name:
            first = (user.first_name or "").strip()
            last = (user.last_name or "").strip()
            full_name = f"{first} {last}".strip()

        if not full_name:
            raise HTTPException(
                status_code=400,
                detail="User name is required."
            )

        # ✅ Check duplicate email
        if user.email:
            if db.query(Users).filter(Users.email == user.email).first():
                raise HTTPException(
                    status_code=400,
                    detail=f"Email '{user.email}' is already registered."
                )

        # ✅ Check duplicate phone
        if user.phone:
            if db.query(Users).filter(Users.phone == user.phone).first():
                raise HTTPException(
                    status_code=400,
                    detail=f"Phone number '{user.phone}' is already registered."
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
            raise HTTPException(400, f"Role '{role_name}' not found")

        user_instance.roles.append(role_obj)

        # ✅ ACCOUNT TYPE: ORGANIZATION
        if user.accountType.lower() == "organization":
            if not user.organizationName:
                raise HTTPException(400, "Organization name required")

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
                raise HTTPException(400, "Invalid site selected")

            user_instance.org_id = site.org_id

            if not user_instance.org_id:
                raise HTTPException(
                    400, "Selected site has no organization assigned")

            if user.tenant_type == "individual":
                if not user.space_id:
                    raise HTTPException(
                        400, "space_id required for individual tenant")

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
                raise HTTPException(400, "Invalid tenant type")

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

    return get_user_token(facility_db, user_instance)


def get_user_token(facility_db: Session, user: Users):
    roles = [str(r.id) for r in user.roles]
    token = auth.create_access_token({
        "user_id": str(user.id),
        "org_id": str(user.org_id),
        "account_type": user.account_type,
        "role_ids": roles})
    user_data = get_user_by_id(facility_db, user)

    return authchemas.AuthenticationResponse(
        needs_registration=False,
        access_token=token,
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
