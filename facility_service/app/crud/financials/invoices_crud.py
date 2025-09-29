import uuid
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, or_, case, literal, Numeric
from sqlalchemy.dialects.postgresql import UUID

from ...models.crm.contacts import Contact
from ...models.financials.invoices import Invoice, PaymentAR
from ...schemas.financials.invoices_schemas import InvoiceCreate, InvoiceOut, InvoiceUpdate, InvoicesRequest, InvoicesResponse, PaymentOut


# ----------------------------------------------------------------------
# CRUD OPERATIONS
# ----------------------------------------------------------------------

def build_invoices_filters(org_id : UUID, params: InvoicesRequest):
    filters = [Invoice.org_id == org_id]
     
    if params.kind and params.kind.lower() != "all":
        filters.append(Invoice.customer_kind == params.kind)

    if params.status and params.status.lower() != "all":
        filters.append(Invoice.status == params.status)

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(Invoice.invoice_no.ilike(search_term), Contact.full_name.ilike(search_term)))

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
                case([(Invoice.status == "paid", grand_amount)], else_=0)
            ), 0
        ).label("paid_amount"),
        func.coalesce(
            func.sum(
                case([(Invoice.status.in_(["issued", "partial"]), grand_amount)], else_=0)
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
        customer_name = (
            db.query(Contact.full_name)
            .filter(Contact.id == invoice.customer_id)
            .scalar()
        )
        results.append(InvoiceOut.model_validate({
            **invoice.__dict__,
            "date": invoice.date.isoformat() if invoice.date else None,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None, 
            "customer_name": customer_name
            }))
        
    return {"invoices": results, "total": total}

def get_payments(db: Session, org_id: str, params: InvoicesRequest):
    total = (
        db.query(func.count(PaymentAR.id))
        .join(Invoice, PaymentAR.invoice_id == Invoice.id)
        .join(Contact, Invoice.customer_id == Contact.id)
        .filter(PaymentAR.org_id == org_id)
        .scalar()
    )
    
    base_query  = (
        db.query(
            PaymentAR,
            Invoice
            )
        .join(Invoice, PaymentAR.invoice_id == Invoice.id)
        .join(Contact, Invoice.customer_id == Contact.id)
        .filter(PaymentAR.org_id == org_id)
    )
    
    payments = base_query.offset(params.skip).limit(params.limit).all()
    
    results = []
    for payment, invoice in payments:
        customer_name = (
            db.query(Contact.full_name)
            .filter(Contact.id == invoice.customer_id)
            .scalar()
        )
        results.append(PaymentOut.model_validate({
            **payment.__dict__,
            "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
            "invoice_no": invoice.invoice_no,
            "customer_name": customer_name
            }))
        
    return {"payments": results, "total": total}


def get_invoice_by_id(db: Session, invoice_id: str) :
    return db.query(Invoice).filter(Invoice.id == invoice_id).first()


def create_invoice(db: Session, invoice: InvoiceCreate):
    db_invoice = Invoice(**invoice.model_dump(exclude="customer_name"))
    db.add(db_invoice)
    db.commit()
    db.refresh(db_invoice)
    return db_invoice


def update_invoice(db: Session, invoice: InvoiceUpdate) :
    db_invoice = get_invoice_by_id(db, invoice.id)
    if not db_invoice:
        return None
    for k, v in invoice.dict(exclude_unset=True).items():
        setattr(db_invoice, k, v)
    db.commit()
    db.refresh(db_invoice)
    return db_invoice


def delete_invoice(db: Session, invoice_id: str):
    db_invoice = get_invoice_by_id(db, invoice_id)
    if not db_invoice:
        return None
    db.delete(db_invoice)
    db.commit()
    return True

