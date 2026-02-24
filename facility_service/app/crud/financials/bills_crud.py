from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import cast, func, or_, Numeric, Integer

from shared.helpers.json_response_helper import error_response, success_response
from shared.helpers.user_helper import get_user_name
from shared.core.schemas import UserToken

from ...models.financials.bills import Bill, BillLine, BillPayment
from ...models.service_ticket.tickets_work_order import TicketWorkOrder
from ...models.service_ticket.tickets import Ticket
from ...models.space_sites.spaces import Space
from ...models.space_sites.sites import Site

from ...schemas.financials.bills_schemas import (
    BillCreate, BillOut, BillUpdate, BillsOverview, 
    BillsRequest, BillsResponse, BillPaymentCreate, BillPaymentOut
)
from shared.models.users import Users

def build_bills_filters(db: Session, auth_db: Session, org_id: UUID, params: BillsRequest):
    filters = [Bill.org_id == org_id]

    # filters 
    if params.status and params.status.lower() != "all":
        filters.append(Bill.status == params.status)

    if params.vendor_id:
        filters.append(Bill.vendor_id == params.vendor_id)

    # Text Search Bar (bill number OR vendor name)
    if params.search:
        search_term = f"%{params.search}%"
        
        # Step 1: Find any matching Vendor UUIDs from the Auth DB
        matching_users = auth_db.query(Users.id).filter(
            Users.full_name.ilike(search_term)
        ).all()
        matching_user_ids = [u.id for u in matching_users]

        # Step 2: Filter Bills by Bill No OR the found Vendor UUIDs
        filters.append(or_(
            Bill.bill_no.ilike(search_term),
            Bill.vendor_id.in_(matching_user_ids) if matching_user_ids else False
        ))

    return filters

def calculate_bill_status(db: Session, bill: Bill) -> str:

    if bill.status == "draft":
        return "draft"

    bill_total = Decimal(str(bill.totals.get("grand", 0))) if bill.totals else Decimal("0")

    total_paid = db.query(func.sum(BillPayment.amount)).filter(
        BillPayment.bill_id == bill.id
    ).scalar() or 0

    total_paid = Decimal(str(total_paid))
    balance = bill_total - total_paid

    # No payment yet, but not a draft
    if total_paid == 0:
        return "approved" 

    # Fully paid
    if balance <= Decimal("0.01"):
        return "paid"

    return "partial"

def get_site_name_from_work_order(db: Session, work_order_id: UUID) -> str | None:
    """Traverses WorkOrder -> Ticket -> Space -> Site to get the Site Name"""
    if not work_order_id:
        return None
        
    wo = db.query(TicketWorkOrder).filter(TicketWorkOrder.id == work_order_id).first()
    if wo and wo.ticket_id:
        ticket = db.query(Ticket).filter(Ticket.id == wo.ticket_id).first()
        if ticket and ticket.space_id:
            space = db.query(Space).filter(Space.id == ticket.space_id).first()
            if space and space.site_id:
                site = db.query(Site).filter(Site.id == space.site_id).first()
                return site.name if site else None
    return None

def get_bills_overview(db: Session, auth_db: Session, org_id: UUID, params: BillsRequest) -> BillsOverview:
    filters = build_bills_filters(db,auth_db, org_id, params)
    
    total = db.query(func.count(Bill.id)).filter(*filters).scalar()

    grand_amount = cast(
        func.jsonb_extract_path_text(Bill.totals, "grand"),
        Numeric
    )

    total_amount = db.query(
        func.coalesce(func.sum(grand_amount), 0)
    ).filter(*filters).scalar()

    paid_amount = (
        db.query(
            func.coalesce(func.sum(cast(BillPayment.amount, Numeric)), 0)
        )
        .join(Bill, BillPayment.bill_id == Bill.id)
        .filter(*filters)
        .scalar()
    )

    return BillsOverview(
        totalBills=total or 0,
        totalAmount=float(total_amount),
        paidAmount=float(paid_amount),
        outstandingAmount=float(total_amount - paid_amount)
    )

def get_bills(db: Session, auth_db: Session, org_id: UUID, params: BillsRequest) -> BillsResponse:
    filters = build_bills_filters(db, auth_db, org_id, params)
    
    base_query = db.query(Bill).filter(*filters)
    total = base_query.with_entities(func.count(Bill.id)).scalar()

    bills = (
        base_query
        .order_by(Bill.created_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    results = []

    for bill in bills:
        # Resolve relationships
        vendor_name = get_user_name(bill.vendor_id) # Using the helper from your shared core
        site_name = get_site_name_from_work_order(db, bill.work_order_id)
        
        # Calculate status & totals
        actual_status = calculate_bill_status(db, bill)
        
        bill_total = float(bill.totals.get("grand", 0)) if bill.totals else 0.0
        paid_amount = db.query(func.sum(BillPayment.amount)).filter(BillPayment.bill_id == bill.id).scalar() or 0.0

        bill_data = BillOut.model_validate({
            **bill.__dict__,
            "vendor_name": vendor_name,
            "site_name": site_name,
            "status": actual_status,
            "total_amount": bill_total,
            "paid_amount": float(paid_amount),
            "lines": [],
            "payments": []
        })
        results.append(bill_data)

    return BillsResponse(
        bills=results,
        total=total
    )

def get_bill_detail(db: Session, auth_db: Session, org_id: UUID, bill_id: UUID) -> BillOut:
    bill = db.query(Bill).filter(
        Bill.id == bill_id,
        Bill.org_id == org_id
    ).first()

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    lines = db.query(BillLine).filter(BillLine.bill_id == bill.id).all()
    payments = db.query(BillPayment).filter(BillPayment.bill_id == bill.id).all()
    
    vendor_name = get_user_name(bill.vendor_id)
    site_name = get_site_name_from_work_order(db, bill.work_order_id)
    actual_status = calculate_bill_status(db, bill)
    
    bill_total = float(bill.totals.get("grand", 0)) if bill.totals else 0.0
    paid_amount = sum(float(p.amount) for p in payments)

    return BillOut.model_validate({
        **bill.__dict__,
        "vendor_name": vendor_name,
        "site_name": site_name,
        "status": actual_status,
        "total_amount": bill_total,
        "paid_amount": paid_amount,
        "lines": lines,
        "payments": payments
    })


def create_bill(db: Session, org_id: UUID, request: BillCreate, current_user: UserToken) -> BillOut:
    if not request.lines or len(request.lines) == 0:
        raise HTTPException(status_code=400, detail="Bill must have at least one line")

    bill_data = request.model_dump(exclude={"lines"})
    bill_data.update({
        "org_id": org_id,
        "status": request.status or "draft"
    })

    try:
        # Generate Bill Number
        if not bill_data.get("bill_no"):
            bill_data["bill_no"] = generate_bill_number(db, org_id)

        db_bill = Bill(**bill_data)
        db.add(db_bill)
        db.flush()

        bill_amount = 0.0

        for line in request.lines:
            db_line = BillLine(
                bill_id=db_bill.id,
                description=line.description,
                amount=line.amount,
                tax_pct=line.tax_pct
            )
            db.add(db_line)
            bill_amount += float(line.amount or 0)

        db_bill.totals = {"grand": bill_amount}
        db.commit()

        return get_bill_detail(db, db, org_id, db_bill.id)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def update_bill(db: Session, request: BillUpdate, current_user: UserToken):
    pass 


def delete_bill(db: Session, bill_id: str, org_id: UUID):
    db_bill = db.query(Bill).filter(Bill.id == bill_id, Bill.org_id == org_id).first()
    if not db_bill:
        return error_response(message="Bill not found")

    # Hard delete lines and payments first to prevent foreign key errors
    db.query(BillLine).filter(BillLine.bill_id == db_bill.id).delete()
    db.query(BillPayment).filter(BillPayment.bill_id == db_bill.id).delete()
    db.delete(db_bill)
    
    db.commit()
    return success_response(message="Bill deleted successfully")


def save_bill_payment(db: Session, payload: BillPaymentCreate, current_user: UserToken):
    try:
        bill = db.query(Bill).filter(Bill.id == payload.bill_id).first()
        if not bill:
            return error_response(message="Invalid bill ID")

        if bill.status == "draft":
            return error_response(message="Cannot add payments to draft bills")

        payment = BillPayment(
            bill_id=bill.id,
            amount=float(payload.amount),
            method=payload.method,
            paid_at=payload.paid_at or datetime.utcnow(),
        )
        db.add(payment)
        db.flush()

        # Recalculate and update bill status
        new_status = calculate_bill_status(db, bill)
        bill.status = new_status

        db.commit()
        return success_response(data={"payment_id": str(payment.id)})

    except Exception as e:
        db.rollback()
        raise e


def generate_bill_number(db: Session, org_id: UUID) -> str:
    last_number = (
        db.query(
            func.max(cast(func.replace(Bill.bill_no, "BILL-", ""), Integer))
        )
        .filter(Bill.org_id == org_id)
        .scalar()
    )

    next_number = (last_number or 0) + 1
    return f"BILL-{next_number:04d}" if next_number <= 9999 else f"BILL-{next_number}"