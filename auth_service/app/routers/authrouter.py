from fastapi import APIRouter, BackgroundTasks, Depends, Request
from requests import Session
from shared.core import auth
from shared.core.database import get_auth_db as get_db, get_facility_db
from shared.core.schemas import UserToken
from ..schemas import authschema
from ..services import authservices

router = APIRouter(prefix="/api/auth", tags=["Facility Auth"])


@router.post("/google", response_model=authschema.AuthenticationResponse)
def google_login(
        req: authschema.GoogleAuthRequest,
        request: Request,
        db: Session = Depends(get_db),
        facility_db: Session = Depends(get_facility_db)):
    return authservices.google_login(request, db, facility_db, req)


@router.post("/mobile/send_otp")
def send_otp(
        request: authschema.MobileRequest,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        facility_db: Session = Depends(get_facility_db)):
    return authservices.send_otp(background_tasks, db, facility_db, request)


@router.post("/mobile/resend_otp")
def resend_otp(
        request: authschema.MobileRequest,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        facility_db: Session = Depends(get_facility_db)):
    return authservices.resend_otp(background_tasks, db, facility_db, request)


@router.post("/mobile/verify_otp", response_model=authschema.AuthenticationResponse)
def verify_otp(
        request: authschema.OTPVerify,
        api_request: Request,
        db: Session = Depends(get_db),
        facility_db: Session = Depends(get_facility_db)):
    return authservices.verify_otp(api_request, db, facility_db, request)


@router.post("/login", response_model=authschema.AuthenticationResponse)
def login(
        request: authschema.UserAuthRequest,
        api_request: Request,
        db: Session = Depends(get_db),
        facility_db: Session = Depends(get_facility_db)):
    return authservices.verify_user_credentials(api_request, db, facility_db, request)


@router.post("/refresh", response_model=authschema.TokenSuccessResponse)
def refresh_token(
        refresh_token: str,
        db: Session = Depends(get_db)):
    return authservices.refresh_access_token(db, refresh_token)


@router.post("/logout")
def logout(
        refresh_token_str: str = None,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(auth.validate_current_token)):
    return authservices.logout_user(db, current_user.user_id, refresh_token_str)


@router.post("/switch-account", response_model=authschema.AuthenticationResponse)
def switch_account(
        api_request: Request,
        request: authschema.SwitchUserAccountRequest = None,
        db: Session = Depends(get_db),
        facility_db: Session = Depends(get_facility_db),
        current_user: UserToken = Depends(auth.validate_current_token)):
    return authservices.switch_account(api_request, db, facility_db, current_user.user_id, request)
