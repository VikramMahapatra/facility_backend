

from requests import Session
from auth_service.app.models.orgs_safe import OrgSafe
from auth_service.app.models.rolepolicy import RolePolicy
from auth_service.app.models.roles import Roles
from auth_service.app.models.user_organizations import UserOrganization
from shared.helpers.json_response_helper import error_response
from shared.models.users import Users
from shared.utils.system_resources import SYSTEM_ACTIONS, SYSTEM_RESOURCES


def get_pending_organizations(db: Session):

    pending_orgs = (
        db.query(OrgSafe)
        .filter(OrgSafe.status == "pending")
        .order_by(OrgSafe.created_at.desc())
        .limit(5)   # dashboard only needs few
        .all()
    )

    return [
        {
            "id": str(org.id),
            "name": org.name,
            "created_at": org.created_at
        }
        for org in pending_orgs
    ]


def list_pending_orgs(facility_db: Session):
    pending_orgs = facility_db.query(OrgSafe).filter(
        OrgSafe.status == "pending").all()
    return {
        "pending_orgs": [
            {
                "id": o.id,
                "name": o.name,
                "email": o.billing_email,
                "phone": o.contact_phone,
                "created_at": o.created_at.isoformat()
            }
            for o in pending_orgs
        ]
    }


def approve_org(org_id: str, facility_db: Session, auth_db: Session):

    org = facility_db.query(OrgSafe).filter(
        OrgSafe.id == org_id
    ).first()

    if not org:
        return error_response(message="Organization not found")

    # ------------------------------------------------
    # 1. Activate org
    # ------------------------------------------------

    org.status = "active"

    # ------------------------------------------------
    # 2. Activate user organizations
    # ------------------------------------------------

    auth_db.query(UserOrganization).filter(
        UserOrganization.org_id == org_id,
        UserOrganization.account_type == "organization"
    ).update({"status": "active"}, synchronize_session=False)

    # ------------------------------------------------
    # 3. Activate users
    # ------------------------------------------------

    auth_db.query(Users).join(
        UserOrganization,
        Users.id == UserOrganization.user_id
    ).filter(
        UserOrganization.org_id == org_id,
        UserOrganization.account_type == "organization"
    ).update({"status": "active"}, synchronize_session=False)

    # ------------------------------------------------
    # 4. Create ADMIN ROLE if not exists
    # ------------------------------------------------

    admin_role = auth_db.query(Roles).filter(
        Roles.org_id == org_id,
        Roles.name == "admin"
    ).first()

    if not admin_role:

        admin_role = Roles(
            org_id=org_id,
            name="admin",
            description="Default administrator role"
        )

        auth_db.add(admin_role)
        auth_db.flush()   # get role.id

    # ------------------------------------------------
    # 5. Assign admin role to org admin user
    # ------------------------------------------------

    admin_user_org = auth_db.query(UserOrganization).filter(
        UserOrganization.org_id == org_id,
        UserOrganization.account_type == "organization"
    ).first()

    if admin_user_org:

        admin_user_org.roles.append(admin_role)

    # ------------------------------------------------
    # 6. Create ALL ROLE POLICIES
    # ------------------------------------------------

    existing = auth_db.query(RolePolicy).filter(
        RolePolicy.role_id == admin_role.id
    ).count()

    if existing == 0:

        policies = []

        for resource in SYSTEM_RESOURCES:
            for action in SYSTEM_ACTIONS:

                policies.append(
                    RolePolicy(
                        org_id=org_id,
                        role_id=admin_role.id,
                        resource=resource,
                        action=action
                    )
                )

        auth_db.bulk_save_objects(policies)

    # ------------------------------------------------

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
