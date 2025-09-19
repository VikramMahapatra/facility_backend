from fastapi import APIRouter, Depends, File, UploadFile
from requests import Session
from shared.database import get_db
from app.schemas import userschema
from app.services import userservices

router = APIRouter(prefix="/api/user", tags=["Facility User"])

@router.post("/register")
def register(new_user: userschema.UserCreate  = Depends(userschema.as_form), file: UploadFile = File(None), 
    db: Session = Depends(get_db)):
    return userservices.create_user(db, new_user, file)
