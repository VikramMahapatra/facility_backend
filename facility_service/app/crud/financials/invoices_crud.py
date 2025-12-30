from decimal import Decimal
from typing import Any, Dict
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, or_, case, Numeric

from ...models.parking_access.parking_pass import ParkingPass
from ...models.space_sites.sites import Site
from shared.core.schemas import Lookup

from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.service_ticket.tickets_work_order import TicketWorkOrder
from ...models.service_ticket.tickets import Ticket  
from ...models.financials.invoices import Invoice, PaymentAR
from ...schemas.financials.invoices_schemas import InvoiceCreate, InvoiceOut, InvoiceTotalsRequest, InvoiceTotalsResponse, InvoiceUpdate, InvoicesRequest, InvoicesResponse, PaymentOut


# ----------------------------------------------------------------------
# CRUD OPERATIONS
# ----------------------------------------------------------------------

def build_invoices_filters(org_id: UUID, params: InvoicesRequest):
    filters = [
        Invoice.org_id == org_id,
        Invoice.is_deleted == False  # ✅ ADD THIS: Exclude soft-deleted invoices
    ]
     
    if params.billable_item_type and params.billable_item_type.lower() != "all":
        filters.append(Invoice.billable_item_type == params.billable_item_type)

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
        site_name = invoice.site.name if invoice.site else None  
        billable_item_name = None
        
        if invoice.billable_item_type and invoice.billable_item_id:
            if invoice.billable_item_type == "work order":
                ticket_work_order = db.query(TicketWorkOrder).filter(
                    TicketWorkOrder.id == invoice.billable_item_id,
                    TicketWorkOrder.is_deleted == False
                ).first()
                if ticket_work_order:
                    ticket = db.query(Ticket).filter(
                        Ticket.id == ticket_work_order.ticket_id,
                        Ticket.status == "open"
                    ).first()
                    

                    if ticket and ticket.ticket_no:
                        billable_item_name = f"{ticket_work_order.wo_no} | Ticket {ticket.ticket_no}"
                    else:
                        billable_item_name = ticket_work_order.wo_no
                
            elif invoice.billable_item_type == "lease charge":
                lease_charge = db.query(LeaseCharge).filter(
                    LeaseCharge.id == invoice.billable_item_id,
                    LeaseCharge.is_deleted == False
                ).first()
                if lease_charge:
                    if lease_charge.period_start and lease_charge.period_end:
                        start_str = lease_charge.period_start.strftime("%d")
                        end_str = lease_charge.period_end.strftime("%d %b %Y")
                        month_year = lease_charge.period_start.strftime("%b %Y")
                        billable_item_name = f"{lease_charge.charge_code} | {start_str}–{end_str}"
                    else:
                        billable_item_name = lease_charge.charge_code
                        
            elif invoice.billable_item_type == "parking pass":
                parking_pass = db.query(ParkingPass).filter(
                    ParkingPass.id == invoice.billable_item_id,
                    ParkingPass.is_deleted == False
                ).first()

                if parking_pass:
                    if parking_pass.start_date and parking_pass.end_date:
                        start_str = parking_pass.start_date.strftime("%d %b")
                        end_str = parking_pass.end_date.strftime("%d %b %Y")
                        billable_item_name = (
                            f"Parking Pass | {parking_pass.pass_no} | "
                            f"{start_str}–{end_str}"
                        )
                    else:
                        billable_item_name = f"Parking Pass | {parking_pass.pass_no}"

                       
                          
        # ✅ FIX: Convert date objects to strings for Pydantic model
        invoice_data = InvoiceOut.model_validate({
            **invoice.__dict__,
            "date": invoice.date.isoformat() if invoice.date else None,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None, 
            "billable_item_name": billable_item_name,
            "site_name": site_name 
        })
        results.append(invoice_data)
        
    return InvoicesResponse(
        invoices=results,
        total=total
    )

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
        .join(Site, Site.id == Invoice.site_id, isouter=True)
        .filter(
            PaymentAR.org_id == org_id,
            Invoice.is_deleted == False  # ✅ ADD THIS
        )
    )
    

    
    payments = base_query.offset(params.skip).limit(params.limit).all()
    
    results = []
    for payment, invoice in payments:
        billable_item_name = None
        
        if invoice.billable_item_type and invoice.billable_item_id:
            if invoice.billable_item_type == "work order":
                ticket_work_order = db.query(TicketWorkOrder).filter(
                    TicketWorkOrder.id == invoice.billable_item_id,
                    TicketWorkOrder.is_deleted == False
                ).first()
                if ticket_work_order:
                    ticket = db.query(Ticket).filter(
                        Ticket.id == ticket_work_order.ticket_id,
                        Ticket.status == "open"
                    ).first()
                    

                    if ticket and ticket.ticket_no:
                        billable_item_name = f"{ticket_work_order.wo_no} | Ticket {ticket.ticket_no}"
                    else:
                        billable_item_name = ticket_work_order.wo_no
                
            elif invoice.billable_item_type == "lease charge":
                lease_charge = db.query(LeaseCharge).filter(
                    LeaseCharge.id == invoice.billable_item_id,
                    LeaseCharge.is_deleted == False
                ).first()
                if lease_charge:
                    if lease_charge.period_start and lease_charge.period_end:
                        start_str = lease_charge.period_start.strftime("%d")
                        end_str = lease_charge.period_end.strftime("%d %b %Y")
                        month_year = lease_charge.period_start.strftime("%b %Y")
                        billable_item_name = f"{lease_charge.charge_code} | {start_str}–{end_str}"
                    else:
                        billable_item_name = lease_charge.charge_code
                        
                        
            elif invoice.billable_item_type == "parking pass":
                parking_pass = db.query(ParkingPass).filter(
                    ParkingPass.id == invoice.billable_item_id,
                    ParkingPass.is_deleted == False
                ).first()

                if parking_pass:
                    if parking_pass.start_date and parking_pass.end_date:
                        start_str = parking_pass.start_date.strftime("%d %b")
                        end_str = parking_pass.end_date.strftime("%d %b %Y")
                        billable_item_name = (
                            f"Parking Pass | {parking_pass.pass_no} | "
                            f"{start_str}–{end_str}"
                        )
                    else:
                        billable_item_name = f"Parking Pass | {parking_pass.pass_no}"

        
        # ✅ FIX: Convert date objects to strings for Pydantic model
        results.append(PaymentOut.model_validate({
            **payment.__dict__,
            "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
            "invoice_no": invoice.invoice_no,
            "billable_item_name": billable_item_name,
            "site_name": invoice.site.name if invoice.site else None  
        }))
        
    return {"payments": results, "total": total}

def get_invoice_by_id(db: Session, invoice_id: str):
    return db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.is_deleted == False
    ).first()  

def create_invoice(db: Session, org_id: UUID, request: InvoiceCreate, current_user):
    if not request.billable_item_type:
        raise HTTPException(status_code=400, detail="module_type is required")
    if not request.billable_item_id:
        raise HTTPException(status_code=400, detail="entity_id is required")

    billable_item_name = None
    
    if request.billable_item_type == "work order":
        ticket_work_order = db.query(TicketWorkOrder).filter(
            TicketWorkOrder.id == request.billable_item_id,
            TicketWorkOrder.is_deleted == False
        ).first()
        if not ticket_work_order:
            raise HTTPException(status_code=404, detail="Work order not found")
        
        ticket = db.query(Ticket).filter(
            Ticket.id == ticket_work_order.ticket_id,
            Ticket.status == "open"
        ).first()

        if ticket and ticket.ticket_no:
            billable_item_name = f"{ticket_work_order.wo_no} | Ticket #{ticket.ticket_no}"
        else:
            billable_item_name = ticket_work_order.wo_no
        
    elif request.billable_item_type == "lease charge":
        lease_charge = db.query(LeaseCharge).filter(
            LeaseCharge.id == request.billable_item_id,
            LeaseCharge.is_deleted == False
        ).first()
        if not lease_charge:
            raise HTTPException(status_code=404, detail="Lease charge not found")
        

        if lease_charge.period_start and lease_charge.period_end:
            start_str = lease_charge.period_start.strftime("%d")
            end_str = lease_charge.period_end.strftime("%d %b %Y")
            month_year = lease_charge.period_start.strftime("%b %Y")
            billable_item_name = f"{lease_charge.charge_code} | {start_str}–{end_str}"
        else:
            billable_item_name = lease_charge.charge_code
    
    elif request.billable_item_type == "parking pass":
        parking_pass = db.query(ParkingPass).filter(
            ParkingPass.id == request.billable_item_id,
            ParkingPass.is_deleted == False
        ).first()

        if not parking_pass:
            raise HTTPException(status_code=404, detail="Parking pass not found")

        # Build billable item name
        if parking_pass.start_date and parking_pass.end_date:
            start_str = parking_pass.start_date.strftime("%d %b")
            end_str = parking_pass.end_date.strftime("%d %b %Y")
            billable_item_name = (
                f"Parking Pass | {parking_pass.pass_no} | "
                f"{start_str} - {end_str}"
            )
        else:
            billable_item_name = f"Parking Pass | {parking_pass.pass_no}"

 
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid module_type. Must be 'work order', 'lease charge', or 'parking pass'"
        )

    invoice_data = request.model_dump(exclude={"org_id"})
    invoice_data.update({
        "org_id": org_id,
    })
    
    db_invoice = Invoice(**invoice_data)
    db.add(db_invoice)
    db.commit()
    db.refresh(db_invoice)
    site_name = db_invoice.site.name if db_invoice.site else None

   
    invoice_dict = {
        **db_invoice.__dict__,
        "date": db_invoice.date.isoformat() if db_invoice.date else None,
        "due_date": db_invoice.due_date.isoformat() if db_invoice.due_date else None,
        "billable_item_name": billable_item_name,
        "site_name": site_name
    }
    invoice_out = InvoiceOut.model_validate(invoice_dict)
    return invoice_out


def update_invoice(db: Session, invoice_update: InvoiceUpdate, current_user):
    db_invoice = get_invoice_by_id(db, invoice_update.id)
    if not db_invoice:
        return None  
    

    update_data = invoice_update.model_dump(exclude_unset=True, exclude={"id"})
    for k, v in update_data.items():
        setattr(db_invoice, k, v)

    db.commit()
    db.refresh(db_invoice)
    site_name = db_invoice.site.name if db_invoice.site else None

    billable_item_name = None
    if db_invoice.billable_item_type and db_invoice.billable_item_id:
        if db_invoice.billable_item_type == "work order":
            ticket_work_order = db.query(TicketWorkOrder).filter(
                TicketWorkOrder.id == db_invoice.billable_item_id,
                TicketWorkOrder.is_deleted == False
            ).first()
            if ticket_work_order:
                ticket = db.query(Ticket).filter(
                    Ticket.id == ticket_work_order.ticket_id,
                    Ticket.status == "open"
                ).first()
                
                if ticket and ticket.ticket_no:
                    billable_item_name = f"{ticket_work_order.wo_no} | Ticket {ticket.ticket_no}"
                else:
                    billable_item_name = ticket_work_order.wo_no
                
        elif db_invoice.billable_item_type == "lease charge":
            lease_charge = db.query(LeaseCharge).filter(
                LeaseCharge.id == db_invoice.billable_item_id,
                LeaseCharge.is_deleted == False
            ).first()
            if lease_charge:
                if lease_charge.period_start and lease_charge.period_end:
                    start_str = lease_charge.period_start.strftime("%d")
                    end_str = lease_charge.period_end.strftime("%d %b %Y")
                    month_year = lease_charge.period_start.strftime("%b %Y")
                    billable_item_name = f"{lease_charge.charge_code} | {start_str}–{end_str}"
                else:
                    billable_item_name = lease_charge.charge_code
                    
        elif db_invoice.billable_item_type == "parking pass":
            parking_pass = db.query(ParkingPass).filter(
                ParkingPass.id == db_invoice.billable_item_id,
                ParkingPass.is_deleted == False
            ).first()

            if parking_pass:
                if parking_pass.start_date and parking_pass.end_date:
                    start_str = parking_pass.start_date.strftime("%d %b")
                    end_str = parking_pass.end_date.strftime("%d %b %Y")
                    billable_item_name = (
                        f"Parking Pass | {parking_pass.pass_no} | "
                        f"{start_str}–{end_str}"
                    )
                else:
                    billable_item_name = f"Parking Pass | {parking_pass.pass_no}"



    # ✅ FIX: Convert date objects to strings for Pydantic model
    invoice_dict = {
        **db_invoice.__dict__,
        "date": db_invoice.date.isoformat() if db_invoice.date else None,
        "due_date": db_invoice.due_date.isoformat() if db_invoice.due_date else None,
        "site_name": site_name
        
    }
    if billable_item_name:
        invoice_dict["billable_item_name"] = billable_item_name
    
    invoice_out = InvoiceOut.model_validate(invoice_dict)
    return invoice_out


# ----------------- Soft Delete Invoice -----------------
def delete_invoice_soft(db: Session, invoice_id: str, org_id: UUID) -> bool:
    db_invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.org_id == org_id,
        Invoice.is_deleted == False
    ).first()
    
    if not db_invoice:
        return {
            "success": False,
            "message": "Invoice not found or already deleted"
        }
    
    db_invoice.is_deleted = True
    db.commit()
    db.refresh(db_invoice)
    return {
        "success": True,
        "message": "Invoice soft deleted successfully"
    }

def get_invoice_entities_lookup(db: Session, org_id: UUID, site_id: UUID, billable_item_type: str):
    entities = []
    
    if billable_item_type == "work order":        
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
            ticket = db.query(Ticket).filter(
                Ticket.id == wo.ticket_id,
                Ticket.status == "open"
            ).first()
            
            if ticket and ticket.ticket_no:
                formatted_name = f"{wo.wo_no} | Ticket {ticket.ticket_no}"
            else:
                formatted_name = wo.wo_no
                
            entities.append(Lookup(
                id=str(wo.id),
                name=formatted_name  
            ))
            
    elif billable_item_type == "lease charge":
        lease_charges = db.query(LeaseCharge).filter(
            LeaseCharge.is_deleted == False,
            LeaseCharge.lease.has(site_id=site_id),
            LeaseCharge.lease.has(org_id=org_id)
        ).all()
        
        for lc in lease_charges:
            if lc.charge_code:

                if lc.period_start and lc.period_end:
                    start_str = lc.period_start.strftime("%d")
                    end_str = lc.period_end.strftime("%d %b %Y")
                    formatted_name = f"{lc.charge_code} | {start_str}–{end_str}"
                else:
                    formatted_name = lc.charge_code
                    
                entities.append(Lookup(
                    id=str(lc.id),
                    name=formatted_name  
                ))
                
    elif billable_item_type == "parking pass":
        parking_passes = db.query(ParkingPass).filter(
            ParkingPass.is_deleted == False,
            ParkingPass.site_id == site_id,
            ParkingPass.org_id == org_id
        ).all()

        for pp in parking_passes:
            if pp.start_date and pp.end_date:
                start_str = pp.start_date.strftime("%d %b")
                end_str = pp.end_date.strftime("%d %b %Y")
                formatted_name = (
                    f"Parking Pass | {pp.pass_no} | {start_str}–{end_str}"
                )
            else:
                formatted_name = f"Parking Pass | {pp.pass_no}"

            entities.append(Lookup(
                id=str(pp.id),
                name=formatted_name
            ))

    
    return entities


def get_work_order_invoices(db: Session, org_id: UUID, params: InvoicesRequest) -> InvoicesResponse:
    """Get only work order invoices"""
    # Add filter for work order type
    params.billable_item_type = "work order"
    
    base_query = get_invoices_query(db, org_id, params)
    total = base_query.with_entities(func.count(Invoice.id)).scalar()
    
    invoices = (
        base_query
        .order_by(Invoice.updated_at.desc())
        .join(Site, Site.id == Invoice.site_id)
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )   

    results = []
    for invoice in invoices:
        billable_item_name = None
        site_name = invoice.site.name if invoice.site else None 
        
        if invoice.billable_item_id:
            ticket_work_order = db.query(TicketWorkOrder).filter(
                TicketWorkOrder.id == invoice.billable_item_id,
                TicketWorkOrder.is_deleted == False
            ).first()
            if ticket_work_order:
                ticket = db.query(Ticket).filter(
                    Ticket.id == ticket_work_order.ticket_id,
                    Ticket.status == "open"
                ).first()
                
                if ticket and ticket.ticket_no:
                    billable_item_name = f"{ticket_work_order.wo_no} | Ticket {ticket.ticket_no}"
                else:
                    billable_item_name = ticket_work_order.wo_no
                          
        invoice_data = InvoiceOut.model_validate({
            **invoice.__dict__,
            "date": invoice.date.isoformat() if invoice.date else None,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None, 
            "billable_item_name": billable_item_name,
            "site_name": site_name
        })
        results.append(invoice_data)
        
    return InvoicesResponse(
        invoices=results,
        total=total
    )


def get_lease_charge_invoices(db: Session, org_id: UUID, params: InvoicesRequest) -> InvoicesResponse:
    """Get only lease charge invoices"""
    # Add filter for lease charge type
    params.billable_item_type = "lease charge"
    
    base_query = get_invoices_query(db, org_id, params)
    total = base_query.with_entities(func.count(Invoice.id)).scalar()
    
    invoices = (
        base_query
        .order_by(Invoice.updated_at.desc())
        .join(Site, Site.id == Invoice.site_id)
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )   

    results = []
    for invoice in invoices:
        billable_item_name = None
        site_name = invoice.site.name if invoice.site else None
        
        if invoice.billable_item_id:
            lease_charge = db.query(LeaseCharge).filter(
                LeaseCharge.id == invoice.billable_item_id,
                LeaseCharge.is_deleted == False
            ).first()
            if lease_charge:
                if lease_charge.period_start and lease_charge.period_end:
                    start_str = lease_charge.period_start.strftime("%d")
                    end_str = lease_charge.period_end.strftime("%d %b %Y")
                    billable_item_name = f"{lease_charge.charge_code} | {start_str}–{end_str}"
                else:
                    billable_item_name = lease_charge.charge_code
                          
        invoice_data = InvoiceOut.model_validate({
            **invoice.__dict__,
            "date": invoice.date.isoformat() if invoice.date else None,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None, 
            "billable_item_name": billable_item_name ,
            "site_name": site_name 
        })
        results.append(invoice_data)
        
    return InvoicesResponse(
        invoices=results,
        total=total
    )
    
    


def calculate_invoice_totals(db: Session, params: InvoiceTotalsRequest) -> Dict[str, Any]:
        item_type = params.billable_item_type.lower().strip()
        billable_item_id = params.billable_item_id

        if item_type == "work order":
            # Get work order
            work_order = db.query(TicketWorkOrder).filter(
                TicketWorkOrder.id == billable_item_id,
                TicketWorkOrder.is_deleted == False
            ).first()
            
            if not work_order:
                raise HTTPException(status_code=404, detail="Work order not found")
            
            # Calculate totals
            labour = work_order.labour_cost or Decimal('0')
            material = work_order.material_cost or Decimal('0')
            other = work_order.other_expenses or Decimal('0')
            
            subtotal = labour + material + other
            tax = Decimal('0.00')
            grand_total = subtotal + tax
            
        elif item_type == "lease charge":
            # Get lease charge
            lease_charge = db.query(LeaseCharge).filter(
                LeaseCharge.id == billable_item_id,
                LeaseCharge.is_deleted == False
            ).first()
            
            if not lease_charge:
                raise HTTPException(status_code=404, detail="Lease charge not found")
            
            # Calculate totals
            subtotal = lease_charge.amount
            tax = (lease_charge.amount * (lease_charge.tax_pct or Decimal('0'))) / Decimal('100')
            grand_total = subtotal + tax
                
        else:
            raise HTTPException(
                status_code=400,
               detail="Invalid billable_item_type. Must be 'work order', 'lease charge', or 'parking pass'"
            )
        
        return InvoiceTotalsResponse(
            subtotal=round(subtotal, 2),      
            tax=round(tax, 2),          
            grand_total=round(grand_total, 2)   
        )