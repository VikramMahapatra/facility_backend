from uuid import UUID
from typing import List, Optional
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, or_, case, literal, Numeric

from ...models.crm.contacts import Contact
from ...models.leasing_tenants.commercial_partners import CommercialPartner
from ...models.leasing_tenants.tenants import Tenant 
from ...models.financials.invoices import Invoice, PaymentAR
from ...schemas.financials.invoices_schemas import InvoiceCreate, InvoiceOut, InvoiceUpdate, InvoicesRequest, InvoicesResponse, PaymentOut


# ----------------------------------------------------------------------
# CRUD OPERATIONS
# ----------------------------------------------------------------------

def build_invoices_filters(org_id: UUID, params: InvoicesRequest):
    filters = [Invoice.org_id == org_id]
     
    if params.kind and params.kind.lower() != "all":
        filters.append(Invoice.customer_kind == params.kind)

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
    filters = build_invoices_filters(org_id, params)
    
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
        customer_name = None
        
        # ✅ SAME LOGIC AS SERVICE REQUESTS - Get customer name from Tenant/CommercialPartner
        if invoice.customer_kind and invoice.customer_id:
            if invoice.customer_kind == "resident":
                tenant = db.query(Tenant).filter(Tenant.id == invoice.customer_id).first()
                customer_name = tenant.name if tenant else None
            elif invoice.customer_kind == "merchant":
                partner = db.query(CommercialPartner).filter(CommercialPartner.id == invoice.customer_id).first()
                customer_name = partner.legal_name if partner else None
        
        # ✅ FIX: Convert date objects to strings for Pydantic model
        results.append(InvoiceOut.model_validate({
            **invoice.__dict__,
            "date": invoice.date.isoformat() if invoice.date else None,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None, 
            "customer_name": customer_name  # Populated from same logic as service requests
        }))
        
    return {"invoices": results, "total": total}

def get_payments(db: Session, org_id: str, params: InvoicesRequest):
    total = (
        db.query(func.count(PaymentAR.id))
        .join(Invoice, PaymentAR.invoice_id == Invoice.id)
        .filter(PaymentAR.org_id == org_id)
        .scalar()
    )
    
    base_query  = (
        db.query(PaymentAR, Invoice)
        .join(Invoice, PaymentAR.invoice_id == Invoice.id)
        .filter(PaymentAR.org_id == org_id)
    )
    
    payments = base_query.offset(params.skip).limit(params.limit).all()
    
    results = []
    for payment, invoice in payments:
        customer_name = None
        
        # ✅ SAME LOGIC AS SERVICE REQUESTS - Get customer name from Tenant/CommercialPartner
        if invoice.customer_kind and invoice.customer_id:
            if invoice.customer_kind == "resident":
                tenant = db.query(Tenant).filter(Tenant.id == invoice.customer_id).first()
                customer_name = tenant.name if tenant else None
            elif invoice.customer_kind == "merchant":
                partner = db.query(CommercialPartner).filter(CommercialPartner.id == invoice.customer_id).first()
                customer_name = partner.legal_name if partner else None
        
        # ✅ FIX: Convert date objects to strings for Pydantic model
        results.append(PaymentOut.model_validate({
            **payment.__dict__,
            "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
            "invoice_no": invoice.invoice_no,
            "customer_name": customer_name  # Populated from same logic as service requests
        }))
        
    return {"payments": results, "total": total}


def get_invoice_by_id(db: Session, invoice_id: str):
    return db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.is_deleted == False
    ).first()
 # ✅ Add this).first()


def create_invoice(db: Session, org_id: UUID, request: InvoiceCreate, current_user):
    """
    Creates an invoice using SAME LOGIC AS SERVICE REQUESTS
    """
    
    if not request.customer_kind:
        raise HTTPException(status_code=400, detail="customer_kind is required")
    if not request.customer_id:
        raise HTTPException(status_code=400, detail="customer_id is required")
    
    # ✅ SAME LOGIC AS SERVICE REQUESTS - Fetch customer name from Tenant/CommercialPartner
    if request.customer_kind == "resident":
        tenant = db.query(Tenant).filter(Tenant.id == request.customer_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        customer_name = tenant.name
    elif request.customer_kind == "merchant":
        partner = db.query(CommercialPartner).filter(CommercialPartner.id == request.customer_id).first()
        if not partner:
            raise HTTPException(status_code=404, detail="Commercial partner not found")
        customer_name = partner.legal_name
    else:
        raise HTTPException(status_code=400, detail="Invalid customer kind")

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
        "customer_name": customer_name
    }
    invoice_out = InvoiceOut.model_validate(invoice_dict)
    return invoice_out


def update_invoice(db: Session, invoice_update: InvoiceUpdate, current_user):
    db_invoice = get_invoice_by_id(db, invoice_update.id)
    if not db_invoice:
        return None

    # Apply updates
    for k, v in invoice_update.model_dump(exclude_unset=True).items():
        setattr(db_invoice, k, v)

    db.commit()
    db.refresh(db_invoice)

    # ✅ SAME LOGIC AS SERVICE REQUESTS - Fetch customer name from Tenant/CommercialPartner
    customer_name = None
    if db_invoice.customer_kind and db_invoice.customer_id:
        if db_invoice.customer_kind == "resident":
            tenant = db.query(Tenant).filter(Tenant.id == db_invoice.customer_id).first()
            if tenant:
                customer_name = tenant.name
        elif db_invoice.customer_kind == "merchant":
            partner = db.query(CommercialPartner).filter(CommercialPartner.id == db_invoice.customer_id).first()
            if partner:
                customer_name = partner.legal_name

    # ✅ FIX: Convert date objects to strings for Pydantic model
    invoice_dict = {
        **db_invoice.__dict__,
        "date": db_invoice.date.isoformat() if db_invoice.date else None,
        "due_date": db_invoice.due_date.isoformat() if db_invoice.due_date else None,
    }
    if customer_name:
        invoice_dict["customer_name"] = customer_name
    
    invoice_out = InvoiceOut.model_validate(invoice_dict)
    return invoice_out


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
        return False
    
    # ✅ Soft delete
    db_invoice.is_deleted = True
    db.commit()
    return True