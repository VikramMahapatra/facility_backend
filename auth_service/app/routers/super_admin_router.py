from fastapi import APIRouter, BackgroundTasks, Depends, Request
from requests import Session
from auth_service.app.models.orgs_safe import OrgSafe
from auth_service.app.schemas.superadminschema import OrgApprovalRequest
from shared.core import auth
from shared.core.database import get_auth_db as get_db, get_facility_db
from shared.core.schemas import UserToken
from shared.helpers.json_response_helper import error_response
from shared.models.users import Users
from ..schemas import authschema
from ..services import super_admin_services

router = APIRouter(prefix="/api/super-admin",
                   tags=["Super Admin"], dependencies=[Depends(auth.require_super_admin)])


@router.get("/orgs/recent-pending")
def get_pending_organizations(db: Session = Depends(get_facility_db)):
    return super_admin_services.get_pending_organizations(db)


@router.get("/orgs/pending")
def list_pending_orgs(params: OrgApprovalRequest = Depends(), facility_db: Session = Depends(get_facility_db)):
    return super_admin_services.list_pending_orgs(facility_db, params)


@router.post("/orgs/{org_id}/approve")
def approve_org(org_id: str, facility_db: Session = Depends(get_facility_db), auth_db: Session = Depends(get_db)):
    return super_admin_services.approve_org(org_id, facility_db, auth_db)


@router.post("/orgs/{org_id}/reject")
def reject_org(org_id: str, facility_db: Session = Depends(get_facility_db), auth_db: Session = Depends(get_db)):
    return super_admin_services.reject_org(org_id, facility_db, auth_db)


@router.get("/stats")
def super_admin_stats(db: Session = Depends(get_db), facility_db: Session = Depends(get_facility_db)):
    return super_admin_services.super_admin_stats(db, facility_db)
