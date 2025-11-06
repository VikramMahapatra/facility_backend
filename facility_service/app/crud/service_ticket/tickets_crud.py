from datetime import datetime
from sqlalchemy import select
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from uuid import UUID
from sqlalchemy import and_, func
from auth_service.app.models.users import Users
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
from shared.schemas import UserToken

from ...models.service_ticket.ticket_assignment import TicketAssignment
from ...models.service_ticket.tickets import Ticket
from ...models.service_ticket.tickets_workflow import TicketWorkflow
from shared.app_status_code import AppStatusCode
from shared.json_response_helper import error_response

from ...schemas.service_ticket.tickets_schemas import AddCommentRequest, AddFeedbackRequest, AddReactionRequest, TicketActionRequest, TicketCreate, TicketDetailsResponse, TicketFilterRequest, TicketOut


def get_tickets(db: Session, params: TicketFilterRequest, current_user: UserToken):
    """Get all tickets with pagination"""

    if (current_user.account_type == "organization"):
        filters = [Ticket.org_id == current_user.org_id]
    else:
        tenant_id = db.query(Tenant.id).filter(and_(
            Tenant.user_id == current_user.user_id, Tenant.is_deleted == False)).scalar()
        filters = [Ticket.tenant_id == tenant_id]

    if params.space_id:
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


def create_ticket(session: Session, auth_db: Session, data: TicketCreate, user: UserToken):
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

    tenant_id = session.query(Tenant.id).filter(and_(
        Tenant.user_id == user.user_id, Tenant.is_deleted == False)).scalar()

    if not tenant_id:
        return error_response(
            message=f"Invalid tenant",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=400
        )

    category_id = session.query(TicketCategory.id).filter(
        TicketCategory.category_name == data.category).scalar()

    if not category_id:
        return error_response(
            message=f"Invalid category",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=400
        )

    title = f"{data.category} - {space.name}"

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
        preferred_time=data.preferred_time
    )
    session.add(new_ticket)
    session.flush()  # needed to get ticket_id

    # Fetch SLA Policy for auto-assignment
    created_by_name = (
        auth_db.query(Users.full_name)
        .filter(Users.id == user.user_id)
        .scalar()
    )

    sla = session.execute(
        select(SlaPolicy).where(SlaPolicy.service_category == data.category)
    ).scalar_one_or_none()

    assigned_to = sla.default_contact if sla else None

    if assigned_to:
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
            priority=PriorityType.medium,
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
        action_taken=f"Ticket Created by {created_by_name}"
    )
    session.add(workflow_log)

    session.commit()
    session.refresh(new_ticket)
    return new_ticket


def escalate_ticket(db: Session, auth_db: Session, data: TicketActionRequest):
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

    if not ticket.can_escalate:
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

    assigned_to_name = (
        auth_db.query(Users.full_name)
        .filter(Users.id == sla.escalation_contact)
        .scalar()
    )

    if not assigned_to_name:
        return error_response(
            message="User doesnt exist in the system",
            status_code=str(AppStatusCode.USER_USERNAME_IS_NOTREGISTERED),
            http_status=400
        )

    # Assignment Log
    assignment_log = TicketAssignment(
        ticket_id=ticket.id,
        assigned_from=data.action_by,
        assigned_to=sla.escalation_contact,
        reason=data.comment
    )
    db.add(assignment_log)

    # Notification Log
    notification = Notification(
        user_id=sla.escalation_contact,
        type=NotificationType.alert,
        title="Ticket Escalated",
        message=f"Ticket {ticket.ticket_no} have been escalated & assigned to you",
        posted_date=datetime.utcnow(),
        priority=PriorityType.medium,
        read=False,
        is_deleted=False
    )
    db.add(notification)

    # Comment Log
    new_comment = TicketComment(
        ticket_id=ticket.id,
        user_id=data.action_by,
        comment_text=data.comment
    )
    db.add(new_comment)

    # Workflow Log
    workflow_log = TicketWorkflow(
        ticket_id=ticket.id,
        action_by=data.action_by,
        old_status=old_status.value if old_status else None,
        new_status=TicketStatus.ESCALATED,
        action_taken=f"Ticket escalated & assigned to {assigned_to_name}"
    )
    db.add(workflow_log)

    db.commit()
    db.refresh(ticket)

    return ticket


def resolve_ticket(db: Session, auth_db: Session, data: TicketActionRequest):
    ticket = db.execute(select(Ticket).where(
        Ticket.ticket_id == data.ticket_id)).scalar_one_or_none()
    if not ticket:
        raise Exception("Ticket not found")

    old_status = ticket.status
    ticket.status = TicketStatus.CLOSED
    ticket.closed_at = datetime.utcnow()
    ticket.updated_at = datetime.utcnow()

    workflow = TicketWorkflow(
        ticket_id=data.ticket_id,
        action_by=data.action_by,
        old_status=old_status.value if old_status else None,
        new_status=TicketStatus.CLOSED,
        action_taken=data.comment or "Ticket Resolved/Closed"
    )
    db.add(workflow)

    db.commit()
    db.refresh(ticket)
    return ticket


def reopen_ticket(db: Session, auth_db: Session, data: TicketActionRequest):
    ticket = db.execute(select(Ticket).where(
        Ticket.ticket_id == data.ticket_id)).scalar_one_or_none()
    if not ticket:
        raise Exception("Ticket not found")
    if ticket.status != "closed":
        raise Exception("Only closed tickets can be reopened")

    old_status = ticket.status
    ticket.status = TicketStatus.REOPENED
    ticket.updated_at = datetime.utcnow()

    workflow = TicketWorkflow(
        ticket_id=data.ticket_id,
        action_by=data.action_by,
        old_status=old_status.value if old_status else None,
        new_status=TicketStatus.REOPENED,
        action_taken=data.comment or "Ticket Reopened"
    )
    db.add(workflow)

    db.commit()
    db.refresh(ticket)
    return ticket


def return_ticket(db: Session, auth_db: Session, data: TicketActionRequest):
    ticket = db.execute(select(Ticket).where(
        Ticket.ticket_id == data.ticket_id)).scalar_one_or_none()
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
    return ticket


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
