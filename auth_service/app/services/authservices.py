from twilio.rest import Client
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
import requests
from ..schemas.userschema import UserCreate
from shared.app_status_code import AppStatusCode
from shared.config import settings
from google.oauth2 import id_token
from shared.database import get_auth_db as get_db
from shared import auth
from shared.json_response_helper import error_response
from ..models.users import Users
from ..schemas import authchemas
from ..services import userservices

twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

ALLOWED_ROLES = {"manager", "admin", "superadmin", "user"}

security = HTTPBearer()

# Dependency to get current user


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    payload = auth.verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )

    user = userservices.get_user_by_id(db, payload.get("id"))
    if user is None:
        error_response(
            message="User not found",
            status_code=str(AppStatusCode.AUTHENTICATION_USER_INVALID),
            http_status=400
        )
    return user

#### GOOGLE AUTHENTICATION ###


def google_login(db: Session, facility_db: Session, req: authchemas.GoogleAuthRequest):
    try:
        if not req.access_token:
            raise HTTPException(status_code=400, detail="Missing access token")

        # Call Google API to get user info
        response = requests.get(
            settings.GOOGLE_USERINFO_URL,
            params={"alt": "json", "access_token": req.access_token}
        )

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Invalid access token")

        id_info = response.json()

        email = id_info.get("email")
        if not email or id_info.get("verified_email") not in (True, "true", "True", "1", 1):
            raise HTTPException(
                status_code=400, detail="Google email not verified")

        user = db.query(Users).filter(
            Users.email == email and Users.is_deleted == False).first()

        if not user:
            return authchemas.AuthenticationResponse(
                needs_registration=True,
                email=email,
                name=id_info.get("name"),
                picture=id_info.get("picture")
            )

        return userservices.get_user_token(facility_db, user)

    except ValueError as e:
        raise HTTPException(status_code=401, detail="Invalid token")


#### MOBILE AUTHENTICATION ###

def send_otp(request: authchemas.MobileRequest):
    try:
        verification = twilio_client.verify.v2.services(settings.TWILIO_VERIFY_SID).verifications.create(
            to=request.mobile,
            channel="sms"
        )
        return {"message": "OTP sent", "status": verification.status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Twilio error: {str(e)}")


def verify_otp(db: Session, facility_db: Session, request: authchemas.OTPVerify):
    try:
        check = twilio_client.verify.v2.services(settings.TWILIO_VERIFY_SID).verification_checks.create(
            to=request.mobile,
            code=request.otp
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Twilio error: {str(e)}")

    if getattr(check, "status", None) != "approved":
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    user = db.query(Users).filter(Users.phone == request.mobile).first()

    if not user:
        return authchemas.AuthenticationResponse(
            needs_registration=True,
            mobile=request.mobile,
        )

    return userservices.get_user_token(facility_db, user)
