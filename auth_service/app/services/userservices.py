import os
import shutil
from fastapi import UploadFile
from requests import Session
from sqlalchemy import func
from shared import auth
from ..models.orgs_safe import OrgSafe
from ..models.roles import Roles
from ..models.userroles import UserRoles
from ..models.users import Users
from ..schemas.userschema import RoleOut, UserCreate
from shared.config import settings


def create_user(db: Session, facility_db: Session, user: UserCreate):
    # profile_pic_path = None

    # if file:
    #     file_location = os.path.join(settings.UPLOAD_DIR, file.filename)
    #     with open(file_location, "wb") as buffer:
    #         shutil.copyfileobj(file.file, buffer)
    #     profile_pic_path = file_location

    new_user = {
        "full_name": user.name,
        "email": user.email,
        "phone": user.phone,
        "picture_url": str(user.pictureUrl) if user.pictureUrl else None,
        "account_type": user.accountType,
        "status": "active"
    }

    user_instance = Users(**new_user)
    db.add(user_instance)
    db.flush()

    # Add role based on account type
    user_role = "Admin" if user.accountType == "Organization" else "Default"
    default_role = db.query(Roles).filter(
        func.lower(Roles.name) == user_role.lower()).first()

    if default_role:
        user_instance.roles.append(default_role)
    else:
        raise ValueError(f"Role '{user.role}' not found")

    # Add role based on account type
    if user.organizationName:
        new_org = {
            "name": user.organizationName
        }
        org_instance = OrgSafe(**new_org)
        facility_db.add(org_instance)
        facility_db.commit()
        facility_db.refresh(org_instance)

        user_instance.org_id = org_instance.id

    db.commit()
    db.refresh(user_instance)

    roles = [r.name for r in user_instance.roles]
    token = auth.create_access_token({"user_id": str(user_instance.id), "org_id": str(
        user_instance.org_id),  "email": user_instance.email, "role": roles})
    user_data = get_user_by_id(facility_db, user_instance)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_data
    }


def get_user_by_id(facility_db: Session, user_data: Users):
    user_org_data = facility_db.query(OrgSafe).filter(
        OrgSafe.id == user_data.org_id).first()

    user_dict = {
        "id": str(user_data.id),
        "name": user_data.full_name,
        "email": user_data.email,
        "accountType": user_data.account_type,
        "organizationName": user_org_data.name,
        "roles": [RoleOut.model_validate(role) for role in user_data.roles],
    }

    return user_dict
