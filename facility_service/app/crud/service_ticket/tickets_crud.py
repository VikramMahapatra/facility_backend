import base64
from datetime import datetime, timezone
from operator import or_
from typing import Dict, List
from requests import request
from sqlalchemy import desc, distinct, select
from fastapi import HTTPException, BackgroundTasks, UploadFile
from sqlalchemy.orm import Session, selectinload, joinedload, load_only
from uuid import UUID
from sqlalchemy import and_, func, desc
from auth_service.app.models.roles import Roles
from auth_service.app.models.userroles import UserRoles
from ...models.procurement.vendors import Vendor
from shared.models.users import Users
from shared.core.config import Settings
from shared.helpers.email_helper import EmailHelper
from shared.utils.enums import UserAccountType
from ...schemas.system.notifications_schemas import NotificationType, PriorityType
from ...models.system.notifications import Notification
from ...enum.ticket_service_enum import TicketStatus
from ...models.leasing_tenants.tenants import Tenant
from ...models.service_ticket.tickets_category import TicketCategory
from ...models.space_sites.spaces import Space
from ...schemas.mobile_app.help_desk_schemas import ComplaintDetailsResponse, TicketWorkFlowOut

from ...models.service_ticket.sla_policy import SlaPolicy
from ...models.service_ticket.tickets_commets import TicketComment
from ...models.service_ticket.tickets_feedback import TicketFeedback
from ...models.service_ticket.tickets_reaction import ALLOWED_EMOJIS, TicketReaction
from shared.core.schemas import Lookup, UserToken
from ...models.service_ticket.ticket_assignment import TicketAssignment
from ...models.service_ticket.tickets import Ticket
from ...models.service_ticket.tickets_workflow import TicketWorkflow
from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response, success_response
from ...schemas.service_ticket.tickets_schemas import AddCommentRequest, AddFeedbackRequest, AddReactionRequest, PossibleStatusesResponse, StatusOption, TicketActionRequest, TicketAdminRoleRequest, TicketAssignedToRequest, TicketCommentOut, TicketCommentRequest, TicketCreate, TicketDetailsResponse,  TicketFilterRequest, TicketOut, TicketReactionRequest, TicketUpdateRequest, TicketWorkflowOut


def build_ticket_filters(
    db: Session,
    params: TicketFilterRequest,
    current_user: UserToken
):
    account_type = current_user.account_type.lower()

    # -------------------------------------------------
    # BASE FILTERS (Based on user's account type)
    # -------------------------------------------------
    if account_type in (UserAccountType.ORGANIZATION, UserAccountType.STAFF):
        filters = [Ticket.org_id == current_user.org_id]

        if account_type == UserAccountType.STAFF:
            filters.append(Ticket.assigned_to == current_user.user_id)

    else:
        tenant_id = db.query(Tenant.id).filter(
            Tenant.user_id == current_user.user_id,
            Tenant.is_deleted == False
        ).scalar()

        filters = [Ticket.tenant_id == tenant_id]

    # -------------------------------------------------
    # FILTER: SITE
    # -------------------------------------------------
    if params.site_id and params.site_id != "all":
        filters.append(Ticket.site_id == params.site_id)

    # -------------------------------------------------
    # FILTER: SPACE
    # STAFF should not filter space by default
    # -------------------------------------------------
    if params.space_id and account_type != UserAccountType.STAFF:
        filters.append(Ticket.space_id == params.space_id)

    # -------------------------------------------------
    # FILTER: SEARCH (ticket no, title, description)
    # -------------------------------------------------
    if params.search:
        search_term = f"%{params.search.lower()}%"
        filters.append(
            or_(
                func.lower(Ticket.ticket_no).like(search_term),
                func.lower(Ticket.title).like(search_term),
            )
        )

    # -------------------------------------------------
    # FILTER: PRIORITY
    # -------------------------------------------------
    if params.priority and params.priority.lower() != "all":
        filters.append(
            func.lower(Ticket.priority) == params.priority.lower()
        )

    # -------------------------------------------------
    # FILTER: STATUS
    # -------------------------------------------------
    if params.status and params.status.lower() != "all":

        status = params.status.lower()

        if status == "overdue":
            # Overdue = open tickets with SLA breached
            filters.append(
                and_(
                    Ticket.status != "closed",
                    func.extract('epoch', func.now() - Ticket.created_at) / 60 >
                    func.coalesce(SlaPolicy.resolution_time_mins, 0)
                )
            )

            # Overdue requires scaling to SLA joins
            base_query = (
                db.query(Ticket)
                .join(Ticket.category)
                .join(TicketCategory.sla_policy)
                .filter(*filters)
            )

        else:
            # Normal status like 'open', 'inprogress', 'closed'
            filters.append(func.lower(Ticket.status) == status)
            base_query = db.query(Ticket).filter(*filters)

    else:
        # Status not provided → regular query
        base_query = db.query(Ticket).filter(*filters)

    # -------------------------------------------------
    # PERFORMANCE: Load only required fields
    # -------------------------------------------------
    base_query = (
        base_query.options(
            load_only(
                Ticket.id,
                Ticket.ticket_no,
                Ticket.title,
                Ticket.description,
                Ticket.priority,
                Ticket.request_type,
                Ticket.status,
                Ticket.preferred_time,
                Ticket.created_at,
                Ticket.closed_date,
                Ticket.space_id,
            ),
            selectinload(Ticket.category).load_only(
                TicketCategory.category_name
            )
        )
    )

    return base_query


def get_tickets(db: Session, params: TicketFilterRequest, current_user: UserToken):

    base_query = build_ticket_filters(db, params, current_user)

    subq = base_query.with_entities(Ticket.id).subquery()
    total = db.query(func.count()).select_from(subq).scalar()

    query = base_query.order_by(desc(Ticket.updated_at))

    if params.skip is not None:
        query = query.offset(params.skip)

    if params.limit is not None:
        query = query.limit(params.limit)

    tickets = query.all()

    results = []
    for t in tickets:
        data = t.__dict__.copy()
        data.pop("category", None)  # remove SA relationship
        results.append(
            TicketOut(
                **data,
                category=t.category.category_name if t.category else None,
                can_escalate=t.can_escalate,
                can_reopen=t.can_reopen,
                is_overdue=t.is_overdue
            )
        )

    return {"tickets": results, "total": total}

# for mobile -----


def get_ticket_details(db: Session, auth_db: Session, ticket_id: str):
    """
    Fetch full Tickets details along with all related comments and logs
    """
    # Step 1: Fetch service request with joins for related data
    service_req = (
        db.query(Ticket)
        .filter(Ticket.id == ticket_id)
        .first()
    )

    if not service_req:
        raise HTTPException(
            status_code=404, detail="Service request not found")

    # Step 2: Get assigned_to from SLA policies based on category - FIXED
    category_name = service_req.category.category_name if service_req.category else None

    assigned_to_name = None
    # Fetch assigned user full_name from auth.db user table
    assigned_user = (
        auth_db.query(Users)
        .filter(Users.id == service_req.assigned_to)
        .first()
    )
    assigned_to_name = assigned_user.full_name if assigned_user else None

    # Combine both logs
    all_logs = []

    # Add workflow logs
    for log in service_req.comments:
        all_logs.append(TicketWorkFlowOut(
            id=log.id,
            ticket_id=log.ticket_id,
            type="comment",
            action_taken=log.comment_text,
            created_at=log.created_at,
            action_by=log.user_id
        ))

    # Add assignment logs
    for log in service_req.workflows:
        all_logs.append(TicketWorkFlowOut(
            id=log.id,
            ticket_id=log.ticket_id,
            type="audit",
            action_taken=log.action_taken,
            created_at=log.action_time,
            action_by=log.action_by
        ))

    # Sort all logs by created_at
    user_ids = [t.action_by for t in all_logs]

    # fetch all user names from auth db in one go
    users = auth_db.query(Users.id, Users.full_name).filter(
        Users.id.in_(user_ids)).all()
    user_map = {uid: uname for uid, uname in users}

    for l in all_logs:
        l.action_by_name = user_map.get(l.action_by, "Unknown User")

    all_logs.sort(key=lambda x: x.created_at, reverse=True)
    print("service tickets ", service_req)
    attachments_out = []
    if service_req.file_data:
        attachments_out.append(
            {
                "file_name": service_req.file_name,
                "content_type": service_req.content_type,
                # Convert binary to base64 so it can be sent safely in JSON
                "file_data_base64": base64.b64encode(service_req.file_data).decode('utf-8')
            }
        )

    # Step 5: Return as schema
    return ComplaintDetailsResponse.model_validate(
        {
            **service_req.__dict__,
            "category": category_name,
            "space_name": service_req.space.name if service_req.space else None,
            "building_name": service_req.space.building.name if service_req.space and service_req.space.building else None,
            "site_name": service_req.site.name if service_req.site else None,
            "closed_date": service_req.closed_date.isoformat() if service_req.closed_date else None,
            "assigned_to_name": assigned_to_name,
            "logs": all_logs,
            "can_escalate": service_req.can_escalate,
            "can_reopen": service_req.can_reopen,
            "is_overdue": service_req.is_overdue,
            "attachments": attachments_out,
        }
    )


async def create_ticket(
    background_tasks: BackgroundTasks,
    session: Session,
    auth_db: Session,
    data: TicketCreate,
    user: UserToken,
    file: UploadFile = None
):
    account_type = user.account_type.lower()
    # Create Ticket (defaults to OPEN)
    space = (
        session.query(Space)
        .options(joinedload(Space.org))
        .filter(Space.id == data.space_id)
        .first()
    )

    if not space:
        return error_response(
            message=f"Invalid space",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=400
        )

    tenant_id = None
    title = None

    category_name = session.query(
        TicketCategory.category_name).filter(TicketCategory.id == data.category_id).scalar()

    if account_type == UserAccountType.ORGANIZATION:
        tenant_id = data.tenant_id
        title = data.title
    else:
        tenant_id = session.query(Tenant.id).filter(and_(
            Tenant.user_id == user.user_id, Tenant.is_deleted == False)).scalar()
        # ✅ FIXED: Case-insensitive search with site check

        title = f"{category_name} - {space.name}"

        if not tenant_id:
            return error_response(
                message=f"Invalid tenant",
                status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
                http_status=400
            )

    if not category_name:
        # ✅ Better error message to debug
        return error_response(
            message=f"Invalid category",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=400
        )

    new_ticket = Ticket(
        org_id=space.org_id,
        site_id=space.site_id if space.site_id else data.site_id,
        space_id=data.space_id,
        tenant_id=tenant_id,
        category_id=data.category_id,
        title=title,
        description=data.description,
        status=TicketStatus.OPEN,
        created_by=user.user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        preferred_time=data.preferred_time,
        request_type=data.request_type,
        priority=data.priority if hasattr(
            data, "priority") else PriorityType.low,
                # ✅ Add assigned_to and vendor_id fields
        assigned_to=data.assigned_to if hasattr(data, "assigned_to") else None,
        vendor_id=data.vendor_id if hasattr(data, "vendor_id") else None
    )
    if file and file.filename:
        file_bytes = await file.read()
        new_ticket.file_name = file.filename
        new_ticket.content_type = file.content_type or "application/octet-stream"
        new_ticket.file_data = file_bytes  # 👈 store binary data directly

    session.add(new_ticket)
    session.flush()  # needed to get ticket_id

    # Fetch SLA Policy for auto-assignment
    created_by_user = (
        auth_db.query(Users)
        .filter(Users.id == user.user_id)
        .scalar()
    )

    assigned_to_user = None
    sla = None

    # ✅ UPDATED LOGIC: Use provided assigned_to OR fallback to default contact
    assigned_to = None
    
    # First priority: Use assigned_to from request if provided
    if hasattr(data, 'assigned_to') and data.assigned_to:
        assigned_to = data.assigned_to
    # Second priority: Use SLA default contact
    elif new_ticket.category and new_ticket.category.sla_policy:
        sla = new_ticket.category.sla_policy
        assigned_to = sla.default_contact if sla else None

    # Update the ticket with the final assigned_to value
    if assigned_to:
        new_ticket.assigned_to = assigned_to
        
        assigned_to_user = (
            auth_db.query(Users)
            .filter(Users.id == assigned_to)
            .scalar()
        )

        # Only create assignment log if this is different from initial value
        if not hasattr(data, 'assigned_to') or not data.assigned_to:
            assignment_log = TicketAssignment(
                ticket_id=new_ticket.id,
                assigned_from=user.user_id,
                assigned_to=assigned_to,
                reason="Auto-assigned via SLA"
            )
            session.add(assignment_log)

        # Send notification to assigned user
        notification = Notification(
            user_id=assigned_to,
            type=NotificationType.alert,
            title="New Ticket Assigned",
            message=f"You have been assigned ticket {new_ticket.ticket_no}: {title}",
            posted_date=datetime.utcnow(),
            priority=PriorityType(new_ticket.priority),
            read=False,
            is_deleted=False
        )
        session.add(notification)

    # Log Workflow History
    workflow_log = TicketWorkflow(
        ticket_id=new_ticket.id,
        action_by=user.user_id,
        old_status=None,
        new_status=TicketStatus.OPEN.value,
        action_taken=f"Ticket Created by {created_by_user.full_name}"
    )
    session.add(workflow_log)

    session.commit()
    session.refresh(new_ticket)

        # ✅ NEW: Fetch vendor name and assigned to name
    assigned_to_name = ""
    vendor_name = ""

    # Fetch assigned_to user name
    if new_ticket.assigned_to:
        assigned_user = (
            auth_db.query(Users)
            .filter(Users.id == new_ticket.assigned_to)
            .first()
        )
        if assigned_user:
            assigned_to_name = assigned_user.full_name or ""

    # Fetch vendor name (assuming you have a Vendor model)
    if new_ticket.vendor_id:
        vendor = (
            session.query(Vendor)  # Replace with your actual Vendor model
            .filter(Vendor.id == new_ticket.vendor_id)
            .first()
        )
        if vendor:
            vendor_name = vendor.name or ""  # Replace with actual vendor name field
    # email
    if assigned_to_user:
        send_ticket_created_email(
            background_tasks, session, new_ticket, created_by_user, assigned_to_user)

    return TicketOut.model_validate(
        {
            **new_ticket.__dict__,
            "category": new_ticket.category.category_name,
            # ✅ Include the names in response
            "assigned_to_name": assigned_to_name,
            "vendor_name": vendor_name
        }
    )


def escalate_ticket(
    background_tasks: BackgroundTasks,
    db: Session,
    auth_db: Session,
    data: TicketActionRequest,
    user: UserToken
):

    # Fetch ticket
    ticket = db.execute(
        select(Ticket).where(Ticket.id == data.ticket_id)
    ).scalar_one_or_none()

    if not ticket:
        return error_response(
            message=f"Invalid Ticket",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=400
        )

    if (
        not ticket.can_escalate
        or (str(ticket.created_by) != str(data.action_by) and (user.account_type != UserAccountType.ORGANIZATION))
    ):
        return error_response(
            message=f"Not authorize to perform this action",
            status_code=str(AppStatusCode.UNAUTHORIZED_ACTION),
            http_status=400
        )

    # Fetch SLA Policy using category_id
    if not ticket.category or not ticket.category.sla_policy or not ticket.category.sla_policy.escalation_contact:
        return error_response(
            message="No escalation contact configured for SLA",
            status_code=str(AppStatusCode.INVALID_INPUT),
            http_status=400
        )

    old_status = ticket.status
    sla = ticket.category.sla_policy

    # Update ticket
    ticket.status = TicketStatus.ESCALATED
    ticket.assigned_to = sla.escalation_contact
    ticket.updated_at = datetime.utcnow()

    assigned_to_user = (
        auth_db.query(Users.full_name)
        .filter(Users.id == sla.escalation_contact)
        .scalar()
    )

    if not assigned_to_user:
        return error_response(
            message="Assigned user doesnt exist in the system",
            status_code=str(AppStatusCode.USER_USERNAME_IS_NOTREGISTERED),
            http_status=400
        )

    # Assignment Log
    assignment_log = TicketAssignment(
        ticket_id=ticket.id,
        assigned_from=sla.default_contact,
        assigned_to=sla.escalation_contact,
        reason=data.comment
    )

    # Notification Log
    # Get action user details for logs
    action_by_user = auth_db.query(Users).filter(
        Users.id == data.action_by).first()
    action_by_name = action_by_user.full_name if action_by_user else "Unknown User"

    recipient_ids = []

    # Add assigned user
    if ticket.assigned_to:
        recipient_ids.append(ticket.assigned_to)

    # Add action user
    recipient_ids.append(data.action_by)

    # Add tenant if exists
    if ticket.tenant and ticket.tenant.user_id:
        recipient_ids.append(ticket.tenant.user_id)

    # Add admin users using the fetch_role_admin function
    admin_user_ids = fetch_role_admin(
        auth_db, action_by_user.org_id if action_by_user else None)

    # Handle both success and error responses from fetch_role_admin
    if isinstance(admin_user_ids, list):
        recipient_ids.extend([a["user_id"] for a in admin_user_ids])

    recipient_ids = list(set(recipient_ids))

    # Create notifications for all recipients (instead of just one)
    notifications = []
    for recipient_id in recipient_ids:
        notification = Notification(
            user_id=recipient_id,
            type=NotificationType.alert,
            title="Ticket Escalated",
            message=f"Ticket {ticket.ticket_no} have been escalated & assigned to {assigned_to_user} by {action_by_name}",
            posted_date=datetime.utcnow(),
            priority=PriorityType(ticket.priority),
            read=False,
            is_deleted=False
        )
        notifications.append(notification)

    # Workflow Log
    workflow_log = TicketWorkflow(
        ticket_id=ticket.id,
        action_by=data.action_by,
        old_status=old_status.value if old_status else None,
        new_status=TicketStatus.ESCALATED,
        action_taken=f"Ticket {ticket.ticket_no} escalated & assigned to {assigned_to_user}"
    )

    objects_to_add = [assignment_log, workflow_log] + notifications

    # Comment Log
    if data.comment:
        objects_to_add.append(TicketComment(
            ticket_id=ticket.id,
            user_id=data.action_by,
            comment_text=data.comment
        ))

    db.add_all(objects_to_add)
    db.commit()
    db.refresh(ticket)

    # email
    emails = (
        auth_db.query(Users.email)
        .filter(Users.id.in_(recipient_ids))
        .all()
    )
    email_list = [e[0] for e in emails]
    send_ticket_escalated_email(
        background_tasks, db, ticket, assigned_to_user, email_list)

    updated_ticket = TicketOut.model_validate(
        {
            **ticket.__dict__,
            "category": ticket.category.category_name
        }
    )
    return success_response(
        data=updated_ticket,
        message="Ticket escalated successfully"
    )


async def resolve_ticket(
        background_tasks: BackgroundTasks,
        db: Session,
        auth_db: Session,
        data: TicketActionRequest,
        user: UserToken,
        file: UploadFile = None
):
    ticket = db.execute(select(Ticket).where(
        Ticket.id == data.ticket_id)).scalar_one_or_none()

    if not ticket:
        return error_response(
            message=f"Ticket not found",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=400
        )

    if (
        ticket.status == TicketStatus.CLOSED
        or str(ticket.assigned_to) != str(data.action_by) and (user.account_type != UserAccountType.ORGANIZATION)
    ):
        return error_response(
            message=f"Not authorize to perform this action",
            status_code=str(AppStatusCode.UNAUTHORIZED_ACTION),
            http_status=400
        )

    old_status = ticket.status
    ticket.status = TicketStatus.CLOSED
    ticket.closed_date = datetime.utcnow()
    ticket.updated_at = datetime.utcnow()

    # File attachment logic (same as create_ticket)
    if file and file.filename:
        file_bytes = await file.read()
        ticket.file_name = file.filename
        ticket.content_type = file.content_type or "application/octet-stream"
        ticket.file_data = file_bytes  # 👈 store binary data directly

    created_by_user = (
        auth_db.query(Users)
        .filter(Users.id == ticket.created_by)
        .scalar()
    )

    action_by_user = (
        auth_db.query(Users)
        .filter(Users.id == data.action_by)
        .scalar()
    )

    workflow_log = TicketWorkflow(
        ticket_id=data.ticket_id,
        action_by=data.action_by,
        old_status=old_status.value if old_status else None,
        new_status=TicketStatus.CLOSED,
        action_taken=f"Ticket {ticket.ticket_no} closed by {action_by_user.full_name}"
    )

    # Notification Log
    # Get action user details for logs
    recipient_ids = []

    # Add assigned user
    if ticket.assigned_to:
        recipient_ids.append(ticket.assigned_to)

    # Add action user
    recipient_ids.append(data.action_by)

    # Add tenant if exists
    if ticket.tenant and ticket.tenant.user_id:
        recipient_ids.append(ticket.tenant.user_id)

    # Add admin users using the fetch_role_admin function
    admin_user_ids = fetch_role_admin(
        auth_db, action_by_user.org_id if action_by_user else None)

    # Handle both success and error responses from fetch_role_admin
    if isinstance(admin_user_ids, list):
        recipient_ids.extend([a["user_id"] for a in admin_user_ids])

    recipient_ids = list(set(recipient_ids))

    # Create notifications for all recipients (instead of just one)
    notifications = []
    for recipient_id in recipient_ids:
        notification = Notification(
            user_id=recipient_id,
            type=NotificationType.alert,
            title="Ticket Closed",
            message=f"Ticket {ticket.ticket_no} closed by {action_by_user.full_name}",
            posted_date=datetime.utcnow(),
            priority=PriorityType(ticket.priority),
            read=False,
            is_deleted=False
        )
        notifications.append(notification)

     # Prepare all objects to add
    objects_to_add = [workflow_log] + notifications

    # Comment Log
    if data.comment:
        objects_to_add.append(TicketComment(
            ticket_id=ticket.id,
            user_id=data.action_by,
            comment_text=data.comment
        ))

    db.add_all(objects_to_add)
    db.commit()
    db.refresh(ticket)

    # email
    emails = (
        auth_db.query(Users.email)
        .filter(Users.id.in_(recipient_ids))
        .all()
    )
    email_list = [e[0] for e in emails]
    context = {
        "created_by_name": created_by_user.full_name,
        "closed_by": action_by_user.full_name,
        "ticket_no": ticket.ticket_no,
        "feedback": data.comment if data.comment else 'NA'
    }

    send_ticket_closed_email(background_tasks, db, context, email_list)

    updated_ticket = TicketOut.model_validate(
        {
            **ticket.__dict__,
            "category": ticket.category.category_name
        }
    )
    return success_response(
        data=updated_ticket,
        message="Ticket closed successfully"
    )


def reopen_ticket(
        background_tasks: BackgroundTasks,
        db: Session,
        auth_db: Session,
        data: TicketActionRequest,
        user: UserToken
):
    ticket = db.execute(select(Ticket).where(
        Ticket.id == data.ticket_id)).scalar_one_or_none()
    if not ticket:
        raise Exception("Ticket not found")

    if (
        not ticket.can_reopen
        or str(ticket.created_by) != str(data.action_by) and (user.account_type != UserAccountType.ORGANIZATION)
    ):
        return error_response(
            message=f"Not authorize to perform this action",
            status_code=str(AppStatusCode.UNAUTHORIZED_ACTION),
            http_status=400
        )

    old_status = ticket.status
    ticket.status = TicketStatus.REOPENED
    ticket.updated_at = datetime.utcnow()

    action_by_user = (
        auth_db.query(Users)
        .filter(Users.id == data.action_by)
        .first()
    )

    assigned_to_user = (
        auth_db.query(Users.full_name)
        .filter(Users.id == ticket.assigned_to)
        .scalar()
    )

    workflow_log = TicketWorkflow(
        ticket_id=data.ticket_id,
        action_by=data.action_by,
        old_status=old_status.value if old_status else None,
        new_status=TicketStatus.REOPENED,
        action_taken=f"Ticket {ticket.ticket_no} reopened by {action_by_user.full_name}"
    )

    # Notification Log
    recipient_ids = []

    # Add assigned user
    if ticket.assigned_to:
        recipient_ids.append(ticket.assigned_to)

    # Add action user
    recipient_ids.append(data.action_by)

    # Add tenant if exists
    if ticket.tenant and ticket.tenant.user_id:
        recipient_ids.append(ticket.tenant.user_id)

    # Add admin users using the fetch_role_admin function
    admin_user_ids = fetch_role_admin(
        auth_db, action_by_user.org_id if action_by_user else None)

    # Handle both success and error responses from fetch_role_admin
    if isinstance(admin_user_ids, list):
        recipient_ids.extend([a["user_id"] for a in admin_user_ids])

    recipient_ids = list(set(recipient_ids))

    # Create notifications for all recipients
    notifications = []
    for recipient_id in recipient_ids:
        notification = Notification(
            user_id=recipient_id,
            type=NotificationType.alert,
            title="Ticket Reopened",
            message=f"Ticket {ticket.ticket_no} reopened by {action_by_user.full_name}",
            posted_date=datetime.utcnow(),
            priority=PriorityType(ticket.priority),
            read=False,
            is_deleted=False
        )
        notifications.append(notification)

    objects_to_add = [workflow_log] + notifications

    if data.comment:
        objects_to_add.append(TicketComment(
            ticket_id=ticket.id,
            user_id=data.action_by,
            comment_text=data.comment
        ))

    db.add_all(objects_to_add)
    db.commit()
    db.refresh(ticket)

    # Email
    emails = (
        auth_db.query(Users.email)
        .filter(Users.id.in_(recipient_ids))
        .all()
    )
    email_list = [e[0] for e in emails]

    context = {
        "assigned_to": assigned_to_user,
        "reopened_by": action_by_user.full_name,
        "ticket_no": ticket.ticket_no
    }

    send_ticket_reopened_email(background_tasks, db, context, email_list)

    updated_ticket = TicketOut.model_validate(
        {
            **ticket.__dict__,
            "category": ticket.category.category_name
        }
    )
    return success_response(
        data=updated_ticket,
        message="Ticket reopened successfully"
    )


def on_hold_ticket(
    background_tasks: BackgroundTasks,
    db: Session,
    auth_db: Session,
    data: TicketActionRequest,
    user: UserToken
):
    ticket = db.execute(select(Ticket).where(
        Ticket.id == data.ticket_id)).scalar_one_or_none()
    if not ticket:
        raise Exception("Ticket not found")

    if (
        ticket.status in (TicketStatus.CLOSED, TicketStatus.ON_HOLD)
        or str(ticket.assigned_to) != str(data.action_by) and (user.account_type != UserAccountType.ORGANIZATION)
    ):
        return error_response(
            message=f"Not authorize to perform this action",
            status_code=str(AppStatusCode.UNAUTHORIZED_ACTION),
            http_status=400
        )

    old_status = ticket.status
    ticket.status = TicketStatus.ON_HOLD
    ticket.updated_at = datetime.utcnow()

    action_by_user = (
        auth_db.query(Users)
        .filter(Users.id == data.action_by)
        .scalar()
    )

    created_by_user = (
        auth_db.query(Users)
        .filter(Users.id == ticket.created_by)
        .scalar()
    )

    workflow_log = TicketWorkflow(
        ticket_id=data.ticket_id,
        action_by=data.action_by,
        old_status=old_status.value if old_status else None,
        new_status=TicketStatus.ON_HOLD,
        action_taken=f"Ticket {ticket.ticket_no} put on hold by {action_by_user.full_name}"
    )

    # Notification Log
    recipient_ids = []

    # Add assigned user
    if ticket.assigned_to:
        recipient_ids.append(ticket.assigned_to)

    # Add action user
    recipient_ids.append(data.action_by)

    # Add tenant if exists
    if ticket.tenant and ticket.tenant.user_id:
        recipient_ids.append(ticket.tenant.user_id)

    # Add admin users using the fetch_role_admin function
    admin_user_ids = fetch_role_admin(
        auth_db, action_by_user.org_id if action_by_user else None)

    # Handle both success and error responses from fetch_role_admin
    if isinstance(admin_user_ids, list):
        recipient_ids.extend([a["user_id"] for a in admin_user_ids])

    recipient_ids = list(set(recipient_ids))

    # Create notifications for all recipients
    notifications = []
    for recipient_id in recipient_ids:
        notification = Notification(
            user_id=recipient_id,
            type=NotificationType.alert,
            title="Ticket On hold",
            message=f"Ticket {ticket.ticket_no} put on hold by {action_by_user.full_name}",
            posted_date=datetime.utcnow(),
            priority=PriorityType(ticket.priority),
            read=False,
            is_deleted=False
        )
        notifications.append(notification)

    objects_to_add = [workflow_log] + notifications

    if data.comment:
        objects_to_add.append(TicketComment(
            ticket_id=ticket.id,
            user_id=data.action_by,
            comment_text=data.comment
        ))

    db.add_all(objects_to_add)
    db.commit()
    db.refresh(ticket)

    # Email
    emails = (
        auth_db.query(Users.email)
        .filter(Users.id.in_(recipient_ids))
        .all()
    )
    email_list = [e[0] for e in emails]

    context = {
        "created_by": created_by_user.full_name,
        "hold_reason": data.comment if data.comment else None,
        "ticket_no": ticket.ticket_no
    }

    send_ticket_onhold_email(background_tasks, db, context, email_list)

    updated_ticket = TicketOut.model_validate(
        {
            **ticket.__dict__,
            "category": ticket.category.category_name
        }
    )
    return success_response(
        data=updated_ticket,
        message="Ticket put on hold successfully"
    )


def return_ticket(background_tasks: BackgroundTasks, db: Session, auth_db: Session, data: TicketActionRequest):
    ticket = db.execute(select(Ticket).where(
        Ticket.id == data.ticket_id)).scalar_one_or_none()
    if not ticket:
        raise Exception("Ticket not found")

    # Fetch SLA Policy for auto-assignment
    sla = db.execute(
        select(SlaPolicy).where(SlaPolicy.id == Ticket.category_id)
    ).scalar_one_or_none()

    assigned_to = sla.default_contact if sla else None

    old_status = ticket.status
    ticket.status = TicketStatus.RETURNED
    ticket.assigned_to = assigned_to
    ticket.updated_at = datetime.utcnow()

    action_by_user = (
        auth_db.query(Users)
        .filter(Users.id == data.action_by)
        .scalar()
    )

    created_by_user = (
        auth_db.query(Users)
        .filter(Users.id == ticket.created_by)
        .scalar()
    )

    assignment = TicketAssignment(
        ticket_id=data.ticket_id,
        assigned_from=data.action_by,
        assigned_to=assigned_to,
        reason=data.comment or "Ticket Returned"
    )

    workflow = TicketWorkflow(
        ticket_id=data.ticket_id,
        action_by=data.action_by,
        old_status=old_status.value if old_status else None,
        new_status=TicketStatus.RETURNED,
        action_taken=data.comment or "Ticket Returned to Another User"
    )

    # Notification

    recipient_ids = []

    # Add assigned user
    if ticket.assigned_to:
        recipient_ids.append(ticket.assigned_to)

    # Add action user
    recipient_ids.append(data.action_by)

    # Add tenant if exists
    if ticket.tenant and ticket.tenant.user_id:
        recipient_ids.append(ticket.tenant.user_id)

    # Add admin users using the fetch_role_admin function
    admin_user_ids = fetch_role_admin(
        auth_db, action_by_user.org_id if action_by_user else None)

    # Handle both success and error responses from fetch_role_admin
    if isinstance(admin_user_ids, list):
        recipient_ids.extend([a["user_id"] for a in admin_user_ids])

    recipient_ids = list(set(recipient_ids))

    # Create notifications for all recipients
    notifications = []
    for recipient_id in recipient_ids:
        notification = Notification(
            user_id=recipient_id,
            type=NotificationType.alert,
            title="Ticket Returned",
            message=f"Ticket {ticket.ticket_no} put on returned by {action_by_user.full_name}",
            posted_date=datetime.utcnow(),
            priority=PriorityType(ticket.priority),
            read=False,
            is_deleted=False
        )
        notifications.append(notification)

    objects_to_add = [workflow, assignment] + notifications

    if data.comment:
        objects_to_add.append(TicketComment(
            ticket_id=ticket.id,
            user_id=data.action_by,
            comment_text=data.comment
        ))

    db.add_all(objects_to_add)
    db.commit()
    db.refresh(ticket)

    # Email
    emails = (
        auth_db.query(Users.email)
        .filter(Users.id.in_(recipient_ids))
        .all()
    )
    email_list = [e[0] for e in emails]

    context = {
        "created_by": created_by_user.full_name,
        "return_reason": data.comment if data.comment else None,
        "ticket_no": ticket.ticket_no
    }

    send_ticket_return_email(background_tasks, db, context, email_list)

    updated_ticket = TicketOut.model_validate(
        {
            **ticket.__dict__,
            "category": ticket.category.category_name
        }
    )
    return success_response(
        data=updated_ticket,
        message="Ticket returned successfully"
    )


def add_comment(payload: AddCommentRequest, db: Session):
    ticket = db.query(Ticket).filter(Ticket.id == payload.ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    new_comment = TicketComment(
        ticket_id=payload.ticket_id,
        user_id=payload.user_id,
        comment_text=payload.comment_text
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return {"message": "Comment added successfully", "comment_id": new_comment.id}


def add_reaction(payload: AddReactionRequest, db: Session):

    comment = db.query(TicketComment).filter(
        TicketComment.id == payload.comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    reaction = TicketReaction(
        comment_id=payload.comment_id,
        user_id=payload.user_id,
        reaction=payload.reaction
    )
    db.add(reaction)
    db.commit()
    db.refresh(reaction)
    return {"message": "Reaction added successfully", "reaction_id": reaction.id}


def add_feedback(payload: AddFeedbackRequest, db: Session):

    ticket = db.query(Ticket).filter(Ticket.id == payload.ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status != "closed":
        raise HTTPException(
            status_code=403, detail="Feedback can only be added after resolution")

    feedback = TicketFeedback(
        ticket_id=payload.ticket_id,
        user_id=payload.user_id,
        feedback=payload.feedback.upper(),
        remark=payload.remark
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return {"message": "Feedback recorded", "feedback_id": feedback.id}


def send_ticket_created_email(background_tasks, db, new_ticket, created_by_user, assigned_to_user):
    email_helper = EmailHelper()

    recipients = [created_by_user.email, assigned_to_user.email]

    context = {
        "status": TicketStatus.OPEN.value,
        "assigned_to": assigned_to_user.full_name,
        "ticket_no": new_ticket.ticket_no,
        "created_by_name": created_by_user.full_name,
    }

    background_tasks.add_task(
        email_helper.send_email,
        db=db,
        template_code="ticket_created",
        recipients=recipients,
        subject=f"New Ticket Created - {new_ticket.ticket_no}",
        context=context,
    )


def send_ticket_escalated_email(background_tasks, db, ticket, assigned_to_name, recipients):
    email_helper = EmailHelper()

    context = {
        "priority": ticket.priority,
        "assigned_to": assigned_to_name,
        "ticket_no": ticket.ticket_no
    }

    background_tasks.add_task(
        email_helper.send_email,
        db=db,
        template_code="ticket_escalated",
        recipients=recipients,
        subject=f"Ticket Escalated - {ticket.ticket_no}",
        context=context,
    )


def send_ticket_closed_email(background_tasks, db, data, recipients):
    email_helper = EmailHelper()

    background_tasks.add_task(
        email_helper.send_email,
        db=db,
        template_code="ticket_closed",
        recipients=recipients,
        subject=f"Ticket Resolved - {data['ticket_no']}",
        context=data,
    )


def send_ticket_reopened_email(background_tasks, db, data, recipients):
    email_helper = EmailHelper()

    background_tasks.add_task(
        email_helper.send_email,
        db=db,
        template_code="ticket_reopened",
        recipients=recipients,
        subject=f"Ticket Reopened - {data['ticket_no']}",
        context=data,
    )


def send_ticket_onhold_email(background_tasks, db, data, recipients):
    email_helper = EmailHelper()

    background_tasks.add_task(
        email_helper.send_email,
        db=db,
        template_code="ticket_on_hold",
        recipients=recipients,
        subject=f"Ticket On hold - {data['ticket_no']}",
        context=data,
    )


def send_ticket_return_email(background_tasks, db, data, recipients):
    email_helper = EmailHelper()

    background_tasks.add_task(
        email_helper.send_email,
        db=db,
        template_code="ticket_return",
        recipients=recipients,
        subject=f"Ticket Return -{data['ticket_no']}",
        context=data,
    )


def send_ticket_update_status_email(background_tasks, db, data, recipients):
    email_helper = EmailHelper()

    background_tasks.add_task(
        email_helper.send_email,
        db=db,
        template_code="ticket_update_status",
        recipients=recipients,
        subject=f"Ticket Update Status -{data['ticket_no']}",
        context=data,
    )


def send_ticket_update_assigned_to_email(background_tasks, db, data, recipients):
    email_helper = EmailHelper()

    background_tasks.add_task(
        email_helper.send_email,
        db=db,
        template_code="ticket_update_assigned_to",
        recipients=recipients,
        subject=f"Ticket Update Assigned_to -{data['ticket_no']}",
        context=data,
    )


def send_ticket_post_comment_email(background_tasks, db, data, recipients):
    email_helper = EmailHelper()

    background_tasks.add_task(
        email_helper.send_email,
        db=db,
        template_code="ticket_post_comment",
        recipients=recipients,
        subject=f"Ticket Post Comment -{data['ticket_no']}",
        context=data,
    )

# for view ------------------------

# for portal/web


def get_ticket_details_by_Id(db: Session, auth_db: Session, ticket_id: str):
    """
    Fetch full Tickets details along with all related comments and logs
    """
    # Step 1: Fetch service request with joins for related data
    service_req = (
        db.query(Ticket)
        .filter(Ticket.id == ticket_id)
        .first()
    )

    if not service_req:
        raise HTTPException(
            status_code=404, detail="Service request not found")

    # Step 2: Get assigned_to from SLA policies based on category - FIXED
    category_name = service_req.category.category_name if service_req.category else None

    assigned_to_name = None
    # Fetch assigned user full_name from auth.db user table
    assigned_user = (
        auth_db.query(Users)
        .filter(Users.id == service_req.assigned_to)
        .first()
    )
    assigned_to_name = assigned_user.full_name if assigned_user else None

    #  COMMENTS SECTION (TicketComment schema)
    comments = service_req.comments or []

    # Step 3.1: Fetch all reactions in one go
    comment_ids = [c.id for c in comments]
    reactions_all = (
        db.query(TicketReaction)
        .filter(TicketReaction.comment_id.in_(comment_ids))
        .all()
    ) if comment_ids else []

    # Step 3.2: Group reactions by comment_id
    reaction_map = {}
    for r in reactions_all:
        reaction_map.setdefault(r.comment_id, []).append(r)

    # Step 3.3: Fetch comment user names in one go
    comment_user_ids = [c.user_id for c in comments if c.user_id]
    comment_users = (
        auth_db.query(Users.id, Users.full_name)
        .filter(Users.id.in_(comment_user_ids))
        .all()
    ) if comment_user_ids else []
    comment_user_map = {uid: uname for uid, uname in comment_users}

    # Step 3.4: Build comment outputs
    comments_out = []
    for c in comments:
        reactions = [
            {
                "reaction_id": str(r.id),
                "user_id": str(r.user_id),
                "emoji": r.emoji,
                "created_at": r.created_at
            }
            for r in reaction_map.get(c.id, [])
        ]

        comments_out.append(
            TicketCommentOut(
                comment_id=c.id,
                ticket_id=c.ticket_id,
                user_id=c.user_id,
                user_name=comment_user_map.get(c.user_id, "Unknown User"),
                comment_text=c.comment_text,
                created_at=c.created_at,
                reactions=reactions
            )
        )

    # WORKFLOW SECTION (TicketWorkflow schema)
    workflows = service_req.workflows or []

    workflows_out = []
    for w in workflows:
        workflows_out.append(
            TicketWorkflowOut(
                workflow_id=w.id,
                ticket_id=w.ticket_id,
                action_by=w.action_by,
                old_status=getattr(w, "old_status", None),
                new_status=getattr(w, "new_status", None),
                action_taken=w.action_taken,
                action_time=w.action_time
            )
        )

        # ---------------- Add Work Orders ----------------
    ticket_workorders = []

    for wo in service_req.work_orders:
        if wo.is_deleted:  # Skip deleted work orders
            continue
        # Get assigned vendor name from Vendor table
        assigned_to_name = None
        if wo.assigned_to:
            vendor = db.query(Vendor).filter(
                Vendor.id == wo.assigned_to,
                Vendor.is_deleted == False
            ).first()
            assigned_to_name = vendor.name if vendor else None
            # Ticket No from Ticket table
        ticket_no = None
        ticket_data = db.query(Ticket).filter(
            Ticket.id == wo.ticket_id
        ).first()

        if ticket_data:
            ticket_no = ticket_data.ticket_no
        ticket_workorders.append({
            "id": wo.id,
            "wo_no": wo.wo_no,  # <-- Add this line
            "ticket_id": wo.ticket_id,
            "description": wo.description,
            "status": wo.status,
            "ticket_no": ticket_no,
            "assigned_to": wo.assigned_to,
            "assigned_to_name": assigned_to_name,
            "site_name": wo.ticket.site.name if wo.ticket and wo.ticket.site else "",
            "created_at": wo.created_at.isoformat() if wo.created_at else None,
            "updated_at": wo.updated_at.isoformat() if wo.updated_at else None,
        })

    attachments_out = []
    if service_req.file_data:
        attachments_out.append(
            {
                "file_name": service_req.file_name,
                "content_type": service_req.content_type,
                # Convert binary to base64 so it can be sent safely in JSON
                "file_data_base64": base64.b64encode(service_req.file_data).decode('utf-8')
            }
        )
    # Step 5: Return as schema
    return TicketDetailsResponse.model_validate(
        {
            **service_req.__dict__,
            "category": category_name,
            "space_name": service_req.space.name if service_req.space else None,
            "building_name": service_req.space.building.name if service_req.space and service_req.space.building else None,
            "site_name": service_req.site.name if service_req.site else None,
            "closed_date": service_req.closed_date.isoformat() if service_req.closed_date else None,
            "assigned_to_name": assigned_to_name,
            "comments": comments_out,
            "logs": workflows_out,
            "workorders": ticket_workorders,  # <-- Add this
            "can_escalate": service_req.can_escalate,
            "can_reopen": service_req.can_reopen,
            "is_overdue": service_req.is_overdue,
            "attachments": attachments_out,
        }
    )


# update status
def update_ticket_status(
    background_tasks: BackgroundTasks,
    db: Session,
    auth_db: Session,
    data: TicketUpdateRequest,
    current_user: UserToken
):
    # Fetch ticket
    ticket = db.execute(
        select(Ticket).where(Ticket.id == data.ticket_id)
    ).scalar_one_or_none()

    if not ticket:
        return error_response(
            message="Invalid Ticket",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=400
        )

    old_status = ticket.status

    # Update ticket
    ticket.status = data.new_status
    ticket.updated_at = datetime.utcnow()

    if data.new_status == TicketStatus.CLOSED:
        ticket.closed_date = datetime.utcnow()

    created_by_user = (
        auth_db.query(Users)
        .filter(Users.id == ticket.created_by)
        .scalar()
    )

    action_by_user = auth_db.query(Users).filter(
        Users.id == current_user.user_id).first()
    action_by_name = action_by_user.full_name if action_by_user else "Unknown User"

    # Workflow Log
    workflow_log = TicketWorkflow(
        ticket_id=ticket.id,
        action_by=current_user.user_id,
        old_status=old_status.value if old_status else None,
        new_status=data.new_status,
        action_taken=f"Ticket {ticket.ticket_no} status changed from {old_status.value} to {data.new_status.value} by {action_by_name}"
    )

    # Notification Log

    recipient_ids = []

    if ticket.assigned_to:
        recipient_ids.append(ticket.assigned_to)

    recipient_ids.append(current_user.user_id)  # action_by

    if ticket.tenant and ticket.tenant.user_id:
        recipient_ids.append(ticket.tenant.user_id)

    admin_user_ids = fetch_role_admin(auth_db, current_user.org_id)

    recipient_ids.extend([a["user_id"] for a in admin_user_ids])

    recipient_ids = list(set(recipient_ids))

    notifications = []
    for recipient_id in recipient_ids:
        notification = Notification(
            user_id=recipient_id,
            type=NotificationType.alert,
            title=f"Ticket {data.new_status.value.capitalize()}",
            message=f"Ticket {ticket.ticket_no} marked as {data.new_status.value} by {action_by_name}",
            posted_date=datetime.utcnow(),
            priority=PriorityType(ticket.priority),
            read=False,
            is_deleted=False
        )
        notifications.append(notification)

    objects_to_add = [workflow_log] + notifications

    db.add_all(objects_to_add)
    db.commit()
    db.refresh(ticket)

    # Email
    emails = (
        auth_db.query(Users.email)
        .filter(Users.id.in_(recipient_ids))
        .all()
    )
    email_list = [e[0] for e in emails]

    context = {
        "created_by": created_by_user.full_name,
        "ticket_no": ticket.ticket_no,
        "updated_by": action_by_name,
        "new_status": data.new_status.value,
    }

    send_ticket_update_status_email(background_tasks, db, context, email_list)
    # Response
    updated_ticket = TicketOut.model_validate(
        {
            **ticket.__dict__,
            "category": ticket.category.category_name if ticket.category else None
        }
    )

    return success_response(
        data=updated_ticket,
        message=f"Ticket status updated to {data.new_status.value} successfully"
    )


def update_ticket_assigned_to(background_tasks: BackgroundTasks, session: Session, auth_db: Session, data: TicketAssignedToRequest, current_user: UserToken):
    ticket = (
        session.query(Ticket)
        .filter(Ticket.id == data.ticket_id)
        .first()
    )

    if not ticket:
        return error_response(
            message="Invalid Ticket",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=400
        )

    # Get new assigned_to user details
    assigned_to_user = (
        auth_db.query(Users)
        .filter(Users.id == data.assigned_to)
        .scalar()
    )

    if not assigned_to_user:
        return error_response(
            message="Invalid assigned_to user",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=400
        )
    action_by = current_user.user_id
    # Get action_by user details
    action_by_user = (
        auth_db.query(Users)
        .filter(Users.id == action_by)
        .scalar()
    )

    # Update ticket assigned_to (EXACTLY like create_ticket)
    ticket.assigned_to = data.assigned_to
    ticket.updated_at = datetime.utcnow()

    # Assignment Log (EXACTLY like create_ticket pattern)
    assignment_log = TicketAssignment(
        ticket_id=ticket.id,
        assigned_from=action_by,
        assigned_to=data.assigned_to,
        reason="Manual assignment"
    )

    # Notification Log
    # Collect recipients id
    recipient_ids = []

    if ticket.assigned_to:
        recipient_ids.append(ticket.assigned_to)

    recipient_ids.append(current_user.user_id)  # action_by

    if ticket.tenant and ticket.tenant.user_id:
        recipient_ids.append(ticket.tenant.user_id)

    admin_user_ids = fetch_role_admin(auth_db, current_user.org_id)

    recipient_ids.extend([a["user_id"] for a in admin_user_ids])

    recipient_ids = list(set(recipient_ids))

    notifications = []

    for recipient_id in recipient_ids:
        notification = Notification(
            user_id=data.assigned_to,
            type=NotificationType.alert,
            title="Ticket Assigned",
            message=f"You have been assigned ticket {ticket.ticket_no}: {ticket.title}",
            posted_date=datetime.utcnow(),
            priority=PriorityType(ticket.priority),
            read=False,
            is_deleted=False
        )
    notifications.append(notification)

    # Workflow Log
    workflow_log = TicketWorkflow(
        ticket_id=ticket.id,
        action_by=action_by,
        old_status=None,
        new_status=None,
        # Like "Ticket Created by {created_by_user.full_name}"
        action_taken=f"Ticket assigned to {assigned_to_user.full_name} by {action_by_user.full_name if action_by_user else 'Unknown User'}"
    )

    objects_to_add = [workflow_log, assignment_log] + notifications

    session.add_all(objects_to_add)
    session.commit()
    session.refresh(ticket)

    # Email
    emails = (
        auth_db.query(Users.email)
        .filter(Users.id.in_(recipient_ids))
        .all()
    )
    email_list = [e[0] for e in emails]

    context = {
        "assigned_to": assigned_to_user.full_name,  # The person who got assigned
        "ticket_no": ticket.ticket_no,
        "assigned_by": action_by_user.full_name if action_by_user else "System"
    }

    send_ticket_update_assigned_to_email(
        background_tasks, session, context, email_list)

    # Response
    updated_ticket = TicketOut.model_validate(
        {
            **ticket.__dict__,
            "category": ticket.category.category_name if ticket.category else None
        }
    )

    return success_response(
        data=updated_ticket,
        message=f"Ticket assigned to {assigned_to_user.full_name} successfully"
    )


def post_ticket_comment(background_tasks: BackgroundTasks, session: Session, auth_db: Session, data: TicketCommentRequest, current_user: UserToken):

    ticket = (
        session.query(Ticket)
        .options(joinedload(Ticket.tenant))
        .filter(Ticket.id == data.ticket_id)
        .first()
    )

    if not ticket:
        return error_response(
            message="Invalid Ticket",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=400
        )

    comment = TicketComment(
        ticket_id=data.ticket_id,
        user_id=current_user.user_id,
        comment_text=data.comment,
        created_at=datetime.utcnow()
    )
    session.add(comment)
    session.flush()

    current_user_details = (
        auth_db.query(Users)
        .filter(Users.id == current_user.user_id)
        .scalar()
    )

    # Collect recipients id
    recipient_ids = []

    if ticket.assigned_to:
        recipient_ids.append(ticket.assigned_to)

    recipient_ids.append(current_user.user_id)

    if ticket.tenant and ticket.tenant.user_id:
        recipient_ids.append(ticket.tenant.user_id)

    admin_user_ids = fetch_role_admin(auth_db, current_user.org_id)

    recipient_ids.extend([a["user_id"] for a in admin_user_ids])

    recipient_ids = list(set(recipient_ids))

    notifications = []

    for recipient_id in recipient_ids:
        notification = Notification(
            user_id=recipient_id,
            type=NotificationType.alert,
            title="New Comment on Ticket",
            message=f"{current_user_details.full_name if current_user_details else 'User'} commented on ticket {ticket.ticket_no}: {data.comment[:50]}...",
            posted_date=datetime.utcnow(),
            priority=PriorityType(ticket.priority),
            read=False,
            is_deleted=False
        )
        notifications.append(notification)

    objects_to_add = [comment] + notifications

    session.add_all(objects_to_add)
    session.commit()
    session.refresh(ticket)

    # Get assigned_to user details
    assigned_to_user = None
    if ticket.assigned_to:
        assigned_to_user = (
            auth_db.query(Users)
            .filter(Users.id == ticket.assigned_to)
            .scalar()
        )

    # Email
    emails = (
        auth_db.query(Users.email)
        .filter(Users.id.in_(recipient_ids))
        .all()
    )
    email_list = [e[0] for e in emails]

    context = {
        "assigned_to": assigned_to_user.full_name,
        "ticket_no": ticket.ticket_no,
        "comment_by": current_user_details.full_name,
        "comment": data.comment
    }

    send_ticket_post_comment_email(
        background_tasks, session, context, email_list)

    return success_response(
        data=TicketWorkFlowOut(
            id=comment.id,
            ticket_id=comment.ticket_id,
            type="comment",
            action_taken=comment.comment_text,
            created_at=comment.created_at,
            action_by=comment.user_id,
            action_by_name=current_user_details.full_name
        ),
        message="Comment posted successfully"
    )


def get_ticket_logs(db: Session, auth_db: Session, ticket_id: str):
    # Step 1: Fetch service request with joins for related data
    service_req = (
        db.query(Ticket)
        .filter(Ticket.id == ticket_id)
        .first()
    )

    if not service_req:
        raise HTTPException(
            status_code=404, detail="Service request not found")

    # Combine both logs
    all_logs = []

    # Add workflow logs
    for log in service_req.comments:
        all_logs.append(TicketWorkFlowOut(
            id=log.id,
            ticket_id=log.ticket_id,
            type="comment",
            action_taken=log.comment_text,
            created_at=log.created_at,
            action_by=log.user_id
        ))

    # Add assignment logs
    for log in service_req.workflows:
        all_logs.append(TicketWorkFlowOut(
            id=log.id,
            ticket_id=log.ticket_id,
            type="audit",
            action_taken=log.action_taken,
            created_at=log.action_time,
            action_by=log.action_by
        ))

    # Sort all logs by created_at
    user_ids = [t.action_by for t in all_logs]

    # fetch all user names from auth db in one go
    users = auth_db.query(Users.id, Users.full_name).filter(
        Users.id.in_(user_ids)).all()
    user_map = {uid: uname for uid, uname in users}

    for l in all_logs:
        l.action_by_name = user_map.get(l.action_by, "Unknown User")

    all_logs.sort(key=lambda x: x.created_at, reverse=True)

    # Step 5: Return as schema
    return all_logs


def get_possible_next_statuses(db: Session, ticket_id: str):
    """
    Get possible next statuses for a ticket based on current status
    """
    # Query the ticket from database using your actual Ticket model
    ticket = (
        db.query(Ticket)
        .filter(Ticket.id == ticket_id)
        .first()
    )

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Get current status from your actual ticket
    current_status = ticket.status

    # Define possible next statuses based on business rules
    status_transitions = {
        TicketStatus.OPEN: [
            "closed",
            "escalated",
            "on_hold",
            "in_progress"
        ],
        TicketStatus.CLOSED: [
            "reopened"
        ],
        TicketStatus.RETURNED: [
            "reopened",
            "on_hold",
            "in_progress"
        ],
        TicketStatus.REOPENED: [
            "escalated",
            "closed",
            "in_progress",
            "on_hold"
        ],
        TicketStatus.ESCALATED: [
            "closed",
            "in_progress",
            "on_hold"
        ],
        TicketStatus.IN_PROGRESS: [
            "closed",
            "returned",
            "reopened",
            "escalated",
            "on_hold"
        ],
        TicketStatus.ON_HOLD: [
            "in_progress",
            "closed",
            "escalated"
        ]
    }

    all_statuses = [
        Lookup(id=type.value, name=type.name.capitalize())
        for type in TicketStatus
    ]

    # print("Filter STATUSES:", status_transitions.get(current_status, []))

    possible_next_statuses = [
        status for status in all_statuses
        if status.id in status_transitions.get(current_status, [])
    ]

    possible_next_statuses.append(
        Lookup(
            id=current_status.value,
            name=current_status.name.capitalize()
        )
    )

    return possible_next_statuses


def react_on_comment(session: Session, data: TicketReactionRequest, current_user: UserToken):
    """
    Toggle reaction on a comment (user can have only ONE reaction per comment)
    """
    # Validate comment
    if data.emoji not in ALLOWED_EMOJIS:
        return error_response("Invalid emoji type", http_status=400)

    comment = session.query(TicketComment).filter(
        TicketComment.id == data.comment_id).first()
    if not comment:
        return error_response("Invalid Comment", http_status=404)

    # Check if this user already reacted (any emoji)
    existing_reaction = (
        session.query(TicketReaction)
        .filter(
            TicketReaction.comment_id == data.comment_id,
            TicketReaction.user_id == current_user.user_id
        )
        .limit(1)
        .first()
    )

    # If reaction exists
    if existing_reaction:
        # If user clicked the same emoji again → remove (toggle off)
        if existing_reaction.emoji == data.emoji:
            session.delete(existing_reaction)
            session.commit()
            return success_response(
                data={},
                message="Reaction removed successfully"
            )
        else:
            # If user clicked different emoji → update it (switch reaction)
            existing_reaction.emoji = data.emoji
            session.commit()
            return success_response(
                data={
                    "reaction_id": existing_reaction.id,
                    "comment_id": existing_reaction.comment_id,
                    "emoji": existing_reaction.emoji
                },
                message="Reaction updated successfully"
            )

    # No previous reaction → create new
    new_reaction = TicketReaction(
        comment_id=data.comment_id,
        user_id=current_user.user_id,
        emoji=data.emoji
    )
    session.add(new_reaction)
    session.commit()

    return success_response(
        data={
            "reaction_id": new_reaction.id,
            "comment_id": new_reaction.comment_id,
            "emoji": new_reaction.emoji
        },
        message="Reaction added successfully"
    )


def fetch_role_admin(session: Session, org_id):
    """
    Fetch all users in the given organization who have account_type='ORGANIZATION'
    and at least one role containing 'admin'
    """

    # Query for admin users
    admin_users = (
        session.query(Users.id, Users.full_name,
                      Users.email, Users.account_type,)
        .join(UserRoles, Users.id == UserRoles.user_id)
        .join(Roles, Roles.id == UserRoles.role_id)
        .filter(
            and_(
                Users.org_id == org_id,
                func.lower(Users.account_type) == "organization",
                func.lower(Roles.name).like("%admin%"),
                Users.is_deleted == False
            )
        )
        .distinct()
        .all()
    )

    # ✅ If no admins found → return 404 cleanly, not as exception
    if not admin_users:
        return error_response(
            message="No admin users found in this organization",
            http_status=404
        )

    data = [
        {
            "user_id": str(u.id),
            "full_name": u.full_name,
            "email": u.email,
            "account_type": u.account_type,
        }
        for u in admin_users
    ]

    return data


def tickets_filter_priority_lookup(db: Session, org_id: str) -> List[Dict]:
    """
    Get distinct priority values for filter dropdown
    Follows same structure as housekeeping_tasks_filter_status_lookup
    """
    query = (
        db.query(
            Ticket.priority.label("id"),
            Ticket.priority.label("name")
        )
        .filter(Ticket.org_id == org_id)
        .distinct()
        .order_by(Ticket.priority.asc())
    )
    rows = query.all()
    return [{"id": r.id, "name": r.name} for r in rows]


def tickets_filter_status_lookup(db: Session, org_id: str) -> List[Dict]:
    """
    Get distinct status values for filter dropdown
    Follows same structure as housekeeping_tasks_filter_status_lookup
    """
    query = (
        db.query(
            Ticket.status.label("id"),
            Ticket.status.label("name")
        )
        .filter(Ticket.org_id == org_id)
        .distinct()
        .order_by(Ticket.status.asc())
    )
    rows = query.all()
    return [{"id": r.id, "name": r.name} for r in rows]


def ticket_no_lookup(db: Session, org_id: str) -> List[Dict]:
    query = (
        db.query(
            Ticket.id.label("id"),
            Ticket.ticket_no.label("name")
        )
        .filter(
            and_(
                Ticket.org_id == org_id,
                Ticket.status != TicketStatus.CLOSED
            )
        )
        .distinct()
        .order_by(Ticket.ticket_no.asc())
    )

    rows = query.all()
    # Convert UUID to string for JSON serialization
    return [{"id": str(r.id), "name": r.name} for r in rows]
