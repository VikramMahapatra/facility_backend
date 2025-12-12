from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, or_, case, Numeric

from shared.core.schemas import Lookup

from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.service_ticket.tickets_work_order import TicketWorkOrder
from ...models.service_ticket.tickets import Ticket  
from ...models.financials.invoices import Invoice, PaymentAR
from ...schemas.financials.invoices_schemas import InvoiceCreate, InvoiceOut, InvoiceUpdate, InvoicesRequest, InvoicesResponse, PaymentOut


# ----------------------------------------------------------------------
# CRUD OPERATIONS
# ----------------------------------------------------------------------

def build_invoices_filters(org_id: UUID, params: InvoicesRequest):
    filters = [
        Invoice.org_id == org_id,
        Invoice.is_deleted == False  # ✅ ADD THIS: Exclude soft-deleted invoices
    ]
     
    if params.module_type and params.module_type.lower() != "all":
        filters.append(Invoice.module_type == params.module_type)

    if params.status and params.status.lower() != "all":
        filters.append(Invoice.status == params.status)

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(
            Invoice.invoice_no.ilike(search_term), 
        ))

    return filters

def get_invoices_query(db: Session, org_id: UUID, params: InvoicesRequest):
    filters = build_invoices_filters(org_id, params)
    return db.query(Invoice).filter(*filters)

def get_invoices_overview(db: Session, org_id: UUID, params: InvoicesRequest):
    filters = build_invoices_filters(org_id, params)  # ✅ This now includes is_deleted == False
    
    # Alias for convenience
    grand_amount = cast(func.jsonb_extract_path_text(Invoice.totals, "grand"), Numeric)
        
    counts = db.query(
        func.count(Invoice.id).label("total_invoices"),
        func.coalesce(func.sum(grand_amount), 0).label("total_amount"),
        func.coalesce(
            func.sum(
                case((Invoice.status == "paid", grand_amount), else_=0)
            ), 0
        ).label("paid_amount"),
        func.coalesce(
            func.sum(
                case((Invoice.status.in_(["issued", "partial"]), grand_amount), else_=0)
            ), 0
        ).label("outstanding_amount"),
    ).filter(*filters).one()

    return {
        "totalInvoices": counts.total_invoices,
        "totalAmount": float(counts.total_amount),
        "paidAmount": float(counts.paid_amount),
        "outstandingAmount": float(counts.outstanding_amount),
    }
    
def get_invoices(db: Session, org_id: UUID, params: InvoicesRequest) -> InvoicesResponse:
    base_query = get_invoices_query(db, org_id, params)
    total = base_query.with_entities(func.count(Invoice.id)).scalar()
    
    invoices = (
        base_query
        .order_by(Invoice.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )   

    results = []
    for invoice in invoices:
        entity_name = None
        
        # ✅ SIMPLE LOGIC: Get customer name from TicketWorkOrder or LeaseCharge
        if invoice.module_type and invoice.entity_id:
            if invoice.module_type == "work order":
                ticket_work_order = db.query(TicketWorkOrder).filter(
                    TicketWorkOrder.id == invoice.entity_id,
                    TicketWorkOrder.is_deleted == False
                ).first()
                # Use work order number
                if ticket_work_order:
                    entity_name = ticket_work_order.wo_no
                
            elif invoice.module_type == "lease charge":
                lease_charge = db.query(LeaseCharge).filter(
                    LeaseCharge.id == invoice.entity_id,
                    LeaseCharge.is_deleted == False
                ).first()
                # Use charge code
                if lease_charge:
                    entity_name = lease_charge.charge_code
                          
        # ✅ FIX: Convert date objects to strings for Pydantic model
        results.append(InvoiceOut.model_validate({
            **invoice.__dict__,
            "date": invoice.date.isoformat() if invoice.date else None,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None, 
            "entity_name": entity_name  # Populated from same logic as service requests
        }))
        
    return {"invoices": results, "total": total}

def get_payments(db: Session, org_id: str, params: InvoicesRequest):
    total = (
        db.query(func.count(PaymentAR.id))
        .join(Invoice, PaymentAR.invoice_id == Invoice.id)
        .filter(
            PaymentAR.org_id == org_id,
            Invoice.is_deleted == False  # ✅ ADD THIS
        )
        .scalar()
    )
    
    base_query  = (
        db.query(PaymentAR, Invoice)
        .join(Invoice, PaymentAR.invoice_id == Invoice.id)
        .filter(
            PaymentAR.org_id == org_id,
            Invoice.is_deleted == False  # ✅ ADD THIS
        )
    )
    
    # ... rest of the function
    
    payments = base_query.offset(params.skip).limit(params.limit).all()
    
    results = []
    for payment, invoice in payments:
        entity_name = None
        
         # ✅ SIMPLE LOGIC: Get customer name from TicketWorkOrder or LeaseCharge
        if invoice.module_type and invoice.entity_id:
            if invoice.module_type == "work order":
                ticket_work_order = db.query(TicketWorkOrder).filter(
                    TicketWorkOrder.id == invoice.entity_id,
                    TicketWorkOrder.is_deleted == False
                ).first()
                # Use work order number
                if ticket_work_order:
                    entity_name = ticket_work_order.wo_no
                
            elif invoice.module_type == "lease charge":
                lease_charge = db.query(LeaseCharge).filter(
                    LeaseCharge.id == invoice.entity_id,
                    LeaseCharge.is_deleted == False
                ).first()
                # Use charge code
                if lease_charge:
                    entity_name = lease_charge.charge_code
        
        # ✅ FIX: Convert date objects to strings for Pydantic model
        results.append(PaymentOut.model_validate({
            **payment.__dict__,
            "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
            "invoice_no": invoice.invoice_no,
            "entity_name": entity_name  # Populated from same logic as service requests
        }))
        
    return {"payments": results, "total": total}

def get_invoice_by_id(db: Session, invoice_id: str):
    return db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.is_deleted == False
    ).first()  # ✅ Returns None if not found, no exception


def create_invoice(db: Session, org_id: UUID, request: InvoiceCreate, current_user):
    """
    Creates an invoice using SAME LOGIC AS SERVICE REQUESTS
    """
    
    if not request.module_type:
        raise HTTPException(status_code=400, detail="module_type is required")
    if not request.entity_id:
        raise HTTPException(status_code=400, detail="entity_id is required")
    
    # ✅ SIMPLE LOGIC: Validate entity exists and get customer name
    entity_name = None
    
    if request.module_type == "work order":
        ticket_work_order = db.query(TicketWorkOrder).filter(
            TicketWorkOrder.id == request.entity_id,
            TicketWorkOrder.is_deleted == False
        ).first()
        if not ticket_work_order:
            raise HTTPException(status_code=404, detail="Work order not found")
        # Use work order number
        entity_name = ticket_work_order.wo_no
        
    elif request.module_type == "lease charge":
        lease_charge = db.query(LeaseCharge).filter(
            LeaseCharge.id == request.entity_id,
            LeaseCharge.is_deleted == False
        ).first()
        if not lease_charge:
            raise HTTPException(status_code=404, detail="Lease charge not found")
        
        # Use charge code
        entity_name = lease_charge.charge_code
        
    else:
        raise HTTPException(status_code=400, detail="Invalid module_type. Must be 'work_order' or 'lease_charge'")
    
    # Create invoice
    invoice_data = request.model_dump(exclude={"org_id"})
    invoice_data.update({
        "org_id": org_id,
    })
    
    db_invoice = Invoice(**invoice_data)
    db.add(db_invoice)
    db.commit()
    db.refresh(db_invoice)

    # ✅ FIX: Convert date objects to strings for Pydantic model
    invoice_dict = {
        **db_invoice.__dict__,
        "date": db_invoice.date.isoformat() if db_invoice.date else None,
        "due_date": db_invoice.due_date.isoformat() if db_invoice.due_date else None,
        "entity_name": entity_name
    }
    invoice_out = InvoiceOut.model_validate(invoice_dict)
    return invoice_out


def update_invoice(db: Session, invoice_update: InvoiceUpdate, current_user):
    db_invoice = get_invoice_by_id(db, invoice_update.id)
    if not db_invoice:
        return None  # ✅ Follow the same pattern as update_tax_code
    
    # Apply updates - exclude 'id' since we're using it for lookup
    update_data = invoice_update.model_dump(exclude_unset=True, exclude={"id"})
    for k, v in update_data.items():
        setattr(db_invoice, k, v)

    db.commit()
    db.refresh(db_invoice)

    # ✅ SIMPLE LOGIC: Fetch customer name from TicketWorkOrder or LeaseCharge
    entity_name = None
    if db_invoice.module_type and db_invoice.entity_id:
        if db_invoice.module_type == "work order":
            ticket_work_order = db.query(TicketWorkOrder).filter(
                TicketWorkOrder.id == db_invoice.entity_id,
                TicketWorkOrder.is_deleted == False
            ).first()
            if ticket_work_order:
                entity_name = ticket_work_order.wo_no
                
        elif db_invoice.module_type == "lease charge":
            lease_charge = db.query(LeaseCharge).filter(
                LeaseCharge.id == db_invoice.entity_id,
                LeaseCharge.is_deleted == False
            ).first()
            if lease_charge:
                entity_name = lease_charge.charge_code


    # ✅ FIX: Convert date objects to strings for Pydantic model
    invoice_dict = {
        **db_invoice.__dict__,
        "date": db_invoice.date.isoformat() if db_invoice.date else None,
        "due_date": db_invoice.due_date.isoformat() if db_invoice.due_date else None,
    }
    if entity_name:
        invoice_dict["entity_name"] = entity_name
    
    invoice_out = InvoiceOut.model_validate(invoice_dict)
    return invoice_out

# ----------------- Soft Delete Invoice -----------------
# ----------------- Soft Delete Invoice -----------------
def delete_invoice_soft(db: Session, invoice_id: str, org_id: UUID) -> bool:
    """
    Soft delete invoice - set is_deleted to True
    Returns: True if deleted, False if not found
    """
    db_invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.org_id == org_id,
        Invoice.is_deleted == False
    ).first()
    
    if not db_invoice:
        return False  # ✅ FIXED: Return False like work_order function
    
    # ✅ Soft delete
    db_invoice.is_deleted = True
    db.commit()
    return True

def get_invoice_entities_lookup(db: Session, org_id: UUID, site_id: UUID, module_type: str):
    """
    Get lookup list of entities for invoice creation
    """
    entities = []
    
    if module_type == "work order":
        # Alternative: Filter through ticket's site_id directly
        from ...models.service_ticket.tickets import Ticket  # Import if needed
        
        work_orders = db.query(TicketWorkOrder).filter(
            TicketWorkOrder.is_deleted == False,
            TicketWorkOrder.ticket_id.in_(
                db.query(Ticket.id).filter(
                    Ticket.site_id == site_id,
                    func.lower(Ticket.status)== "open"
                )
            )
        ).all()
        
        for wo in work_orders:
            entities.append(Lookup(
                id=str(wo.id),
                name=wo.wo_no
            ))
            
    elif module_type == "lease charge":
        # Get LeaseCharges for the site AND org
        lease_charges = db.query(LeaseCharge).filter(
            LeaseCharge.is_deleted == False,
            LeaseCharge.lease.has(site_id=site_id),
            LeaseCharge.lease.has(org_id=org_id)
        ).all()
        
        for lc in lease_charges:
            if lc.charge_code:
                entities.append(Lookup(
                    id=str(lc.id),
                    name=lc.charge_code
                ))
    
    return entities