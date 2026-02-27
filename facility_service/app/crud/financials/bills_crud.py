from sqlalchemy import func
from sqlalchemy.orm import Session
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List
from uuid import UUID
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import cast, func, or_, Numeric, Integer

from facility_service.app.crud.common.attachment_crud import AttachmentService
from facility_service.app.enum.module_enum import ModuleName
from facility_service.app.models.procurement.vendors import Vendor
from facility_service.app.schemas.financials.invoices_schemas import InvoicesRequest, PaymentOut
from shared.helpers.json_response_helper import error_response, success_response
from shared.helpers.user_helper import get_user_name, get_users_bulk
from shared.core.schemas import UserToken

from ...models.financials.bills import Bill, BillLine, BillPayment
from ...models.service_ticket.tickets_work_order import TicketWorkOrder
from ...models.service_ticket.tickets import Ticket
from ...models.space_sites.spaces import Space
from ...models.space_sites.sites import Site

from ...schemas.financials.bills_schemas import (
    BillCreate, BillLineOut, BillOut, BillUpdate, BillsOverview,
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

        # Step 2: Filter Bills by Bill No OR the found Vendor UUIDs
        filters.append(or_(
            Bill.bill_no.ilike(search_term),
            Vendor.name.ilike(search_term)
        ))

    return filters


def calculate_bill_status(db: Session, bill: Bill) -> str:

    if bill.status == "draft":
        return "draft"

    bill_total = Decimal(str(bill.totals.get("grand", 0))
                         ) if bill.totals else Decimal("0")

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

    wo = db.query(TicketWorkOrder).filter(
        TicketWorkOrder.id == work_order_id).first()
    if wo and wo.ticket_id:
        ticket = db.query(Ticket).filter(Ticket.id == wo.ticket_id).first()
        if ticket and ticket.space_id:
            space = db.query(Space).filter(Space.id == ticket.space_id).first()
            if space and space.site_id:
                site = db.query(Site).filter(Site.id == space.site_id).first()
                return site.name if site else None
    return None


def get_bills_overview(db: Session, auth_db: Session, org_id: UUID, params: BillsRequest) -> BillsOverview:

    total = (
        db.query(func.count(Bill.id)).join(
            Vendor, Bill.vendor_id == Vendor.id)
    ).filter(Bill.org_id == org_id, Bill.is_deleted == False).scalar()

    grand_amount = cast(
        func.jsonb_extract_path_text(Bill.totals, "grand"),
        Numeric
    )

    total_amount = db.query(
        func.coalesce(func.sum(grand_amount), 0)
    ).filter(Bill.org_id == org_id, Bill.is_deleted == False).scalar()

    paid_amount = (
        db.query(
            func.coalesce(func.sum(cast(BillPayment.amount, Numeric)), 0)
        )
        .join(Bill, BillPayment.bill_id == Bill.id)
        .filter(Bill.org_id == org_id, Bill.is_deleted == False)
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
        # Using the helper from your shared core
        vendor_name = bill.vendor.name if bill.vendor else None
        space_name = bill.space.name if bill.space else None
        site_name = bill.site.name if bill.site else None

        # Calculate status & totals
        actual_status = calculate_bill_status(db, bill)

        bill_total = float(bill.totals.get("grand", 0)) if bill.totals else 0.0
        paid_amount = db.query(func.sum(BillPayment.amount)).filter(
            BillPayment.bill_id == bill.id).scalar() or 0.0

        bill_data = BillOut.model_validate({
            **bill.__dict__,
            "vendor_name": vendor_name,
            "space_name": space_name,
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

    payments = db.query(BillPayment).filter(
        BillPayment.bill_id == bill.id).all()

    space_name = bill.space.name if bill.space else None
    site_name = bill.site.name if bill.site else None
    vendor_name = bill.vendor.name if bill.vendor else None
    actual_status = calculate_bill_status(db, bill)

    bill_total = float(bill.totals.get("grand", 0)) if bill.totals else 0.0
    paid_amount = sum(float(p.amount) for p in payments)

    bill_lines = []

    for line in bill.lines:
        item_no = None

        # -------- WORK ORDER --------
        wo = db.query(TicketWorkOrder).filter(
            TicketWorkOrder.id == line.item_id,
            TicketWorkOrder.is_deleted == False
        ).first()

        if wo:
            item_no = f"#{wo.wo_no}"

        bill_lines.append(BillLineOut.model_validate({
            **line.__dict__,
            "work_order_no": item_no,
        }))

    # -------------------------------------------------
    # PAYMENTS
    # -------------------------------------------------

    payments_list = [
        {
            "id": p.id,
            "org_id": p.org_id,
            "bill_id": p.bill_id,
            "bill_no": bill.bill_no,
            "method": p.method,
            "ref_no": p.ref_no,
            "amount": Decimal(str(p.amount)),
            "paid_at": p.paid_at.date().isoformat() if p.paid_at else None,
        }
        for p in payments
    ]

    attachments_out = AttachmentService.get_attachments(
        db, ModuleName.bills, bill.id)

    return BillOut.model_validate({
        **bill.__dict__,
        "vendor_name": vendor_name,
        "site_name": site_name,
        "space_name": space_name,
        "status": actual_status,
        "total_amount": bill_total,
        "paid_amount": paid_amount,
        "lines": bill_lines,
        "payments": payments_list,
        "attachments_out": attachments_out
    })


async def create_bill(
    db: Session,
    org_id: UUID,
    request: BillCreate,
    attachments: list[UploadFile] | None,
    current_user: UserToken
) -> BillOut:
    if not request.lines or len(request.lines) == 0:
        raise HTTPException(
            status_code=400, detail="Bill must have at least one line")

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
                item_id=line.item_id,
                description=line.description,
                amount=line.amount,
                tax_pct=line.tax_pct
            )
            db.add(db_line)
            bill_amount += float(line.amount or 0)

        db_bill.totals = {"grand": bill_amount}
        db.commit()

        # Bill Attachments
        await AttachmentService.save_attachments(
            db,
            ModuleName.bills,
            db_bill.id,
            attachments
        )

        return get_bill_detail(db, db, org_id, db_bill.id)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


async def update_bill(
    db: Session,
    org_id: UUID,
    bill_id: UUID,
    request: BillCreate,
    attachments: list[UploadFile] | None,
    removed_attachment_ids: list[UUID] | None,
    current_user: UserToken
) -> BillOut:

    db_bill = (
        db.query(Bill)
        .filter(
            Bill.id == bill_id,
            Bill.org_id == org_id,
            Bill.is_deleted.is_(False)
        )
        .first()
    )

    if not db_bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    if not request.lines or len(request.lines) == 0:
        raise HTTPException(
            status_code=400,
            detail="Bill must have at least one line"
        )

    try:
        # -------------------------------------------------
        # 1️⃣ Update Bill Fields (except immutable fields)
        # -------------------------------------------------
        update_data = request.model_dump(exclude={"lines", "bill_no"})

        for key, value in update_data.items():
            setattr(db_bill, key, value)

        db_bill.updated_at = datetime.utcnow()

        # -------------------------------------------------
        # 2️⃣ Replace Bill Lines (safe approach)
        # -------------------------------------------------
        db.query(BillLine).filter(
            BillLine.bill_id == db_bill.id
        ).delete(synchronize_session=False)

        bill_amount = 0.0

        for line in request.lines:
            db_line = BillLine(
                bill_id=db_bill.id,
                item_id=line.item_id,
                description=line.description,
                amount=line.amount,
                tax_pct=line.tax_pct
            )
            db.add(db_line)
            bill_amount += float(line.amount or 0)

        db_bill.totals = {"grand": bill_amount}

        # -------------------------------------------------
        # 3️⃣ Remove Attachments (explicit delete)
        # -------------------------------------------------
        if removed_attachment_ids:
            AttachmentService.delete_attachments(
                db=db,
                module=ModuleName.bills,
                entity_id=db_bill.id,
                attachment_ids=removed_attachment_ids
            )

        # -------------------------------------------------
        # 4️⃣ Add New Attachments
        # -------------------------------------------------
        await AttachmentService.save_attachments(
            db=db,
            module=ModuleName.bills,
            entity_id=db_bill.id,
            files=attachments
        )

        # -------------------------------------------------
        # 5️⃣ Commit Once
        # -------------------------------------------------
        db.commit()
        db.refresh(db_bill)

        return get_bill_detail(db, db, org_id, db_bill.id)

    except Exception as e:
        db.rollback()
        raise e


def delete_bill(db: Session, bill_id: str, org_id: UUID):
    db_bill = db.query(Bill).filter(
        Bill.id == bill_id, Bill.org_id == org_id).first()
    if not db_bill:
        return error_response(message="Bill not found")

    # Hard delete lines and payments first to prevent foreign key errors
    db.query(BillLine).filter(BillLine.bill_id == db_bill.id).delete()
    db.query(BillPayment).filter(BillPayment.bill_id == db_bill.id).delete()
    db.delete(db_bill)

    db.commit()
    return success_response(message="Bill deleted successfully")


def save_bill_payment(
    db: Session,
    payload: BillPaymentCreate,
    current_user: UserToken
):
    try:
        # ---------------------------
        # 0. Validate bill
        # ---------------------------
        if not payload.bill_id:
            return error_response(message="Bill is required")

        bill: Bill = db.query(Bill).filter(
            Bill.id == payload.bill_id,
            Bill.is_deleted == False
        ).first()

        if not bill:
            return error_response(message="Invalid bill ID")

        # ---------------------------
        # 1. Validate bill status
        # ---------------------------
        if bill.status == "draft":
            return error_response(
                message="Cannot add payments to draft bills"
            )

        if bill.status == "paid":
            return error_response(
                message="Bill is already fully paid"
            )

        # ---------------------------
        # 2. Validate ref_no
        # ---------------------------
        if payload.method != "cash" and not payload.ref_no:
            return error_response(
                message="ref_no is mandatory for non-cash payments"
            )

        # prevent duplicate ref_no per bill
        if payload.ref_no:
            duplicate = db.query(BillPayment).filter(
                BillPayment.bill_id == bill.id,
                BillPayment.ref_no == payload.ref_no,
                BillPayment.is_deleted == False
            ).first()

            if duplicate:
                return error_response(
                    message=f"Duplicate payment ref_no '{payload.ref_no}' for this bill"
                )

        # ---------------------------
        # 3. Prevent Overpayment
        # ---------------------------
        bill_total = float(bill.totals.get("grand") or 0)

        existing_payments = db.query(BillPayment).filter(
            BillPayment.bill_id == bill.id,
            BillPayment.is_deleted == False
        ).all()

        already_paid = sum(float(p.amount) for p in existing_payments)
        incoming_amount = float(payload.amount or 0)

        new_total_paid = already_paid + incoming_amount

        if new_total_paid > bill_total + 0.01:
            remaining = bill_total - already_paid
            return error_response(
                message=f"Payment exceeds bill total. Remaining payable amount is {round(remaining, 2)}"
            )

        # ---------------------------
        # 4. Create payment
        # ---------------------------
        payment = BillPayment(
            bill_id=bill.id,
            org_id=current_user.org_id,
            amount=incoming_amount,
            method=payload.method,
            ref_no=payload.ref_no,
            paid_at=payload.paid_at or datetime.utcnow(),
        )

        db.add(payment)
        db.flush()

        # ---------------------------
        # 5. Recalculate bill status
        # ---------------------------
        new_status = calculate_bill_status(db, bill)
        bill.status = new_status

        # ---------------------------
        # 6. Safety check (race condition guard)
        # ---------------------------
        payments = db.query(BillPayment).filter(
            BillPayment.bill_id == bill.id,
            BillPayment.is_deleted == False
        ).all()

        total_paid = sum(float(p.amount) for p in payments)

        if total_paid > bill_total + 0.01:
            db.rollback()
            return error_response(message="Overpayment detected")

        db.commit()

        return success_response(data={"payment_id": str(payment.id)})

    except Exception as e:
        db.rollback()
        raise e


def workorder_vendor_lookup(db: Session, space_id: UUID):

    vendors = (
        db.query(
            Vendor.id.label("id"),
            Vendor.name.label("name"),

            # ✅ safe JSON extraction
            func.coalesce(
                Vendor.contact["email"].astext,
                ""
            ).label("email"),

            func.coalesce(
                Vendor.contact["phone"].astext,
                ""
            ).label("phone"),
        )
        .join(
            TicketWorkOrder,
            TicketWorkOrder.bill_to_id == Vendor.id
        )
        .join(
            Ticket,
            Ticket.id == TicketWorkOrder.ticket_id
        )
        .filter(
            Ticket.space_id == space_id,
            TicketWorkOrder.bill_to_type == "vendor",
            TicketWorkOrder.status == "completed",
            TicketWorkOrder.is_deleted == False,
            Vendor.is_deleted == False,
            Vendor.status == "active",
        )
        .distinct()
        .order_by(Vendor.name.asc())
        .all()
    )

    return [
        {
            "id": str(v.id),
            "name": v.name,
            "email": v.email,
            "phone": v.phone,
        }
        for v in vendors
    ]


def get_pending_work_orders_for_vendor(
    db: Session,
    space_id: UUID,
    vendor_id: str,
    bill_id: UUID | None = None
) -> List[Dict]:

    work_order_list = []

    # Common subquery
    bill_filter = (
        db.query(BillLine.item_id)
        .join(Bill)
        .filter(
            Bill.vendor_id == vendor_id,
            Bill.status.notin_(["void", "paid"]),
        )
    )

    # Important part for EDIT mode
    if bill_id:
        bill_filter = bill_filter.filter(Bill.id != bill_id)

    work_orders = (
        db.query(TicketWorkOrder)
        .join(Ticket, Ticket.id == TicketWorkOrder.ticket_id)
        .filter(
            TicketWorkOrder.is_deleted == False,
            TicketWorkOrder.bill_to_type == "vendor",
            TicketWorkOrder.bill_to_id == vendor_id,
            Ticket.space_id == space_id,
            ~TicketWorkOrder.id.in_(bill_filter)

        )
        .all()
    )

    for wo in work_orders:
        cust_id = wo.bill_to_id
        work_order_list.append({
            "id": str(wo.id),
            "work_order_no": wo.wo_no,
            "description": wo.description,
            "amount": wo.total_amount
        })

    return work_order_list


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


def get_payments(db: Session, auth_db: Session, org_id: str, params: InvoicesRequest):

    # -----------------------------------------
    # Total Count
    # -----------------------------------------
    total = (
        db.query(func.count(BillPayment.id))
        .join(Bill, BillPayment.bill_id == Bill.id)
        .filter(
            BillPayment.org_id == org_id,
            Bill.is_deleted == False
        )
        .scalar()
    )

    # -----------------------------------------
    # Base Query with eager loading
    # -----------------------------------------
    base_query = (
        db.query(BillPayment)
        .options(
            joinedload(BillPayment.bill)
            .joinedload(Bill.lines),
            joinedload(BillPayment.bill)
            .joinedload(Bill.site)
        )
        .join(Bill, BillPayment.bill_id == Bill.id)
        .join(Vendor, Vendor.id == Bill.vendor_id)
        .filter(
            BillPayment.org_id == org_id,
            Bill.is_deleted == False
        )
    )

    # Text Search Bar (bill number OR vendor name)
    if params.search:
        search_term = f"%{params.search}%"

        # Step 2: Filter Bills by Bill No OR the found Vendor UUIDs
        base_query = base_query.filter(or_(
            Bill.bill_no.ilike(search_term),
            Vendor.name.ilike(search_term)
        ))

    payments = (
        base_query
        .order_by(BillPayment.paid_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    results = []

    for payment in payments:

        bill = payment.bill
        vendor_name = bill.vendor.name if bill.vendor else None
        space_name = bill.space.name if bill.space else None
        site_name = bill.site.name if bill.site else None

        results.append(BillPaymentOut.model_validate({
            **payment.__dict__,
            "paid_at": payment.paid_at.date().isoformat() if payment.paid_at else None,
            "bill_no": bill.bill_no,
            "space_name": space_name,
            "site_name": site_name,
            "customer_name": vendor_name
        }))

    return {
        "payments": results,
        "total": total
    }
