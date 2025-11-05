from datetime import datetime
import select
from sqlalchemy.orm import Session
from uuid import UUID

from facility_service.app.models.service_ticket.sla_policy import SlaPolicy

from ...models.service_ticket.ticket_assignment import TicketAssignment
from ...models.service_ticket.tickets import Ticket
from ...models.service_ticket.tickets_workflow import TicketWorkflow
from shared.app_status_code import AppStatusCode
from shared.json_response_helper import error_response

from ...schemas.service_ticket.tickets_schemas import TicketCreate, TicketFilterRequest




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
    

    
def create_ticket(session: Session, data):
    # Create Ticket (defaults to OPEN)
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