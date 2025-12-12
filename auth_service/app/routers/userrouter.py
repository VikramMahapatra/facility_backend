from fastapi import APIRouter, Depends, File, UploadFile, Request
from requests import Session
from auth_service.app.schemas import authschema
from shared.core.database import get_auth_db, get_facility_db
from ..schemas import userschema
from ..services import userservices

router = APIRouter(prefix="/api/user", tags=["Facility User"])


@router.post("/setup", response_model=authschema.AuthenticationResponse)
def setup(
        new_user: userschema.UserCreate,
        request: Request,
        auth_db: Session = Depends(get_auth_db),
        facility_db: Session = Depends(get_facility_db)):
    return userservices.create_user(request, auth_db, facility_db, new_user)
