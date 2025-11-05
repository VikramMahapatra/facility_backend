from datetime import datetime
import select
from fastapi import HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

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

from ...schemas.service_ticket.tickets_schemas import AddCommentRequest, AddFeedbackRequest, AddReactionRequest, TicketActionRequest, TicketCreate, TicketDetailsResponse, TicketFilterRequest


def get_tickets(db: Session, params: TicketFilterRequest):
    """Get all tickets with pagination"""
    try:
        skip = (params.page - 1) * params.limit
        limit = params.limit
        tickets = db.query(Ticket).offset(skip).limit(limit).all()
        return tickets
    except Exception as e:
        return error_response(
            message=f"Error retrieving tickets: {str(e)}",
            status_code=str(AppStatusCode.OPERATION_FAILED),
            http_status=400
        )


def get_ticket_details(db: Session, ticket_id: str):
    """
    Fetch full Tickets details along with all related comments
    """
    # Step 1: Fetch service request
    service_req = (
        db.query(Ticket)
        .filter(Ticket.id == ticket_id)
        .first()
    )

    if not service_req:
        raise HTTPException(
            status_code=404, detail="Service request not found")

    # Step 2: Fetch all comments for that service request (latest first)
    comments = (
        db.query(TicketComment)
        .filter(
            TicketComment.ticket_id == ticket_id,
        )
        .order_by(TicketComment.created_at.desc())  # ✅ latest first
        .all()
    )

    # Step 3: Return as schema
    return TicketDetailsResponse(
        id=service_req.id,
        sr_no=service_req.sr_no,
        category=service_req.category,
        priority=service_req.priority,
        status=service_req.status,
        description=service_req.description,
        created_at=service_req.created_at,
        updated_at=service_req.updated_at,
        requester_kind=service_req.requester_kind,
        requester_id=service_req.requester_id,
        space_id=service_req.space_id,
        site_id=service_req.site_id,
        comments=comments
    )


def create_ticket(session: Session, data: TicketCreate, user: UserToken):
    # Create Ticket (defaults to OPEN)

    # site_id
    # tenant_id
    # title

    new_ticket = Ticket(
        org_id=data.org_id,
        site_id=data.site_id,
        space_id=data.space_id,
        tenant_id=data.tenant_id,
        category_id=data.category_id,
        title=data.title,
        description=data.description,
        status="OPEN",
        created_by=data.created_by,
        created_date=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        prefered_time=data.prefered_time
    )
    session.add(new_ticket)
    session.flush()  # needed to get ticket_id

    # Fetch SLA Policy for auto-assignment
    sla = session.execute(
        select(SlaPolicy).where(SlaPolicy.sla_id == data.category_id)
    ).scalar_one_or_none()

    assigned_to = sla.default_contact if sla else None

    if assigned_to:
        new_ticket.assigned_to = assigned_to

        assignment_log = TicketAssignment(
            ticket_id=new_ticket.ticket_id,
            assigned_from=data.created_by,
            assigned_to=assigned_to,
            reason="Auto-assigned via SLA"
        )
        session.add(assignment_log)

    # Log Workflow History
    workflow_log = TicketWorkflow(
        ticket_id=new_ticket.ticket_id,
        action_by=data.created_by,
        old_status=None,
        new_status="OPEN",
        action_taken="Ticket Created"
    )
    session.add(workflow_log)

    session.commit()
    session.refresh(new_ticket)
    return new_ticket


def escalate_ticket(db: Session, data: TicketActionRequest):
    # Fetch ticket
    ticket = db.execute(
        select(Ticket).where(Ticket.ticket_id == data.ticket_id)
    ).scalar_one_or_none()

    if not ticket:
        raise Exception("Ticket not found")

    # Fetch SLA Policy using category_id
    sla = db.execute(
        select(SlaPolicy).where(SlaPolicy.sla_id == ticket.category_id)
    ).scalar_one_or_none()

    if not sla or not sla.escalation_contact:
        raise Exception("No escalation contact configured for SLA")

    old_status = ticket.status

    # Update ticket
    ticket.status = "ESCALATED"
    ticket.assigned_to = sla.escalation_contact
    ticket.updated_at = datetime.utcnow()

    # Assignment Log
    assignment_log = TicketAssignment(
        ticket_id=ticket.ticket_id,
        assigned_from=data.action_by,
        assigned_to=sla.escalation_contact,
        reason=data.comment
    )
    db.add(assignment_log)

    # Workflow Log
    workflow_log = TicketWorkflow(
        ticket_id=ticket.ticket_id,
        action_by=data.action_by,
        old_status=old_status,
        new_status="ESCALATED",
        action_taken="Manual Escalation Triggered"
    )
    db.add(workflow_log)

    db.commit()
    db.refresh(ticket)

    return ticket


def resolve_ticket(db: Session, data: TicketActionRequest):
    ticket = db.execute(select(Ticket).where(
        Ticket.ticket_id == data.ticket_id)).scalar_one_or_none()
    if not ticket:
        raise Exception("Ticket not found")

    old_status = ticket.status
    ticket.status = "CLOSED"
    ticket.closed_at = datetime.utcnow()
    ticket.updated_at = datetime.utcnow()

    workflow = TicketWorkflow(
        ticket_id=data.ticket_id,
        action_by=data.action_by,
        old_status=old_status,
        new_status="CLOSED",
        action_taken=data.comment or "Ticket Resolved/Closed"
    )
    db.add(workflow)

    db.commit()
    db.refresh(ticket)
    return ticket


def reopen_ticket(db: Session, data: TicketActionRequest):
    ticket = db.execute(select(Ticket).where(
        Ticket.ticket_id == data.ticket_id)).scalar_one_or_none()
    if not ticket:
        raise Exception("Ticket not found")
    if ticket.status != "CLOSED":
        raise Exception("Only closed tickets can be reopened")

    old_status = ticket.status
    ticket.status = "REOPENED"
    ticket.updated_at = datetime.utcnow()

    workflow = TicketWorkflow(
        ticket_id=data.ticket_id,
        action_by=data.action_by,
        old_status=old_status,
        new_status="REOPENED",
        action_taken=data.comment or "Ticket Reopened"
    )
    db.add(workflow)

    db.commit()
    db.refresh(ticket)
    return ticket


def return_ticket(db: Session, data: TicketActionRequest):
    ticket = db.execute(select(Ticket).where(
        Ticket.ticket_id == data.ticket_id)).scalar_one_or_none()
    if not ticket:
        raise Exception("Ticket not found")

    old_status = ticket.status
    ticket.status = "RETURNED"
    ticket.assigned_to = data.return_to
    ticket.updated_at = datetime.utcnow()

    assignment = TicketAssignment(
        ticket_id=data.ticket_id,
        assigned_from=data.action_by,
        assigned_to=data.return_to,
        reason=data.comment or "Ticket Returned"
    )
    db.add(assignment)

    workflow = TicketWorkflow(
        ticket_id=data.ticket_id,
        action_by=data.action_by,
        old_status=old_status,
        new_status="RETURNED",
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

    if ticket.status != "RESOLVED":
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
