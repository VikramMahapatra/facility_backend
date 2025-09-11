import os
import shutil
from fastapi import UploadFile
from requests import Session
from sqlalchemy import func
from app.helpers import authhelper
from app.models.roles import Roles
from app.models.userroles import UserRoles
from app.models.users import Users
from app.schemas.userschema import UserCreate
from app.core.config import settings


def get_user_by_id(db:Session, id:int):
    user_data = db.query(Users)\
        .filter(Users.id == id)\
        .join(UserRoles, Users.id  == UserRoles.user_id)\
        .join(Roles, UserRoles.role_id  == Roles.id)\
        .first()
        
    user_dict =  {
        "id": user_data.id,
        "name": user_data.full_name,
        "email": user_data.email,
        "org_id": user_data.org_id,
        "status": user_data.status,
    }
    
    return user_dict

def create_user(db: Session, user : UserCreate, file: UploadFile):
    profile_pic_path = None
    
    if file:
        file_location = os.path.join(settings.UPLOAD_DIR, file.filename)
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        profile_pic_path = file_location
        
    new_user = {
        "full_name" : user.name,
        "email" : user.email,
        "phone" : user.phone,
        "picture_url" : profile_pic_path,
        "status" : "inactive"
    }
    
    user_instance = Users(**new_user)
    db.add(user_instance)
    db.flush()
    
    default_role = db.query(Roles).filter(func.lower(Roles.name) == user.role.lower()).first()
    
    if default_role:
        user_instance.roles.append(default_role)
    else:
        raise ValueError(f"Role '{user.role}' not found")
    
    db.commit()
    db.refresh(user_instance)
    
    roles = [r.name for r in user_instance.roles]
    
    token = authhelper.create_access_token({"user_id": str(user_instance.id), "email": user_instance.email, "role": roles})
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_instance
    }
    
def get_user_by_id(db:Session, id:int):
    return db.query(Users).filter(Users.user_id == id).first()
    