

from datetime import datetime
from fastapi import BackgroundTasks
from requests import Session
from sqlalchemy import or_
from auth_service.app.models.orgs_safe import OrgSafe
from auth_service.app.models.rolepolicy import RolePolicy
from auth_service.app.models.roles import Roles
from auth_service.app.models.user_organizations import UserOrganization
from auth_service.app.schemas.superadminschema import OrgApprovalRequest
from shared.helpers.email_helper import EmailHelper
from shared.helpers.json_response_helper import error_response
from shared.models.users import Users
from shared.utils.enums import UserAccountType
from shared.utils.system_resources import SYSTEM_ACTIONS, SYSTEM_RESOURCES
from auth_service.app.models.associations import RoleAccountType


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
            "email": org.billing_email,
            "phone": org.contact_phone,
            "created_at": org.created_at
        }
        for org in pending_orgs
    ]


def list_pending_orgs(facility_db: Session, params: OrgApprovalRequest):
    org_query = facility_db.query(OrgSafe)

    total_pending_orgs = org_query.filter(OrgSafe.status == "pending").count()

    if params.status:
        org_query = org_query.filter(OrgSafe.status == params.status)

    if params.search:
        search_term = f"%{params.search}%"
        org_query = org_query.filter(
            or_(
                OrgSafe.name.ilike(search_term),
                OrgSafe.billing_email.ilike(search_term),
                OrgSafe.contact_phone.ilike(search_term)
            )
        )

    total = org_query.count()

    orgs = (
        org_query
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    return {
        "orgs": [
            {
                "id": o.id,
                "name": o.name,
                "email": o.billing_email,
                "phone": o.contact_phone,
                "status": o.status,
                "created_at": o.created_at.isoformat()
            }
            for o in orgs
        ],
        "total": total,
        "total_pending": total_pending_orgs
    }


def approve_org(background_tasks: BackgroundTasks, org_id: str, facility_db: Session, auth_db: Session):

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
        UserOrganization.account_type == UserAccountType.ORGANIZATION.value
    ).update({"status": "active"}, synchronize_session=False)

    # ------------------------------------------------
    # 3. Activate users
    # ------------------------------------------------

    user_ids = auth_db.query(UserOrganization.user_id).filter(
        UserOrganization.org_id == org_id,
        UserOrganization.account_type == UserAccountType.ORGANIZATION.value
    )

    auth_db.query(Users).filter(
        Users.id.in_(user_ids)
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

    auth_db.add(
        RoleAccountType(
            role_id=admin_role.id,
            account_type=UserAccountType.ORGANIZATION
        )
    )

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

    # Send approval email to org admin
    context = {
        "organization_name": org.name,
        "organization_email": org.billing_email,
        "approval_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}

    send_approval_email(background_tasks, db=auth_db,
                        email=org.billing_email, context=context)

    return {"message": f"Organization '{org.name}' approved"}


def reject_org(background_tasks: BackgroundTasks, org_id: str, facility_db: Session, auth_db: Session):
    org = facility_db.query(OrgSafe).filter(OrgSafe.id == org_id).first()
    if not org:
        return error_response(message="Organization not found")

    # Reject the organization
    org.status = "rejected"

    # Make related user organizations with account_type 'organization' rejected
    auth_db.query(UserOrganization).filter(
        UserOrganization.org_id == org_id,
        UserOrganization.account_type == UserAccountType.ORGANIZATION
    ).update({"status": "rejected"}, synchronize_session=False)

    facility_db.commit()
    auth_db.commit()

    # Send rejection email to org admin
    context = {
        "organization_name": org.name,
        "organization_email": org.billing_email,
        "rejection_reason": "Unfortunately, your organization registration did not meet our criteria at this time. Please review the requirements and consider reapplying in the future."}

    send_rejection_email(background_tasks, db=auth_db,
                         email=org.billing_email, context=context)

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


def send_approval_email(background_tasks, db, email, context):
    email_helper = EmailHelper()

    background_tasks.add_task(
        email_helper.send_email,
        db=db,
        template_code="org_approved",
        recipients=[email],
        subject="Your Organization Has Been Approved 🎉",
        context=context,
    )


def send_rejection_email(background_tasks, db, email, context):
    email_helper = EmailHelper()

    background_tasks.add_task(
        email_helper.send_email,
        db=db,
        template_code="org_rejected",
        recipients=[email],
        subject="Update Regarding Your Organization Registration",
        context=context,
    )
