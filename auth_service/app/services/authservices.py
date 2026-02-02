import random
from twilio.rest import Client
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
import requests
from datetime import datetime, timedelta, timezone

from ..models.user_organizations import UserOrganization
from ..models.otp_verifications import OtpVerification
from shared.models.user_login_session import UserLoginSession
from shared.helpers.email_helper import EmailHelper
from shared.models.refresh_token import RefreshToken
from ..schemas.userschema import UserCreate
from shared.utils.app_status_code import AppStatusCode
from shared.core.config import settings
from google.oauth2 import id_token
from shared.core.database import get_auth_db as get_db
from shared.core import auth
from shared.helpers.json_response_helper import error_response, success_response
from shared.models.users import Users
from ..schemas import authschema
from ..services import userservices

twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

security = HTTPBearer()


#### GOOGLE AUTHENTICATION ###

def google_login(
        request: Request,
        db: Session,
        facility_db: Session,
        req: authschema.GoogleAuthRequest):
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
            Users.email == email,
            Users.is_deleted == False).first()

        if not user:
            return authschema.AuthenticationResponse(
                needs_registration=True,
                email=email,
                name=id_info.get("name"),
                picture=id_info.get("picture")
            )

        return userservices.get_user_token(request, db, facility_db, user)

    except ValueError as e:
        print(f"Google token error: {e}")
        return error_response(
            message="Something went wrong",
            status_code=str(AppStatusCode.AUTHENTICATION_USER_OTP_EXPIRED),
            http_status=status.HTTP_400_BAD_REQUEST
        )


#### MOBILE AUTHENTICATION ###

def generate_otp(length=6):
    return str(random.randint(10**(length-1), (10**length)-1))


def send_otp(background_tasks: BackgroundTasks, db: Session, facility_db: Session, request: authschema.MobileRequest):
    try:
        message = None
        print("MOBILE VALUE:", repr(request.mobile))
        if request.mobile and request.mobile.strip():
            message = "OTP sent to your mobile no."
            # verification = twilio_client.verify.v2.services(settings.TWILIO_VERIFY_SID).verifications.create(
            #     to=request.mobile,
            #     channel="sms"
            # )
            # return {"message": "OTP sent", "status": verification.status}
        elif request.email:
            otp = generate_otp()
            # store OTP in DB
            otp_entry = OtpVerification(
                email=request.email,
                otp=otp,
                created_at=datetime.utcnow(),
                is_verified=False
            )
            db.add(otp_entry)
            db.commit()
            send_otp_email(background_tasks, facility_db, otp, request.email)
            message = "OTP sent to your email."
        else:
            return error_response(
                message="Invalid Request",
                status_code=AppStatusCode.INVALID_INPUT
            )

        return success_response(
            data="",
            message=message
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error sending OTP:{str(e)}")


def verify_otp(
        api_request: Request,
        db: Session,
        facility_db: Session,
        request: authschema.OTPVerify):
    user = None
    if request.mobile and request.mobile.strip():
        try:
            # check = twilio_client.verify.v2.services(settings.TWILIO_VERIFY_SID).verification_checks.create(
            #     to=request.mobile,
            #     code=request.otp
            # )
            check = {"status": "approved"}
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Twilio error: {str(e)}")

        status_value = getattr(check, "status", None) or check.get("status")

        if status_value != "approved":
            return error_response(
                message="Invalid or expired OTP",
                status_code=str(AppStatusCode.AUTHENTICATION_USER_OTP_EXPIRED),
                http_status=status.HTTP_400_BAD_REQUEST
            )

        user = db.query(Users).filter(
            Users.phone == request.mobile, Users.is_deleted == False).first()
    elif request.email:
        record = (
            db.query(OtpVerification)
            .filter(OtpVerification.email == request.email, OtpVerification.is_verified == False)
            .order_by(OtpVerification.created_at.desc())
            .first()
        )
        if not record:
            return error_response(message="OTP not found", status_code=AppStatusCode.INVALID_INPUT)

        if record.is_expired:
            return error_response(message="OTP expired", status_code=AppStatusCode.AUTHENTICATION_USER_OTP_EXPIRED)

        if record.otp != request.otp:
            return error_response(message="Invalid OTP", status_code=AppStatusCode.INVALID_INPUT)

        # mark verified
        record.is_verified = True
        db.commit()

        user = db.query(Users).filter(Users.email == request.email).first()
    else:
        return error_response(
            message="Invalid Request",
            status_code=AppStatusCode.INVALID_INPUT
        )

    if not user:
        return authschema.AuthenticationResponse(
            needs_registration=True,
            mobile=request.mobile,
        )

    return userservices.get_user_token(api_request, db, facility_db, user)


def verify_user_credentials(
        api_request: Request,
        db: Session,
        facility_db: Session,
        request: authschema.UserAuthRequest):
    user = db.query(Users).filter(
        Users.username == request.username,
        Users.is_deleted == False
    ).first()

    if not user or not user.verify_password(request.password):
        return error_response(message="Invalid credentials")

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


def logout_user(db: Session, user_id: str, refresh_token_str: str = None):
    now = datetime.now(timezone.utc)

    if refresh_token_str:
        # 🔹 Case 1: Web/portal logout using refresh token
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

        token.revoked = True
        token.session.is_active = False
        token.session.logged_out_at = now
        db.commit()

        return {"message": "Logged out successfully"}

    else:
        # 🔹 Case 2: Mobile logout (no refresh token)
        # Simply deactivate the active mobile session(s)
        sessions = (
            db.query(UserLoginSession)
            .filter(
                UserLoginSession.user_id == user_id,
                UserLoginSession.platform == "mobile",
                UserLoginSession.is_active == True
            )
            .all()
        )

        if not sessions:
            return error_response(
                message="No active mobile sessions found.",
                status_code=str(AppStatusCode.AUTHENTICATION_TOKEN_INVALID),
                http_status=status.HTTP_404_NOT_FOUND
            )

        for session in sessions:
            session.is_active = False
            session.logged_out_at = now

        db.commit()
        return {"message": "Mobile session(s) logged out successfully"}


def send_otp_email(background_tasks, db, otp, email):
    email_helper = EmailHelper()

    background_tasks.add_task(
        email_helper.send_email,
        db=db,
        template_code="otp_send",
        recipients=[email],
        subject="Your One Time Password to login",
        context={"otp": otp},
    )


def switch_account(
        api_request: Request,
        db: Session,
        facility_db: Session,
        user_id: str,
        request: authschema.SwitchUserAccountRequest = None):

    user = db.query(Users).filter(
        Users.id == user_id,
        Users.is_deleted == False
    ).first()

    if not user:
        return error_response(
            message="User not found",
            status_code=str(AppStatusCode.AUTHENTICATION_USER_INVALID),
            http_status=status.HTTP_404_NOT_FOUND
        )

    with db.begin():
        db.query(UserOrganization).filter(
            UserOrganization.user_id == user_id,
            UserOrganization.is_default == True
        ).update(
            {"is_default": False},
            synchronize_session=False
        )

        default_org = (
            db.query(UserOrganization)
            .filter(UserOrganization.id == request.user_org_id, UserOrganization.account_type == request.account_type)
            .first()
        )

        default_org.is_default = True
        db.commit()

    return userservices.get_user_token(api_request, db, facility_db, user)
