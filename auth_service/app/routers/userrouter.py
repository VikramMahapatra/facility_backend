from fastapi import APIRouter, Depends, File, UploadFile, Request
from requests import Session
from auth_service.app.schemas import authchemas
from shared.core.database import get_auth_db, get_facility_db
from ..schemas import userschema
from ..services import userservices

router = APIRouter(prefix="/api/user", tags=["Facility User"])

# @router.post("/register")
# def register(new_user: userschema.UserCreate  = Depends(userschema.as_form), file: UploadFile = File(None),
#     db: Session = Depends(get_db)):
#     return userservices.create_user(db, new_user, file)


@router.post("/setup", response_model=authchemas.AuthenticationResponse)
def setup(
        new_user: userschema.UserCreate,
        request: Request,
        auth_db: Session = Depends(get_auth_db),
        facility_db: Session = Depends(get_facility_db)):
    return userservices.create_user(request, auth_db, facility_db, new_user)
