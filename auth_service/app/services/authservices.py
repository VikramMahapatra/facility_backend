from twilio.rest import Client
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
import requests
from datetime import datetime, timedelta, timezone
from auth_service.app.models.user_login_session import UserLoginSession
from ..models.refresh_token import RefreshToken
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
        return error_response(
            message="Invalid access token",
            status_code=str(AppStatusCode.AUTHENTICATION_TOKEN_INVALID),
            http_status=status.HTTP_400_BAD_REQUEST
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


def google_login(
        request: Request,
        db: Session,
        facility_db: Session,
        req: authchemas.GoogleAuthRequest):
    try:
        if not req.access_token:
            return error_response(
                message="Missing access token",
                status_code=str(AppStatusCode.AUTHENTICATION_TOKEN_INVALID),
                http_status=status.HTTP_400_BAD_REQUEST
            )

        # Call Google API to get user info
        response = requests.get(
            settings.GOOGLE_USERINFO_URL,
            params={"alt": "json", "access_token": req.access_token}
        )

        if response.status_code != 200:
            return error_response(
                message="Invalid access token",
                status_code=str(AppStatusCode.AUTHENTICATION_TOKEN_INVALID),
                http_status=status.HTTP_400_BAD_REQUEST
            )

        id_info = response.json()

        email = id_info.get("email")
        if not email or id_info.get("verified_email") not in (True, "true", "True", "1", 1):
            return error_response(
                message="Google email not verified",
                status_code=str(
                    AppStatusCode.AUTHENTICATION_CREDENTIALS_INVALID),
                http_status=status.HTTP_400_BAD_REQUEST
            )

        user = db.query(Users).filter(
            Users.email == email and Users.is_deleted == False).first()

        if not user:
            return authchemas.AuthenticationResponse(
                needs_registration=True,
                email=email,
                name=id_info.get("name"),
                picture=id_info.get("picture")
            )

        return userservices.get_user_token(request, db, facility_db, user)

    except ValueError as e:
        return error_response(
            message="Invalid or expired OTP",
            status_code=str(AppStatusCode.AUTHENTICATION_USER_OTP_EXPIRED),
            http_status=status.HTTP_400_BAD_REQUEST
        )


#### MOBILE AUTHENTICATION ###

def send_otp(request: authchemas.MobileRequest):
    try:
        # verification = twilio_client.verify.v2.services(settings.TWILIO_VERIFY_SID).verifications.create(
        #     to=request.mobile,
        #     channel="sms"
        # )
        # return {"message": "OTP sent", "status": verification.status}
        return {"message": "OTP sent", "status": "pending"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Twilio error: {str(e)}")


def verify_otp(
        api_request: Request,
        db: Session,
        facility_db: Session,
        request: authchemas.OTPVerify):
    try:
        # check = twilio_client.verify.v2.services(settings.TWILIO_VERIFY_SID).verification_checks.create(
        #     to=request.mobile,
        #     code=request.otp
        # )
        check = {"status": "approved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Twilio error: {str(e)}")

    status_value = getattr(check, "status", None) or check.get("status")

    if status_value != "approved":
        return error_response(
            message="Invalid or expired OTP",
            status_code=str(AppStatusCode.AUTHENTICATION_USER_OTP_EXPIRED),
            http_status=status.HTTP_400_BAD_REQUEST
        )

    user = db.query(Users).filter(Users.phone == request.mobile).first()

    if not user:
        return authchemas.AuthenticationResponse(
            needs_registration=True,
            mobile=request.mobile,
        )

    return userservices.get_user_token(api_request, db, facility_db, user)


def refresh_access_token(db: Session, refresh_token_str: str):
    token = (
        db.query(RefreshToken)
        .filter_by(token=refresh_token_str, revoked=False)
        .first()
    )

    now = datetime.now(timezone.utc)

    if not token or token.expires_at < now:
        return error_response(
            message="Invalid or expired refresh token",
            status_code=str(AppStatusCode.AUTHENTICATION_TOKEN_INVALID),
            http_status=status.HTTP_401_UNAUTHORIZED
        )

    session = token.session
    if not session.is_active:
        return error_response(
            message="Session inactive",
            status_code=str(AppStatusCode.AUTHENTICATION_UNAUTHORIZED_ACCESS),
            http_status=status.HTTP_401_UNAUTHORIZED
        )

    user = db.query(Users).filter(Users.id == session.user_id).first()
    if not user:
        return error_response(
            message="User not found",
            status_code=str(AppStatusCode.AUTHENTICATION_USER_INVALID),
            http_status=status.HTTP_404_NOT_FOUND
        )

    # Invalidate old refresh token
    token.revoked = True

    # Issue new access + refresh tokens
    roles = [str(r.id) for r in user.roles]
    new_access_token = auth.create_access_token({
        "user_id": str(user.id),
        "session_id": str(session.id),
        "org_id": str(user.org_id),
        "account_type": user.account_type,
        "role_ids": roles})
    new_refresh = auth.create_refresh_token(db, session.id)

    db.commit()

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh.token,
        "token_type": "bearer"
    }


def logout_user(db: Session, user_id: str, refresh_token_str: str):
    token = (
        db.query(RefreshToken)
        .join(UserLoginSession)
        .filter(
            UserLoginSession.user_id == user_id,
            RefreshToken.token == refresh_token_str,
            RefreshToken.revoked == False
        )
        .first()
    )

    if not token:
        return error_response(
            message="Active session or refresh token not found.",
            status_code=str(AppStatusCode.AUTHENTICATION_TOKEN_INVALID),
            http_status=status.HTTP_404_NOT_FOUND
        )

    now = datetime.now(timezone.utc)
    token.revoked = True
    token.session.is_active = False
    token.session.logged_out_at = now
    db.commit()

    return {"message": "Logged out successfully"}
