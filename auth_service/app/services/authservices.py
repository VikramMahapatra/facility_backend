from twilio.rest import Client
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from google.auth.transport import requests
from app.core.config import settings
from google.oauth2 import id_token
from app.core.database import get_db
from app.helpers import authhelper
from app.models.users import Users
from app.schemas import authchemas
from app.services import userservices

twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

ALLOWED_ROLES = {"manager", "admin", "superadmin", "user"}

security = HTTPBearer()

# Dependency to get current user
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db:Session=Depends(get_db)):
    token = credentials.credentials
    payload = authhelper.verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    
    user = userservices.get_user_by_id(db, payload.get("id"))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user

#### GOOGLE AUTHENTICATION ###

def google_login(db: Session, req: authchemas.GoogleAuthRequest):
    try:
        request = requests.Request()
        id_info = id_token.verify_oauth2_token(req.token, request, settings.GOOGLE_CLIENT_ID)

        if id_info.get("aud") != settings.GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=401, detail="Google ID token audience mismatch")

        email = id_info.get("email")
        if not email or id_info.get("email_verified") not in (True, "true", "True", "1", 1):
            raise HTTPException(status_code=400, detail="Google email not verified")

        user = db.query(Users).filter(Users.email == email).first()
        if not user:
            return {
                "needs_registration": True,
                "email": email,
                "allowed_roles": sorted(ALLOWED_ROLES),
            }

        token = authhelper.create_access_token({"user_id": user.id, "email": user.email, "role": user.role})
        return {
            "needs_registration": False,
            "token": {
                "access_token": token,
                "token_type": "bearer",
                "redirect_url": role_redirect(user.role),
            },
        }
    
    except ValueError as e:
        raise HTTPException(status_code=401, detail="Invalid token")
    
def role_redirect(role: str) -> str:
    return f"/dashboard/{role}"
    
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

def verify_otp(db: Session, request: authchemas.OTPVerify):
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
        # if not request.role:
        #     raise HTTPException(status_code=400, detail="New user must provide role")
        # user = models.User(mobile=request.mobile, role=request.role)
        # db.add(user)
        # db.commit()
        # db.refresh(user)
        is_new = True
        
        return {
                "access_token": "",
                "token_type": "bearer",
                "needs_registration": True,
            }
    else:
        is_new = False

        token = authhelper.create_access_token({"user_id": user.id, "mobile": user.mobile, "role": user.role})
        redirect_map = {"admin": "/admin/home", "superadmin": "/superadmin/dashboard", "user": "/user/home"}

        return {
        "access_token": token,
        "token_type": "bearer",
        "new_user": is_new,
        "redirect_url": redirect_map.get(user.role, "/user/home")
}