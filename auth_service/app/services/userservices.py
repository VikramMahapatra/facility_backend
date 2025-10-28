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


def create_user(db: Session, facility_db: Session, user: UserCreate):
    # profile_pic_path = None

    # if file:
    #     file_location = os.path.join(settings.UPLOAD_DIR, file.filename)
    #     with open(file_location, "wb") as buffer:
    #         shutil.copyfileobj(file.file, buffer)
    #     profile_pic_path = file_location
    now = datetime.utcnow()

    if user.name and user.name.strip():
        full_name = user.name
    else:
        # Combine first_name + last_name (handling missing parts)
        first = user.first_name or ""
        last = user.last_name or ""
        full_name = f"{first} {last}".strip() or None

    if not full_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="full_name is required. Provide user.name or user.first_name/user.last_name."
        )

    # ✅ Email duplicate check
    if user.email:
        existing_email = db.query(Users).filter(
            Users.email == user.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{user.email}' is already registered."
            )

    # ✅ Phone duplicate check
    if user.phone:
        existing_phone = db.query(Users).filter(
            Users.phone == user.phone).first()
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Phone number '{user.phone}' is already registered."
            )

    new_user = {
        "full_name": full_name,
        "email": user.email,
        "phone": user.phone,
        "picture_url": str(user.pictureUrl) if user.pictureUrl else None,
        "account_type": user.accountType,
        "status": "pending_approval"
    }

    user_instance = Users(**new_user)
    db.add(user_instance)
    db.flush()

    # Add role based on account type
    user_role = "admin" if func.lower(
        user.accountType) == "organization" else "default"
    default_role = db.query(Roles).filter(
        func.lower(Roles.name) == user_role.lower()).first()

    if default_role:
        user_instance.roles.append(default_role)
    else:
        raise ValueError(f"Role '{user.role}' not found")

    # Add role based on account type
    if func.lower(user.accountType) == "organization" and user.organizationName:
        new_org = {
            "name": user.organizationName
        }
        org_instance = OrgSafe(**new_org)
        facility_db.add(org_instance)
        facility_db.commit()
        facility_db.refresh(org_instance)

        user_instance.org_id = org_instance.id
    elif func.lower(user.accountType) == "tenant":
        user_instance.org_id = facility_db.query(
            SiteSafe.org_id).filter(SiteSafe.id == user.site_id).scalar()

        if not user_instance.org_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid site."
            )

        if user.tenant_type == "individual":
            tenant_data = {
                "site_id": user.site_id,
                "space_id": user.space_id,
                "name": full_name,
                "email": user.email,
                "phone": user.phone,
                "status": "inactive",
                "user_id": user_instance.id
            }
            db_tenant = TenantSafe(**tenant_data)
            facility_db.add(db_tenant)
        elif user.tenant_type == "commercial":
            # Only create CommercialPartner
            partner_data = {
                "site_id": user.site_id,
                "type": "merchant",
                "legal_name": full_name,
                "contact": {
                    "name": full_name,
                    "phone": user.phone,
                    "email": user.email
                },
                "status": "inactive",
                "user_id": user_instance.id
            }
            db_partner = CommercialPartnerSafe(**partner_data)
            facility_db.add(db_partner)

        facility_db.commit()

    db.commit()
    db.refresh(user_instance)

    return get_user_token(facility_db, user_instance)


def get_user_token(facility_db: Session, user: Users):
    roles = [str(r.id) for r in user.roles]
    token = auth.create_access_token({
        "user_id": str(user.id),
        "org_id": str(user.org_id),
        "account_type": user.account_type,
        "status": user.status,
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
