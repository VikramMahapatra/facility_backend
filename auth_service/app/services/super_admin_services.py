

from requests import Session
from auth_service.app.models.orgs_safe import OrgSafe
from auth_service.app.models.user_organizations import UserOrganization
from shared.helpers.json_response_helper import error_response
from shared.models.users import Users


def list_pending_orgs(facility_db: Session):
    pending_orgs = facility_db.query(OrgSafe).filter(
        OrgSafe.status == "pending").all()
    return {"pending_orgs": [o.to_dict() for o in pending_orgs]}


def approve_org(org_id: str, facility_db: Session, auth_db: Session):
    org = facility_db.query(OrgSafe).filter(OrgSafe.id == org_id).first()
    if not org:
        return error_response(message="Organization not found")

    # Approve the organization
    org.status = "active"

    # Make related user organizations with account_type 'organization' active
    auth_db.query(UserOrganization).filter(
        UserOrganization.org_id == org_id,
        UserOrganization.account_type == "organization"
    ).update({"status": "active"}, synchronize_session=False)

    facility_db.commit()
    auth_db.commit()
    return {"message": f"Organization '{org.name}' approved"}


def reject_org(org_id: str, facility_db: Session, auth_db: Session):
    org = facility_db.query(OrgSafe).filter(OrgSafe.id == org_id).first()
    if not org:
        return error_response(message="Organization not found")

    # Reject the organization
    org.status = "rejected"

    # Make related user organizations with account_type 'organization' rejected
    auth_db.query(UserOrganization).filter(
        UserOrganization.org_id == org_id,
        UserOrganization.account_type == "organization"
    ).update({"status": "rejected"}, synchronize_session=False)

    facility_db.commit()
    auth_db.commit()
    return {"message": f"Organization '{org.name}' rejected"}


def super_admin_stats(db: Session, facility_db: Session):
    total_orgs = facility_db.query(OrgSafe).count()
    pending_orgs = facility_db.query(OrgSafe).filter(
        OrgSafe.status == "pending").count()
    total_users = db.query(Users).count()
    return {
        "total_orgs": total_orgs,
        "pending_orgs": pending_orgs,
        "total_users": total_users
    }
