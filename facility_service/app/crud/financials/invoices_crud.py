from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict 
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Date, func, cast, or_, case, Numeric

from facility_service.app.models.leasing_tenants.leases import Lease
from facility_service.app.models.system.notifications import Notification, NotificationType, PriorityType 

from ...enum.revenue_enum import  InvoicePayementMethod

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
                        start_str = lease_charge.period_start.strftime("%d %b %Y")
                        end_str = lease_charge.period_end.strftime("%d %b %Y")
                        month_year = lease_charge.period_start.strftime("%b %Y")
                        billable_item_name = f"{lease_charge.charge_code} | {start_str} - {end_str}"
                    else:
                        billable_item_name = lease_charge.charge_code
                        
            elif invoice.billable_item_type == "parking pass":
                parking_pass = db.query(ParkingPass).filter(
                    ParkingPass.id == invoice.billable_item_id,
                    ParkingPass.is_deleted == False
                ).first()

                if parking_pass:
                    if parking_pass.start_date and parking_pass.end_date:
                        start_str = parking_pass.start_date.strftime("%d %b %Y")
                        end_str = parking_pass.end_date.strftime("%d %b %Y")
                        billable_item_name = (
                            f"Parking Pass | {parking_pass.pass_no} | "
                            f"{start_str}–{end_str}"
                        )
                    else:
                        billable_item_name = f"Parking Pass | {parking_pass.pass_no}"
        
        # ✅ ADD THIS: Get payments for the invoice
        payments = db.query(PaymentAR).filter(
            PaymentAR.invoice_id == invoice.id
        ).all()
        
        payments_list = []
        for payment in payments:
            payments_list.append({
                "id": payment.id,
                "org_id": payment.org_id,
                "invoice_id": payment.invoice_id,
                "invoice_no": invoice.invoice_no,
                "billable_item_name": billable_item_name,
                "method": payment.method,
                "ref_no": payment.ref_no,
                "amount": Decimal(str(payment.amount)),
                "paid_at": payment.paid_at.date().isoformat(), 
                "meta": payment.meta
            })
        
        # ✅ CRITICAL: Calculate dynamic status
        invoice_amount = 0.0
        if invoice.totals and "grand" in invoice.totals:
            invoice_amount = float(invoice.totals.get("grand", 0.0))
        
        # Calculate ACTUAL status based on payments
        actual_status = calculate_invoice_status(
            db=db,
            invoice_id=invoice.id,
            invoice_amount=invoice_amount,
            due_date=invoice.due_date
        )
        
        # Also calculate is_paid
        is_paid = (actual_status == "paid")
        
        # ✅ FIX: Convert date objects to strings for Pydantic model
        invoice_data = InvoiceOut.model_validate({
            **invoice.__dict__,
            "date": invoice.date.isoformat() if invoice.date else None,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None, 
            "billable_item_name": billable_item_name,
            "site_name": site_name,
            "status": actual_status,  # ✅ Use CALCULATED status, not stored status
            "payments": payments_list or []
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
                        
                                        # Get customer name from ticket
                    if ticket.tenant:
                        customer_name = f"{ticket.tenant.name}"
                    elif ticket.vendor:
                        customer_name = ticket.vendor.name
                    elif ticket.space and ticket.space.tenant:
                        # Fallback: get from space tenant
                        space_tenant = ticket.space.tenant
                        customer_name = f"{space_tenant.name} {space_tenant.name}"
                
            elif invoice.billable_item_type == "lease charge":
                lease_charge = db.query(LeaseCharge).filter(
                    LeaseCharge.id == invoice.billable_item_id,
                    LeaseCharge.is_deleted == False
                ).first()
                if lease_charge:
                    if lease_charge.period_start and lease_charge.period_end:
                        start_str = lease_charge.period_start.strftime("%d %b %Y")
                        end_str = lease_charge.period_end.strftime("%d %b %Y")
                        month_year = lease_charge.period_start.strftime("%b %Y")
                        billable_item_name = f"{lease_charge.charge_code} | {start_str} - {end_str}"
                    else:
                        billable_item_name = lease_charge.charge_code
                    
                    # Get customer name from lease
                    if lease_charge.lease:
                        lease = lease_charge.lease
                        if lease.tenant:
                            customer_name = f"{lease.tenant.name}"
                        elif lease.partner:
                            customer_name = lease.partner.legal_name
                        
                        
            elif invoice.billable_item_type == "parking pass":
                parking_pass = db.query(ParkingPass).filter(
                    ParkingPass.id == invoice.billable_item_id,
                    ParkingPass.is_deleted == False
                ).first()

                if parking_pass:
                    if parking_pass.start_date and parking_pass.end_date:
                        start_str = parking_pass.start_date.strftime("%d %b %Y")
                        end_str = parking_pass.end_date.strftime("%d %b %Y")
                        billable_item_name = (
                            f"Parking Pass | {parking_pass.pass_no} | "
                            f"{start_str}–{end_str}"
                        )
                    else:
                        billable_item_name = f"Parking Pass | {parking_pass.pass_no}"
                        
                    # Get customer name
                    if parking_pass.pass_holder_name:
                        customer_name = parking_pass.pass_holder_name
                    elif parking_pass.space and parking_pass.space.tenant:
                        # Fallback to space tenant
                        space_tenant = parking_pass.space.tenant
                        customer_name = f"{space_tenant.name} {space_tenant.name}"
                    
        # ✅ FIX: Convert date objects to strings for Pydantic model
        results.append(PaymentOut.model_validate({
            **payment.__dict__,
           "paid_at": payment.paid_at.date().isoformat(), 
            "invoice_no": invoice.invoice_no,
            "billable_item_name": billable_item_name,
            "site_name": invoice.site.name if invoice.site else None,
            "customer_name": customer_name
        }))
        
    return {"payments": results, "total": total}

def get_invoice_by_id(db: Session, invoice_id: UUID):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    return invoice


def calculate_invoice_status(db: Session, invoice_id: UUID, invoice_amount: float, due_date: Date = None):
    """
    Calculate invoice status based on payments and due date
    
    Logic:
    1. If total payments == invoice amount → 'paid'
    2. If total payments < invoice amount and due_date is past → 'overdue'
    3. If total payments < invoice amount and due_date is not past → 'partial'
    4. If no payments → 'issued'
    """
    # Get total payments for this invoice
    total_payments_result = db.query(func.sum(PaymentAR.amount)).filter(
        PaymentAR.invoice_id == invoice_id
    ).scalar()
    
    total_payments = float(total_payments_result) if total_payments_result else 0.0
    
    # Check if there are any payments at all
    has_payments = db.query(PaymentAR).filter(
        PaymentAR.invoice_id == invoice_id
    ).first() is not None
    
    # Apply logic
    if not has_payments:
        return "issued"
    
    # Use Decimal for precise comparison to avoid floating point issues
    invoice_decimal = Decimal(str(invoice_amount))
    payments_decimal = Decimal(str(total_payments))
    
    # Check if fully paid (allow small tolerance for floating point)
    if payments_decimal >= invoice_decimal - Decimal('0.01'):  # Fully paid
        return "paid"
    elif due_date and due_date < date.today():  # Past due and not fully paid
        return "overdue"
    else:  # Has payments but not fully paid and not overdue
        return "partial"
    
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
        
            # ADD THIS LINE: Get lease for notification
        lease = db.query(Lease).filter(Lease.id == lease_charge.lease_id).first()

        if lease_charge.period_start and lease_charge.period_end:
            start_str = lease_charge.period_start.strftime("%d %b %Y")
            end_str = lease_charge.period_end.strftime("%d %b %Y")
            month_year = lease_charge.period_start.strftime("%b %Y")
            billable_item_name = f"{lease_charge.charge_code} | {start_str} - {end_str}"
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
            start_str = parking_pass.start_date.strftime("%d %b %Y")
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
        
        
    payments_data = request.payments if request.payments else []
    
    invoice_data = request.model_dump(exclude={"org_id", "payments"})
    invoice_data.update({
        "org_id": org_id,
        "status": "issued",
        "is_paid": False,
    })
    
    try:
        # Start transaction
        db_invoice = Invoice(**invoice_data)
        db.add(db_invoice)
        db.flush()  # Get ID but don't commit yet
        
        payments_created = []
        if payments_data:
            for idx, payment in enumerate(payments_data):
                ref_no = payment.ref_no or f"PAY-{db_invoice.invoice_no}-{idx+1}"
                
                payment_ar = PaymentAR(
                    org_id=org_id,
                    invoice_id=db_invoice.id,
                    method=payment.method,
                    ref_no=ref_no,
                    amount=float(payment.amount),
                    paid_at=payment.paid_at or datetime.now(),
                    meta=payment.meta or {}
                )
                db.add(payment_ar)
                payments_created.append(payment_ar)
        
        # Calculate invoice amount
        invoice_amount = 0.0
        if invoice_data.get('totals') and "grand" in invoice_data['totals']:
            invoice_amount = float(invoice_data['totals'].get("grand", 0.0))
        
        # Calculate status (payments are in session but not yet committed)
        # Since payments are in session, we can calculate manually
        if payments_created:
            total_payments = sum(float(p.amount) for p in payments_created)
            
            # Use Decimal for comparison
            invoice_decimal = Decimal(str(invoice_amount))
            payments_decimal = Decimal(str(total_payments))
            
            if payments_decimal >= invoice_decimal - Decimal('0.01'):
                actual_status = "paid"
            elif db_invoice.due_date and db_invoice.due_date < date.today():
                actual_status = "overdue"
            else:
                actual_status = "partial"
        else:
            actual_status = "issued"
        
        # Update invoice with correct status
        db_invoice.status = actual_status
        db_invoice.is_paid = (actual_status == "paid")
        
                
        # ADD THIS: Notification for invoice creation (lease charge only)
        if request.billable_item_type == "lease charge" and lease:
            # 1. Notification for invoice creation against admin
            invoice_notification = Notification(
                user_id=current_user.user_id,
                type=NotificationType.alert,
                title="Lease Invoice Created",
                message=f"Invoice {db_invoice.invoice_no} created for {billable_item_name}. Amount: {invoice_amount}",
                posted_date=datetime.utcnow(),
                priority=PriorityType.medium,
                read=False,
                is_deleted=False,
                is_email=False
            )
            db.add(invoice_notification)
            
            # 2. Notification for EACH payment (if any payments)
            if payments_created:
                for payment in payments_created:
                    payment_notification = Notification(
                        user_id=current_user.user_id,
                        type=NotificationType.alert,
                        title="Lease Payment Recorded",
                        message=f"Payment of {payment.amount} recorded for invoice {db_invoice.invoice_no}",
                        posted_date=datetime.utcnow(),
                        priority=PriorityType.medium,
                        read=False,
                        is_deleted=False,
                        is_email=False
                    )
                    db.add(payment_notification)
            
            # 3. Notification for FULL PAYMENT (if invoice is fully paid)
            if actual_status == "paid":
                full_payment_notification = Notification(
                    user_id=current_user.user_id,
                    type=NotificationType.alert,
                    title="Lease Invoice Fully Paid",
                    message=f"Invoice {db_invoice.invoice_no} has been fully paid. Total: {invoice_amount}",
                    posted_date=datetime.utcnow(),
                    priority=PriorityType.medium,
                    read=False,
                    is_deleted=False,
                    is_email=False
                )
                db.add(full_payment_notification)

        # Single commit for everything
        db.commit()
        
        # Refresh objects
        db.refresh(db_invoice)
        for payment in payments_created:
            db.refresh(payment)
        
        # Build response
        site_name = db_invoice.site.name if db_invoice.site else None
        payments_list = []
        for payment in payments_created:
            payments_list.append({
                "id": payment.id,
                "org_id": payment.org_id,
                "invoice_id": payment.invoice_id,
                "invoice_no": db_invoice.invoice_no,
                "billable_item_name": billable_item_name,
                "method": payment.method,
                "ref_no": payment.ref_no,
                "amount": Decimal(str(payment.amount)),
               "paid_at": payment.paid_at.date().isoformat(),  
                "meta": payment.meta
            })
        
        invoice_dict = {
            **db_invoice.__dict__,
            "date": db_invoice.date.isoformat() if db_invoice.date else None,
            "due_date": db_invoice.due_date.isoformat() if db_invoice.due_date else None,
            "billable_item_name": billable_item_name,
            "site_name": site_name,
            "status": actual_status,
            "is_paid": (actual_status == "paid"),
            "payments": payments_list
        }
        invoice_out = InvoiceOut.model_validate(invoice_dict)
        return invoice_out
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create invoice: {str(e)}")


def update_invoice(db: Session, invoice_update: InvoiceUpdate, current_user):
    db_invoice = db.query(Invoice).filter(
        Invoice.id == invoice_update.id,
        Invoice.org_id == current_user.org_id,
        Invoice.is_deleted == False
    ).first()
    
    if not db_invoice:
        return None  
    
        # Validation: Check if we can update totals
    has_existing_payments = db.query(PaymentAR).filter(
        PaymentAR.invoice_id == db_invoice.id
    ).first() is not None
    
    if has_existing_payments:
        if 'totals' in invoice_update.model_dump(exclude_unset=True):
            # Get current and new totals for comparison
            current_total = 0.0
            if db_invoice.totals and "grand" in db_invoice.totals:
                current_total = float(db_invoice.totals.get("grand", 0.0))
            
            new_totals = invoice_update.totals
            new_total = 0.0
            if new_totals and "grand" in new_totals:
                new_total = float(new_totals.get("grand", 0.0))
            
            # Allow increasing totals (customer owes more)
            # But don't allow decreasing totals if payments exist
            if new_total < current_total:
                raise HTTPException(
                    status_code=400, 
                    detail="Cannot decrease invoice total after payments have been made"
                )
    
    update_data = invoice_update.model_dump(exclude_unset=True, exclude={"id", "payments"})
    if 'status' in update_data:
        del update_data['status']
        
    for k, v in update_data.items():
        setattr(db_invoice, k, v)
    
    # NEW CODE: Handle payments with update/create logic
    payments_created = []  # Track newly created payments (without IDs)
    payments_updated = []  # Track updated payments (with IDs)
    
    if invoice_update.payments:
        for payment_data in invoice_update.payments:
            if payment_data.id:
                # Update existing payment
                existing_payment = db.query(PaymentAR).filter(
                    PaymentAR.id == payment_data.id,
                    PaymentAR.invoice_id == db_invoice.id,
                    PaymentAR.org_id == current_user.org_id  # Security check
                ).first()
                
                if existing_payment:
                    # Update fields if provided
                    if payment_data.method:
                        existing_payment.method = payment_data.method
                    if payment_data.ref_no:
                        existing_payment.ref_no = payment_data.ref_no
                    if payment_data.amount:
                        existing_payment.amount = float(payment_data.amount)
                    if payment_data.paid_at:
                        existing_payment.paid_at = payment_data.paid_at
                    if payment_data.meta is not None:
                        existing_payment.meta = payment_data.meta or {}
                    
                    payments_updated.append(existing_payment)
                else:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Payment with ID {payment_data.id} not found"
                    )
            else:
                # Create new payment
                existing_payments_count = db.query(PaymentAR).filter(
                    PaymentAR.invoice_id == db_invoice.id
                ).count()
                
                ref_no = payment_data.ref_no or f"PAY-{db_invoice.invoice_no}-{existing_payments_count + 1}"
                
                payment_ar = PaymentAR(
                    org_id=current_user.org_id,
                    invoice_id=db_invoice.id,
                    method=payment_data.method,
                    ref_no=ref_no,
                    amount=float(payment_data.amount),
                    paid_at=payment_data.paid_at or datetime.now(),
                    meta=payment_data.meta or {}
                )
                db.add(payment_ar)
                payments_created.append(payment_ar)
                
                
    
    # Recalculate invoice amount from updated totals
    invoice_amount = 0.0
    if db_invoice.totals and "grand" in db_invoice.totals:
        invoice_amount = float(db_invoice.totals.get("grand", 0.0))
    
    # Calculate new status (includes any new payments)
    new_status = calculate_invoice_status(
        db=db,
        invoice_id=db_invoice.id,
        invoice_amount=invoice_amount,
        due_date=db_invoice.due_date
    )
    
    db_invoice.status = new_status
    db_invoice.is_paid = (new_status == "paid")
    
    # ADD THIS: Notification logic for invoice update (lease charge only)
    if db_invoice.billable_item_type == "lease charge":
        # 1. Notification for EACH NEW payment added
        if payments_created:
            for payment in payments_created:
                payment_notification = Notification(
                    user_id=current_user.user_id,
                    type=NotificationType.alert,
                    title="Lease Payment Added",
                    message=f"Payment of {payment.amount} added to invoice {db_invoice.invoice_no}",
                    posted_date=datetime.utcnow(),
                    priority=PriorityType.medium,
                    read=False,
                    is_deleted=False,
                    is_email=False
                )
                db.add(payment_notification)
        
        # 2. Notification if invoice becomes FULLY PAID after update
        if new_status == "paid":
            # Check if it was not already paid before
            if db_invoice.status != "paid":  # Only notify if status changed to paid
                full_payment_notification = Notification(
                    user_id=current_user.user_id,
                    type=NotificationType.alert,
                    title="Lease Invoice Fully Paid",
                    message=f"Invoice {db_invoice.invoice_no} has been fully paid",
                    posted_date=datetime.utcnow(),
                    priority=PriorityType.medium,
                    read=False,
                    is_deleted=False,
                    is_email=False
                )
                db.add(full_payment_notification)
 
    db.commit()
    db.refresh(db_invoice)
    
    # Refresh newly created payments
    for payment in payments_created:
        db.refresh(payment)
    
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
                    start_str = lease_charge.period_start.strftime("%d %b %Y")
                    end_str = lease_charge.period_end.strftime("%d %b %Y")
                    month_year = lease_charge.period_start.strftime("%b %Y")
                    billable_item_name = f"{lease_charge.charge_code} | {start_str} - {end_str}"
                else:
                    billable_item_name = lease_charge.charge_code
                    
        elif db_invoice.billable_item_type == "parking pass":
            parking_pass = db.query(ParkingPass).filter(
                ParkingPass.id == db_invoice.billable_item_id,
                ParkingPass.is_deleted == False
            ).first()

            if parking_pass:
                if parking_pass.start_date and parking_pass.end_date:
                    start_str = parking_pass.start_date.strftime("%d %b %Y")
                    end_str = parking_pass.end_date.strftime("%d %b %Y")
                    billable_item_name = (
                        f"Parking Pass | {parking_pass.pass_no} | "
                        f"{start_str}–{end_str}"
                    )
                else:
                    billable_item_name = f"Parking Pass | {parking_pass.pass_no}"

    # Get ALL payments (existing + newly created) for response
    all_payments = db.query(PaymentAR).filter(
        PaymentAR.invoice_id == db_invoice.id
    ).all()
    
    payments_list = []
    for payment in all_payments:
        payments_list.append({
            "id": payment.id,
            "org_id": payment.org_id,
            "invoice_id": payment.invoice_id,
            "invoice_no": db_invoice.invoice_no,
            "billable_item_name": billable_item_name,
            "method": payment.method,
            "ref_no": payment.ref_no,
            "amount": Decimal(str(payment.amount)),
            "paid_at": payment.paid_at.date().isoformat(), 
            "meta": payment.meta
        })

    invoice_dict = {
        **db_invoice.__dict__,
        "date": db_invoice.date.isoformat() if db_invoice.date else None,
        "due_date": db_invoice.due_date.isoformat() if db_invoice.due_date else None,
        "site_name": site_name,
        "status": new_status,  
        "is_paid": (new_status == "paid"), 
        "payments": payments_list
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
             ~TicketWorkOrder.id.in_(
                db.query(Invoice.billable_item_id)
                .filter(
                    Invoice.org_id == org_id,
                    Invoice.billable_item_type == "work order",
                    Invoice.is_deleted == False,
                    Invoice.status != "void"
                )
            ),
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
            ~LeaseCharge.id.in_(
                db.query(Invoice.billable_item_id)
                .filter(
                    Invoice.org_id == org_id,
                    Invoice.billable_item_type == "lease charge",
                    Invoice.is_deleted == False,
                    Invoice.status != "void"
                )
            ),
            LeaseCharge.lease.has(site_id=site_id),
            LeaseCharge.lease.has(org_id=org_id)
        ).all()
        
        for lc in lease_charges:
            if lc.charge_code:

                if lc.period_start and lc.period_end:
                    start_str = lc.period_start.strftime("%d %b %Y")
                    end_str = lc.period_end.strftime("%d %b %Y")
                    formatted_name = f"{lc.charge_code} | {start_str} - {end_str}"
                else:
                    formatted_name = lc.charge_code
                    
                entities.append(Lookup(
                    id=str(lc.id),
                    name=formatted_name  
                ))
                
    elif billable_item_type == "parking pass":
        parking_passes = db.query(ParkingPass).filter(
            ParkingPass.is_deleted == False,
            ~ParkingPass.id.in_(
                db.query(Invoice.billable_item_id)
                .filter(
                    Invoice.org_id == org_id,
                    Invoice.billable_item_type == "parking pass",
                    Invoice.is_deleted == False,
                    Invoice.status != "void"
                )
            ),
            ParkingPass.site_id == site_id,
            ParkingPass.org_id == org_id
        ).all()

        for pp in parking_passes:
            if pp.start_date and pp.end_date:
                start_str = pp.start_date.strftime("%d %b %Y")
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
                          
        # ✅ ADD: Get payments and calculate status
        payments = db.query(PaymentAR).filter(
            PaymentAR.invoice_id == invoice.id
        ).all()
        
        payments_list = []
        for payment in payments:
            payments_list.append({
                "id": payment.id,
                "org_id": payment.org_id,
                "invoice_id": payment.invoice_id,
                "invoice_no": invoice.invoice_no,
                "billable_item_name": billable_item_name,
                "method": payment.method,
                "ref_no": payment.ref_no,
                "amount": Decimal(str(payment.amount)),
                "paid_at": payment.paid_at.date().isoformat() if payment.paid_at else None,
                "meta": payment.meta
            })
        
        # Calculate dynamic status
        invoice_amount = 0.0
        if invoice.totals and "grand" in invoice.totals:
            invoice_amount = float(invoice.totals.get("grand", 0.0))
        
        actual_status = calculate_invoice_status(
            db=db,
            invoice_id=invoice.id,
            invoice_amount=invoice_amount,
            due_date=invoice.due_date
        )
        
        is_paid = (actual_status == "paid")
                          
        invoice_data = InvoiceOut.model_validate({
            **invoice.__dict__,
            "date": invoice.date.isoformat() if invoice.date else None,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None, 
            "billable_item_name": billable_item_name,
            "site_name": site_name,
            "status": actual_status,  # ✅ Use calculated status
            "is_paid": is_paid,  # ✅ Use calculated is_paid
            "payments": payments_list  # ✅ Add payments
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
                    start_str = lease_charge.period_start.strftime("%d %b %Y")
                    end_str = lease_charge.period_end.strftime("%d %b %Y")
                    billable_item_name = f"{lease_charge.charge_code} | {start_str} - {end_str}"
                else:
                    billable_item_name = lease_charge.charge_code
                          
        # ✅ ADD: Get payments and calculate status
        payments = db.query(PaymentAR).filter(
            PaymentAR.invoice_id == invoice.id
        ).all()
        
        payments_list = []
        for payment in payments:
            payments_list.append({
                "id": payment.id,
                "org_id": payment.org_id,
                "invoice_id": payment.invoice_id,
                "invoice_no": invoice.invoice_no,
                "billable_item_name": billable_item_name,
                "method": payment.method,
                "ref_no": payment.ref_no,
                "amount": Decimal(str(payment.amount)),
                "paid_at": payment.paid_at.date().isoformat() if payment.paid_at else None,
                "meta": payment.meta
            })
        
        # Calculate dynamic status
        invoice_amount = 0.0
        if invoice.totals and "grand" in invoice.totals:
            invoice_amount = float(invoice.totals.get("grand", 0.0))
        
        actual_status = calculate_invoice_status(
            db=db,
            invoice_id=invoice.id,
            invoice_amount=invoice_amount,
            due_date=invoice.due_date
        )
        
        is_paid = (actual_status == "paid")
                          
        invoice_data = InvoiceOut.model_validate({
            **invoice.__dict__,
            "date": invoice.date.isoformat() if invoice.date else None,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None, 
            "billable_item_name": billable_item_name,
            "site_name": site_name,
            "status": actual_status,  # ✅ Use calculated status
            "is_paid": is_paid,  # ✅ Use calculated is_paid
            "payments": payments_list  # ✅ Add payments
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
        
        
def invoice_payement_method_lookup(db: Session, org_id: UUID):
    return [
        Lookup(id=method.value, name=method.name.capitalize())
        for method in InvoicePayementMethod
    ]