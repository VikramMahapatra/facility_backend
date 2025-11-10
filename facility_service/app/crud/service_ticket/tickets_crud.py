from datetime import datetime
from sqlalchemy import select
from fastapi import HTTPException, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from uuid import UUID
from sqlalchemy import and_, func
from auth_service.app.models.users import Users
from shared.core.config import Settings
from shared.helpers.email_helper import EmailHelper
from shared.utils.enums import UserAccountType
from ...schemas.system.notifications_schemas import NotificationType, PriorityType
from ...models.system.notifications import Notification
from ...enum.ticket_service_enum import TicketStatus
from ...models.leasing_tenants.tenants import Tenant
from ...models.service_ticket.tickets_category import TicketCategory
from ...models.space_sites.spaces import Space
from ...schemas.mobile_app.help_desk_schemas import TicketWorkFlowOut

from ...models.service_ticket.sla_policy import SlaPolicy
from ...models.service_ticket.tickets_commets import TicketComment
from ...models.service_ticket.tickets_feedback import TicketFeedback
from ...models.service_ticket.tickets_reaction import TicketReaction
from shared.core.schemas import UserToken
from ...models.service_ticket.ticket_assignment import TicketAssignment
from ...models.service_ticket.tickets import Ticket
from ...models.service_ticket.tickets_workflow import TicketWorkflow
from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response, success_response
from ...schemas.service_ticket.tickets_schemas import AddCommentRequest, AddFeedbackRequest, AddReactionRequest, TicketActionRequest, TicketCreate, TicketDetailsResponse, TicketFilterRequest, TicketOut


def build_ticket_filters(db: Session, params: TicketFilterRequest, current_user: UserToken):
    account_type = current_user.account_type.lower()
    if (account_type in (UserAccountType.ORGANIZATION, UserAccountType.STAFF)):
        filters = [Ticket.org_id == current_user.org_id]

        if account_type == UserAccountType.STAFF:
            filters.append(Ticket.assigned_to == current_user.user_id)
    else:
        tenant_id = db.query(Tenant.id).filter(and_(
            Tenant.user_id == current_user.user_id, Tenant.is_deleted == False)).scalar()
        filters = [Ticket.tenant_id == tenant_id]

    if params.site_id:
        filters.append(Ticket.site_id == params.site_id)

    if params.space_id and account_type != UserAccountType.STAFF:
        filters.append(Ticket.space_id == params.space_id)

    if params.status and params.status.lower() != "all":
        status = params.status.lower()

        if status == "overdue":
            # Join TicketCategory -> SlaPolicy to compute overdue tickets
            filters.append(
                and_(
                    Ticket.status != "closed",
                    func.extract('epoch', func.now() - Ticket.created_at) / 60 >
                    func.coalesce(SlaPolicy.resolution_time_mins, 0)
                )
            )

            base_query = (
                db.query(Ticket)
                .join(Ticket.category)
                .join(TicketCategory.sla_policy)
                .filter(*filters)
            )

        elif status == TicketStatus.OPEN.value:
            open_statuses = [
                TicketStatus.OPEN.value,
                TicketStatus.ESCALATED.value,
                TicketStatus.RETURNED.value,
                TicketStatus.REOPENED.value,
                TicketStatus.IN_PROGRESS.value,
            ]
            filters.append(Ticket.status.in_(open_statuses))
            base_query = db.query(Ticket).filter(*filters)

        else:
            filters.append(func.lower(Ticket.status) == status)
            base_query = db.query(Ticket).filter(*filters)

    else:
        base_query = db.query(Ticket).filter(*filters)

    return base_query


def get_tickets(db: Session, params: TicketFilterRequest, current_user: UserToken):
    """Get all tickets with pagination"""

    base_query = build_ticket_filters(db, params, current_user)

    total = base_query.with_entities(func.count(Ticket.id)).scalar()

    if params.skip and params.limit:
        tickets = (
            base_query
            .offset(params.skip)
            .limit(params.limit)
            .all()
        )
    else:
        tickets = base_query.all()

    results = []
    for t in tickets:
        category_name = t.category.category_name if t.category else None
        complaint_data = {
            **t.__dict__,
            "category": category_name,  # override with name
            "can_escalate": t.can_escalate,
            "can_reopen": t.can_reopen,
            "is_overdue": t.is_overdue,
        }

        results.append(TicketOut.model_validate(complaint_data))

    return {"tickets": results, "total": total}


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
            "logs": all_logs,
            "can_escalate": service_req.can_escalate,
            "can_reopen": service_req.can_reopen,
            "is_overdue": service_req.is_overdue,
        }
    )


def create_ticket(background_tasks: BackgroundTasks, session: Session, auth_db: Session, data: TicketCreate, user: UserToken):
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
    category_id = None

    if account_type == UserAccountType.ORGANIZATION:
        tenant_id = data.tenant_id
        title = data.title
        category_id = data.category_id
    else:
        tenant_id = session.query(Tenant.id).filter(and_(
            Tenant.user_id == user.user_id, Tenant.is_deleted == False)).scalar()
        title = f"{data.category} - {space.name}"
        category_id = session.query(TicketCategory.id).filter(
            and_(TicketCategory.category_name == data.category, TicketCategory.site_id == space.site_id)).scalar()

    if not tenant_id:
        return error_response(
            message=f"Invalid tenant",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=400
        )

    if not category_id:
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
        category_id=category_id,
        title=title,
        description=data.description,
        status=TicketStatus.OPEN,
        created_by=user.user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        preferred_time=data.preferred_time,
        request_type=data.request_type
    )
    session.add(new_ticket)
    session.flush()  # needed to get ticket_id

    # Fetch SLA Policy for auto-assignment
    created_by_user = (
        auth_db.query(Users)
        .filter(Users.id == user.user_id)
        .scalar()
    )

    assigned_to_user = None

    sla = session.execute(
        select(SlaPolicy).where(SlaPolicy.service_category == data.category)
    ).scalar_one_or_none()

    assigned_to = sla.default_contact if sla else None

    if assigned_to:
        assigned_to_user = (
            auth_db.query(Users)
            .filter(Users.id == assigned_to)
            .scalar()
        )
        new_ticket.assigned_to = assigned_to

        assignment_log = TicketAssignment(
            ticket_id=new_ticket.id,
            assigned_from=user.user_id,
            assigned_to=assigned_to,
            reason="Auto-assigned via SLA"
        )
        session.add(assignment_log)

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

    # email
    send_ticket_created_email(
        background_tasks, session, new_ticket, created_by_user, assigned_to_user)

    return TicketOut.model_validate(
        {
            **new_ticket.__dict__,
            "category": new_ticket.category.category_name
        }
    )


def escalate_ticket(background_tasks: BackgroundTasks, db: Session, auth_db: Session, data: TicketActionRequest):
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
        or str(ticket.created_by) != str(data.action_by)
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
    notification = Notification(
        user_id=sla.escalation_contact,
        type=NotificationType.alert,
        title="Ticket Escalated",
        message=f"Ticket {ticket.ticket_no} have been escalated & assigned to you",
        posted_date=datetime.utcnow(),
        priority=PriorityType(ticket.priority),
        read=False,
        is_deleted=False
    )

    # Workflow Log
    workflow_log = TicketWorkflow(
        ticket_id=ticket.id,
        action_by=data.action_by,
        old_status=old_status.value if old_status else None,
        new_status=TicketStatus.ESCALATED,
        action_taken=f"Ticket {ticket.ticket_no} escalated & assigned to {assigned_to_user}"
    )

    objects_to_add = [assignment_log, notification, workflow_log]

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
    recipient_ids = [
        data.action_by,
        sla.escalation_contact,
        sla.default_contact
    ]
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


def resolve_ticket(background_tasks: BackgroundTasks, db: Session, auth_db: Session, data: TicketActionRequest):
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
        or str(ticket.assigned_to) != str(data.action_by)
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
    notification = Notification(
        user_id=ticket.tenant_id,
        type=NotificationType.alert,
        title="Ticket Closed",
        message=f"Ticket {ticket.ticket_no} closed by {action_by_user.full_name}",
        posted_date=datetime.utcnow(),
        priority=PriorityType(ticket.priority),
        read=False,
        is_deleted=False
    )

    objects_to_add = [notification, workflow_log]

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
    context = {
        "created_by_name": created_by_user.full_name,
        "closed_by": action_by_user.full_name,
        "ticket_no": ticket.ticket_no,
        "feedback": data.comment if data.comment else 'NA'
    }

    email_list = [created_by_user.email, action_by_user.email]

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


def reopen_ticket(background_tasks: BackgroundTasks, db: Session, auth_db: Session, data: TicketActionRequest):
    ticket = db.execute(select(Ticket).where(
        Ticket.id == data.ticket_id)).scalar_one_or_none()
    if not ticket:
        raise Exception("Ticket not found")
    if not ticket.can_reopen or ticket.created_by != data.action_by:
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
        .scalar()
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
    notification = Notification(
        user_id=ticket.assigned_to,
        type=NotificationType.alert,
        title="Ticket Reopened",
        message=f"Ticket {ticket.ticket_no} reopened by {action_by_user.full_name}",
        posted_date=datetime.utcnow(),
        priority=PriorityType(ticket.priority),
        read=False,
        is_deleted=False
    )

    objects_to_add = [notification, workflow_log]

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
    context = {
        "assigned_to": assigned_to_user.full_name,
        "reopened_by": action_by_user.full_name,
        "ticket_no": ticket.ticket_no
    }

    email_list = [assigned_to_user.email, action_by_user.email]

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


def on_hold_ticket(background_tasks: BackgroundTasks, db: Session, auth_db: Session, data: TicketActionRequest):
    ticket = db.execute(select(Ticket).where(
        Ticket.id == data.ticket_id)).scalar_one_or_none()
    if not ticket:
        raise Exception("Ticket not found")

    print(f"assigned by : {ticket.assigned_to}, action by : {data.action_by}")

    if (
        ticket.status in (TicketStatus.CLOSED, TicketStatus.ON_HOLD)
        or str(ticket.assigned_to) != str(data.action_by)
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
    notification = Notification(
        user_id=ticket.tenant_id,
        type=NotificationType.alert,
        title="Ticket On hold",
        message=f"Ticket {ticket.ticket_no} put on hold by {action_by_user.full_name}",
        posted_date=datetime.utcnow(),
        priority=PriorityType(ticket.priority),
        read=False,
        is_deleted=False
    )

    objects_to_add = [notification, workflow_log]

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
    context = {
        "created_by": created_by_user.full_name,
        "hold_reason": data.comment if data.comment else None,
        "ticket_no": ticket.ticket_no
    }

    email_list = [created_by_user.email, action_by_user.email]

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
        select(SlaPolicy).where(SlaPolicy.sla_id == data.category_id)
    ).scalar_one_or_none()

    assigned_to = sla.default_contact if sla else None

    old_status = ticket.status
    ticket.status = TicketStatus.RETURNED
    ticket.assigned_to = assigned_to
    ticket.updated_at = datetime.utcnow()

    assignment = TicketAssignment(
        ticket_id=data.ticket_id,
        assigned_from=data.action_by,
        assigned_to=assigned_to,
        reason=data.comment or "Ticket Returned"
    )
    db.add(assignment)

    workflow = TicketWorkflow(
        ticket_id=data.ticket_id,
        action_by=data.action_by,
        old_status=old_status.value if old_status else None,
        new_status=TicketStatus.RETURNED,
        action_taken=data.comment or "Ticket Returned to Another User"
    )
    db.add(workflow)

    db.commit()
    db.refresh(ticket)
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
        subject=f"Ticket Escalated - {data["ticket_no"]}",
        context=data,
    )


def send_ticket_reopened_email(background_tasks, db, data, recipients):
    email_helper = EmailHelper()

    background_tasks.add_task(
        email_helper.send_email,
        db=db,
        template_code="ticket_reopened",
        recipients=recipients,
        subject=f"Ticket Reopened - {data["ticket_no"]}",
        context=data,
    )


def send_ticket_onhold_email(background_tasks, db, data, recipients):
    email_helper = EmailHelper()

    background_tasks.add_task(
        email_helper.send_email,
        db=db,
        template_code="ticket_on_hold",
        recipients=recipients,
        subject=f"Ticket On hold - {data["ticket_no"]}",
        context=data,
    )
