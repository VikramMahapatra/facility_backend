from fastapi import APIRouter, Depends
from requests import Session
from shared.database import get_db
from app.schemas import authchemas
from app.services import authservices

router = APIRouter(prefix="/api/auth", tags=["Facility Auth"])

@router.post("/google", response_model=authchemas.AuthResponse)
def google_login(req: authchemas.GoogleAuthRequest, db: Session = Depends(get_db)):
    return authservices.google_login(db, req)

@router.post("/mobile/send_otp")
def send_otp(request: authchemas.MobileRequest):
    return authservices.send_otp(request)

@router.post("/mobile/verify_otp", response_model=authchemas.AuthResponse)
def verify_otp(request: authchemas.OTPVerify, db: Session = Depends(get_db)):
    return authservices.verify_otp(db, request)