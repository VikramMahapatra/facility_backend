from collections import defaultdict

from sqlalchemy import Integer, func
from sqlalchemy.orm import joinedload
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import Date, and_, func, cast, literal, or_, case, Numeric, text
from sqlalchemy.dialects.postgresql import JSONB
from facility_service.app.crud.financials.invoice_email_service import InvoiceEmailService
from facility_service.app.crud.service_ticket.tickets_crud import fetch_role_admin
from facility_service.app.models.financials.customer_advances import AdvanceAdjustment, CustomerAdvance
from facility_service.app.models.leasing_tenants.leases import Lease
from facility_service.app.models.leasing_tenants.tenant_spaces import TenantSpace
from facility_service.app.models.leasing_tenants.tenants import Tenant
from facility_service.app.models.space_sites.owner_maintenances import OwnerMaintenanceCharge
from facility_service.app.models.space_sites.space_owners import SpaceOwner
from facility_service.app.models.space_sites.spaces import Space
from facility_service.app.models.system.notifications import Notification, NotificationType, PriorityType
from shared.core.database import AuthSessionLocal
from shared.helpers.json_response_helper import error_response, success_response
from shared.helpers.user_helper import get_user_detail, get_user_name
from shared.models.users import Users
from shared.utils.invoice_pdf import generate_invoice_pdf, get_invoice_email_template

from ...enum.revenue_enum import InvoicePayementMethod, InvoiceType

from ...models.parking_access.parking_pass import ParkingPass
from ...models.space_sites.sites import Site
from shared.core.schemas import Lookup, UserToken

from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.service_ticket.tickets_work_order import TicketWorkOrder
from ...models.service_ticket.tickets import Ticket
from ...models.financials.invoices import Invoice, InvoiceLine, PaymentAR
from ...schemas.financials.invoices_schemas import InvoiceCreate, InvoiceLineOut, InvoiceOut, InvoicePaymentHistoryOut, InvoiceTotalsRequest, InvoiceTotalsResponse, InvoiceUpdate, InvoicesRequest, InvoicesResponse, PaymentCreateWithInvoice, PaymentOut
from facility_service.app.models.parking_access import parking_pass


# ----------------------------------------------------------------------
# CRUD OPERATIONS
# ----------------------------------------------------------------------

def build_invoices_filters(org_id: UUID, params: InvoicesRequest):
    filters = [
        Invoice.org_id == org_id,
        Invoice.is_deleted == False  # ✅ ADD THIS: Exclude soft-deleted invoices
    ]

    if params.billable_item_type and params.billable_item_type.lower() != "all":
        filters.append(InvoiceLine.code == params.billable_item_type)

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
    # ✅ This now includes is_deleted == False
    filters = build_invoices_filters(org_id, params)
    total = db.query(func.count(Invoice.id)).filter(*filters).scalar()

    grand_amount = cast(
        func.jsonb_extract_path_text(Invoice.totals, "grand"),
        Numeric
    )

    total_amount = db.query(
        func.coalesce(func.sum(grand_amount), 0)
    ).filter(*filters).scalar()

    paid_amount = (
        db.query(
            func.coalesce(func.sum(cast(PaymentAR.amount, Numeric)), 0)
        )
        .join(Invoice, PaymentAR.invoice_id == Invoice.id)
        # Ensure we only sum payments for non-deleted invoices
        .filter(*filters, PaymentAR.org_id == org_id, Invoice.is_deleted == False)
        .scalar()
    )

    return {
        "totalInvoices": total,
        "totalAmount": float(total_amount),
        "paidAmount": float(paid_amount),
        "outstandingAmount": float(total_amount - paid_amount),
    }


def get_invoices(db: Session, org_id: UUID, params: InvoicesRequest) -> InvoicesResponse:

    base_query = (
        db.query(Invoice)
        .options(
            joinedload(Invoice.lines),
            joinedload(Invoice.site),
            joinedload(Invoice.payments)
        )
        .filter(
            Invoice.org_id == org_id,
            Invoice.is_deleted == False
        )
    )

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
        space_name = invoice.space.name if invoice.space else None
        site_name = invoice.site.name if invoice.site else None

        building_id = invoice.space.building_block_id if invoice.space and invoice.space.building_block_id else None
        building_name = invoice.space.building.name if invoice.space and invoice.space.building else None,

        code = None
        item_no = None
        user_name = None

        # -----------------------------------------
        # Take first line for summary
        # -----------------------------------------
        if invoice.lines:

            line = invoice.lines[0]
            code = line.code

            # -------- WORK ORDER --------
            if line.code == InvoiceType.work_order.value:
                wo = db.query(TicketWorkOrder).filter(
                    TicketWorkOrder.id == line.item_id,
                    TicketWorkOrder.is_deleted == False
                ).first()

                if wo:
                    item_no = wo.wo_no
                    user_name = get_user_name(wo.bill_to_id)

            # -------- RENT --------
            elif line.code == InvoiceType.rent.value:
                lease = (
                    db.query(Lease)
                    .join(LeaseCharge, LeaseCharge.lease_id == Lease.id)
                    .filter(
                        LeaseCharge.id == line.item_id,
                        Lease.is_deleted == False
                    ).first()
                )

                if lease:
                    item_no = lease.lease_number

                    # assuming lease.tenant_user_id
                    user_name = get_user_name(lease.tenant.user_id)

            # -------- OWNER MAINTENANCE --------
            elif line.code == InvoiceType.owner_maintenance.value:
                om = db.query(OwnerMaintenanceCharge).filter(
                    OwnerMaintenanceCharge.id == line.item_id,
                    OwnerMaintenanceCharge.is_deleted == False
                ).first()

                if om:
                    item_no = om.maintenance_no
                    user_name = get_user_name(om.owner_user_id)

            # -------- PARKING PASS --------
            elif line.code == InvoiceType.parking_pass.value:
                pass_obj = db.query(ParkingPass).filter(
                    ParkingPass.id == line.item_id,
                    ParkingPass.is_deleted == False
                ).first()

                if pass_obj:
                    item_no = pass_obj.pass_no
                    user_name = get_user_name(pass_obj.user_id)

        # -----------------------------------------
        # Payments
        # -----------------------------------------
        payments_list = []

        for payment in invoice.payments:
            payments_list.append({
                "id": payment.id,
                "amount": Decimal(str(payment.amount)),
                "method": payment.method,
                "ref_no": payment.ref_no,
                "paid_at": payment.paid_at.date().isoformat() if payment.paid_at else None
            })

        # -----------------------------------------
        # Status Calculation
        # -----------------------------------------
        invoice_amount = 0.0
        if invoice.totals and "grand" in invoice.totals:
            invoice_amount = float(invoice.totals.get("grand", 0.0))

        actual_status = calculate_invoice_status(
            db=db,
            invoice=invoice
        )

        is_paid = (actual_status == "paid")

        # -----------------------------------------
        # Build Response
        # -----------------------------------------
        invoice_data = InvoiceOut.model_validate({
            **invoice.__dict__,
            "date": invoice.date.isoformat() if invoice.date else None,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "site_name": site_name,
            "space_name": space_name,
            "building_id": building_id,
            "building_name": building_name,
            "status": actual_status,
            "is_paid": is_paid,
            "payments": payments_list or [],
            "code": code,
            "item_no": item_no,
            "user_name": user_name,
            "lines": invoice.lines,
            "created_at": invoice.created_at.isoformat() if isinstance(invoice.created_at, datetime) else invoice.created_at,
            "updated_at": invoice.updated_at.isoformat() if isinstance(invoice.updated_at, datetime) else invoice.updated_at,

        })

        results.append(invoice_data)

    return InvoicesResponse(
        invoices=results,
        total=total
    )


def get_payments(db: Session, auth_db: Session, org_id: str, params: InvoicesRequest):

    # -----------------------------------------
    # Total Count
    # -----------------------------------------
    total = (
        db.query(func.count(PaymentAR.id))
        .join(Invoice, PaymentAR.invoice_id == Invoice.id)
        .filter(
            PaymentAR.org_id == org_id,
            Invoice.is_deleted == False
        )
        .scalar()
    )

    # -----------------------------------------
    # Base Query with eager loading
    # -----------------------------------------
    base_query = (
        db.query(PaymentAR)
        .options(
            joinedload(PaymentAR.invoice)
            .joinedload(Invoice.lines),
            joinedload(PaymentAR.invoice)
            .joinedload(Invoice.site)
        )
        .join(Invoice, PaymentAR.invoice_id == Invoice.id)
        .filter(
            PaymentAR.org_id == org_id,
            Invoice.is_deleted == False
        )
    )

    payments = (
        base_query
        .order_by(PaymentAR.paid_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    results = []

    for payment in payments:

        invoice = payment.invoice
        site_name = invoice.site.name if invoice.site else None

        code = None
        item_no = None
        customer_name = None

        # -----------------------------------------
        # Take first invoice line as summary
        # -----------------------------------------
        if invoice.lines:

            line = invoice.lines[0]
            code = line.code

            # -------- WORKORDER --------
            if line.code == "WORKORDER":
                wo = db.query(TicketWorkOrder).filter(
                    TicketWorkOrder.id == line.item_id,
                    TicketWorkOrder.is_deleted == False
                ).first()

                if wo:
                    item_no = wo.wo_no

                    if wo.bill_to_id:
                        customer_name = get_user_name(wo.bill_to_id)

            # -------- RENT --------
            elif line.code == "RENT":
                lease = (
                    db.query(Lease)
                    .join(LeaseCharge, LeaseCharge.lease_id == Lease.id)
                    .filter(
                        LeaseCharge.id == line.item_id,
                        Lease.is_deleted == False
                    ).first()
                )

                if lease:
                    item_no = lease.lease_number

                    if lease.tenant:
                        customer_name = lease.tenant.name or lease.tenant.legal_name

            # -------- PARKING PASS --------
            elif line.code == "PARKING_PASS":
                parking_pass = db.query(ParkingPass).filter(
                    ParkingPass.id == line.item_id,
                    ParkingPass.is_deleted == False
                ).first()

                if parking_pass:
                    item_no = parking_pass.pass_no
                    if parking_pass.partner_id:
                        customer_name = get_user_name(parking_pass.partner_id)

            # -------- OWNER MAINTENANCE --------
            elif line.code == "OWNER_MAINTENANCE":
                om = db.query(OwnerMaintenanceCharge).filter(
                    OwnerMaintenanceCharge.id == line.item_id,
                    OwnerMaintenanceCharge.is_deleted == False
                ).first()

                if om:
                    item_no = om.maintenance_no

                    if om.space_owner_id:
                        customer_name = get_user_name(om.space_owner_id)

        # -----------------------------------------
        # Build Response
        # -----------------------------------------
        results.append(PaymentOut.model_validate({
            **payment.__dict__,
            "paid_at": payment.paid_at.date().isoformat() if payment.paid_at else None,
            "invoice_no": invoice.invoice_no,
            "code": code,
            "item_no": item_no,
            "site_name": site_name,
            "customer_name": customer_name,
            "line_count": len(invoice.lines)
        }))

    return {
        "payments": results,
        "total": total
    }


def get_invoice_by_id(db: Session, invoice_id: UUID):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    return invoice


def calculate_invoice_status(
    db: Session,
    invoice: Invoice
):
    """
    Status rules:
    draft -> not yet issued
    issued -> no payments yet
    partial -> some payment but not full
    paid -> fully settled
    overdue -> due date passed and still balance
    """

    if invoice.status == "draft":
        return "draft"

    invoice_total = Decimal(str(invoice.totals.get("grand", 0)))

    total_paid = db.query(func.sum(PaymentAR.amount)).filter(
        PaymentAR.invoice_id == invoice.id,
        PaymentAR.is_deleted == False
    ).scalar() or 0

    total_paid = Decimal(str(total_paid))
    balance = invoice_total - total_paid

    # No payment yet
    if total_paid == 0:
        return "issued"

    # Fully paid (advance or payment)
    if balance <= Decimal("0.01"):
        return "paid"

    # Past due
    if invoice.due_date and invoice.due_date < date.today():
        return "overdue"

    return "partial"


def create_invoice(
    db: Session,
    auth_db: Session,
    org_id: UUID,
    request: InvoiceCreate,
    current_user
):
    if not request.lines or len(request.lines) == 0:
        raise HTTPException(
            status_code=400, detail="Invoice must have at least one line")

    invoice_data = request.model_dump(exclude={"org_id", "lines"})
    invoice_data.update({
        "org_id": org_id,
        "status": request.status,
        "is_paid": False,
    })

    try:
        # Generate invoice number
        invoice_data["invoice_no"] = generate_invoice_number(db, org_id)

        db_invoice = Invoice(**invoice_data)
        db.add(db_invoice)
        db.flush()

        invoice_amount = 0

        # ===============================
        # PROCESS INVOICE LINES
        # ===============================
        for line in request.lines:

            # --------------------------------
            # VALIDATE BASE
            # --------------------------------
            if not line.code:
                raise HTTPException(
                    status_code=400, detail="Line code is required")

            # --------------------------------
            # CREATE INVOICE LINE RECORD
            # --------------------------------
            db_line = InvoiceLine(
                invoice_id=db_invoice.id,
                code=line.code,
                item_id=line.item_id,
                description=line.description,
                amount=line.amount,
                tax_pct=line.tax_pct
            )

            db.add(db_line)

            invoice_amount += float(line.amount or 0)

        db_invoice.totals = {
            "grand": invoice_amount
        }

        if request.status == "issued":
            apply_advance_to_invoice(db, db_invoice)

            # ===============================
            # GENERIC INVOICE NOTIFICATION
            # ===============================
            notification = Notification(
                user_id=current_user.user_id,
                type=NotificationType.alert,
                title="Invoice Created",
                message=f"Invoice {db_invoice.invoice_no} created. Amount: {invoice_amount}",
                posted_date=datetime.utcnow(),
                priority=PriorityType.medium,
                read=False,
                is_deleted=False,
                is_email=False
            )
            db.add(notification)

            # send email
            # service = InvoiceEmailService()
            # service.send_invoice_to_customer(
            #     db=db,
            #     invoice=db_invoice,
            #     customer_email=db_invoice.customer_email
            # )

        db.commit()

        # ===============================
        # RESPONSE BUILD
        # ===============================
        site_name = db_invoice.site.name if db_invoice.site else None

        invoice_dict = {
            **db_invoice.__dict__,
            "date": db_invoice.date.isoformat() if db_invoice.date else None,
            "due_date": db_invoice.due_date.isoformat() if db_invoice.due_date else None,
            "site_name": site_name,
            "status": db_invoice.status,
            "is_paid": (db_invoice.status == "paid"),
        }

        return InvoiceOut.model_validate(invoice_dict)

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def update_invoice(db: Session, invoice_update: InvoiceUpdate, current_user):
    db_invoice = db.query(Invoice).filter(
        Invoice.id == invoice_update.id,
        Invoice.org_id == current_user.org_id,
        Invoice.is_deleted == False
    ).first()

    if not db_invoice:
        return error_response(message="Invoice not found")

    old_invoice_status = db_invoice.status

    # Check if payments exist
    has_existing_payments = db.query(PaymentAR).filter(
        PaymentAR.invoice_id == db_invoice.id
    ).first() is not None

    update_data = invoice_update.model_dump(exclude_unset=True)

    # Prevent modifying totals/lines if payment exists
    if has_existing_payments and ("lines" in update_data or "totals" in update_data):
        return error_response(
            message="Cannot modify invoice lines or totals after payments exist"
        )

    # -------------------------
    # UPDATE BASIC FIELDS
    # -------------------------
    allowed_fields = {"site_id", "date", "due_date", "currency", "meta"}
    for field in allowed_fields:
        if field in update_data:
            setattr(db_invoice, field, update_data[field])

    billable_item_names = []
    invoice_amount = 0

    # -------------------------
    # UPDATE LINES
    # -------------------------
    if "lines" in update_data:

        # Delete old lines
        db.query(InvoiceLine).filter(
            InvoiceLine.invoice_id == db_invoice.id
        ).delete()

        for line in update_data["lines"]:
            code = line["code"]
            item_id = line["item_id"]
            db_line = InvoiceLine(
                invoice_id=db_invoice.id,
                code=code,
                item_id=item_id,
                description=line.get("description"),
                amount=line["amount"],
                tax_pct=line.get("tax_pct", 0)
            )

            db.add(db_line)

            invoice_amount += float(line["amount"])

    else:
        # If lines not updated, use existing
        existing_lines = db.query(InvoiceLine).filter(
            InvoiceLine.invoice_id == db_invoice.id
        ).all()

        for line in existing_lines:
            invoice_amount += float(line.amount or 0)

    # -------------------------
    # UPDATE TOTALS
    # -------------------------
    db_invoice.totals = {
        "grand": invoice_amount
    }

    if invoice_update.status == "issued" and old_invoice_status == "draft":
        apply_advance_to_invoice(db, db_invoice)

        # send email
        service = InvoiceEmailService()
        service.send_invoice_to_customer(
            db=db,
            invoice=db_invoice,
            customer_email=db_invoice.customer_email
        )

    # -------------------------
    # STATUS RECALCULATION
    # -------------------------
    new_status = calculate_invoice_status(
        db=db,
        db_invoice=db_invoice
    )

    db_invoice.status = new_status
    db_invoice.is_paid = (new_status == "paid")

    db.commit()
    db.refresh(db_invoice)

    # -------------------------
    # RESPONSE
    # -------------------------
    site_name = db_invoice.site.name if db_invoice.site else None

    invoice_dict = {
        **db_invoice.__dict__,
        "date": db_invoice.date.isoformat() if db_invoice.date else None,
        "due_date": db_invoice.due_date.isoformat() if db_invoice.due_date else None,
        "site_name": site_name,
        "status": new_status,
        "is_paid": (new_status == "paid"),
    }

    return InvoiceOut.model_validate(invoice_dict)


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


def get_pending_charges_by_customer(
    db: Session,
    space_id: UUID,
    code: str,
    invoice_id: UUID | None = None
) -> List[Dict]:

    customers = defaultdict(
        lambda: {"customer_id": None, "customer_name": None, "charges": []}
    )

    # Common subquery
    invoice_filter = (
        db.query(InvoiceLine.item_id)
        .join(Invoice)
        .filter(
            Invoice.space_id == space_id,
            InvoiceLine.code == code,
            Invoice.status.notin_(["void", "paid"]),
            Invoice.is_deleted == False,
        )
    )

    # Important part for EDIT mode
    if invoice_id:
        invoice_filter = invoice_filter.filter(Invoice.id != invoice_id)

    # ---------------------------
    # RENT
    # ---------------------------
    if code == "rent":
        lease_charges = (
            db.query(LeaseCharge)
            .join(Lease, LeaseCharge.lease_id == Lease.id)
            .filter(
                LeaseCharge.is_deleted == False,
                Lease.space_id == space_id,
                ~LeaseCharge.id.in_(invoice_filter)
            )
            .all()
        )

        for lc in lease_charges:
            tenant = db.query(Tenant).filter(Tenant.id == lc.payer_id).first()
            tenant_user = get_user_detail(tenant.user_id)

            customers[tenant.user_id]["customer_id"] = tenant_user.id
            customers[tenant.user_id]["customer_name"] = tenant_user.full_name
            customers[tenant.user_id]["customer_email"] = tenant_user.email
            customers[tenant.user_id]["customer_phone"] = tenant_user.phone
            customers[tenant.user_id]["charges"].append({
                "type": "rent",
                "id": str(lc.id),
                "period": f"{lc.period_start:%d %b %Y} - {lc.period_end:%d %b %Y}"
            })

    # ---------------------------
    # MAINTENANCE
    # ---------------------------
    elif code == "maintenance":
        maint_charges = (
            db.query(OwnerMaintenanceCharge)
            .filter(
                OwnerMaintenanceCharge.is_deleted == False,
                OwnerMaintenanceCharge.space_id == space_id,
                ~OwnerMaintenanceCharge.id.in_(invoice_filter)
            )
            .all()
        )

        for om in maint_charges:
            cust_id = om.space_owner.owner_user_id if om.space_owner else None
            owner_user = get_user_detail(cust_id)

            customers[cust_id]["customer_id"] = owner_user.id
            customers[cust_id]["customer_name"] = owner_user.full_name
            customers[cust_id]["customer_email"] = owner_user.email
            customers[cust_id]["customer_phone"] = owner_user.phone
            customers[cust_id]["charges"].append({
                "type": "maintenance",
                "id": str(om.id),
                "period": f"{om.period_start:%d %b %Y} - {om.period_end:%d %b %Y}"
            })

    # ---------------------------
    # PARKING PASS
    # ---------------------------
    elif code == "parking pass":
        passes = (
            db.query(ParkingPass)
            .filter(
                ParkingPass.is_deleted == False,
                ParkingPass.space_id == space_id,
                ~ParkingPass.id.in_(invoice_filter)
            )
            .all()
        )

        for pp in passes:
            cust_id = pp.partner_id
            owner_user = get_user_detail(cust_id)

            customers[cust_id]["customer_id"] = owner_user.id
            customers[cust_id]["customer_name"] = owner_user.full_name
            customers[cust_id]["customer_email"] = owner_user.email
            customers[cust_id]["customer_phone"] = owner_user.phone
            customers[cust_id]["charges"].append({
                "type": "parking pass",
                "id": str(pp.id),
                "period": f"{pp.valid_from:%d %b %Y} - {pp.valid_to:%d %b %Y}",
                "pass_no": pp.pass_no
            })

    # ---------------------------
    # WORK ORDER
    # ---------------------------
    elif code == "work_order":
        work_orders = (
            db.query(TicketWorkOrder)
            .join(Ticket, Ticket.id == TicketWorkOrder.ticket_id)
            .filter(
                TicketWorkOrder.is_deleted == False,
                TicketWorkOrder.bill_to_type.in_(["tenant", "owner"]),
                Ticket.space_id == space_id,
                ~TicketWorkOrder.id.in_(invoice_filter)

            )
            .all()
        )

        for wo in work_orders:
            cust_id = wo.bill_to_id
            owner_user = get_user_detail(cust_id)

            customers[cust_id]["customer_id"] = owner_user.id
            customers[cust_id]["customer_name"] = owner_user.full_name
            customers[cust_id]["customer_email"] = owner_user.email
            customers[cust_id]["customer_phone"] = owner_user.phone
            customers[cust_id]["charges"].append({
                "type": "work_order",
                "id": str(wo.id),
                "work_order_no": wo.wo_no
            })

    return list(customers.values())


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
            invoice=invoice
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
                charge_code = lease_charge.charge_code.code
                if lease_charge.period_start and lease_charge.period_end:
                    start_str = lease_charge.period_start.strftime("%d %b %Y")
                    end_str = lease_charge.period_end.strftime("%d %b %Y")
                    billable_item_name = f"{charge_code} | {start_str} - {end_str}"
                else:
                    billable_item_name = charge_code

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
            invoice=invoice
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
    item_id = params.billable_item_id

    if item_type == InvoiceType.work_order.value:
        # Get work order
        work_order = db.query(TicketWorkOrder).filter(
            TicketWorkOrder.id == item_id,
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

    elif item_type == InvoiceType.rent.value:
        # Get lease
        lease = (
            db.query(Lease)
            .join(LeaseCharge, Lease.id == LeaseCharge.lease_id)
            .filter(
                LeaseCharge.id == item_id,
                Lease.is_deleted == False
            ).first()
        )

        if not lease:
            raise HTTPException(status_code=404, detail="Lease not found")

        # Calculate totals using rent_amount
        subtotal = lease.rent_amount
        tax = Decimal('0')
        grand_total = subtotal

    elif item_type == InvoiceType.owner_maintenance.value:
        maintenance = db.query(OwnerMaintenanceCharge).filter(
            OwnerMaintenanceCharge.id == item_id,
            OwnerMaintenanceCharge.is_deleted == False
        ).first()

        if not maintenance:
            raise HTTPException(
                status_code=404,
                detail="Owner maintenance charge not found"
            )

        # ✅ USE STORED AMOUNT (CAM already calculated)
        subtotal = maintenance.amount or Decimal("0")

        tax = Decimal("0.00")  # GST can be added later
        grand_total = subtotal + tax
    elif item_type == InvoiceType.parking_pass.value:
        parking_pass = db.query(ParkingPass).filter(
            ParkingPass.id == item_id,
            ParkingPass.is_deleted == False
        ).first()

        if not parking_pass:
            raise HTTPException(
                status_code=404,
                detail="Parking pass not found"
            )

        # ✅ USE STORED AMOUNT (CAM already calculated)
        subtotal = parking_pass.charge_amount or Decimal("0")

        tax = Decimal("0.00")  # GST can be added later
        grand_total = subtotal + tax

    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid billable_item_type. Must be 'work order', 'lease charge', or 'parking pass', 'owner maintenance'."
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


def get_invoice_detail(
    db: Session,
    auth_db: Session,
    org_id: UUID,
    invoice_id: UUID
) -> InvoiceOut:

    invoice = (
        db.query(Invoice)
        .options(
            joinedload(Invoice.site),
            joinedload(Invoice.lines)
        )
        .filter(
            Invoice.id == invoice_id,
            Invoice.org_id == org_id,
            Invoice.is_deleted == False
        )
        .first()
    )

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    space_name = invoice.space.name if invoice.space else None
    site_name = invoice.site.name if invoice.site else None

    code = None
    user_name = get_user_name(invoice.user_id)

    invoice_lines = []

    # -------------------------------------------------
    # GET FROM FIRST LINE (same logic as list API)
    # -------------------------------------------------
    for line in invoice.lines:
        item_no = None
        item_label = None
        code = line.code

        # -------- WORK ORDER --------
        if line.code == InvoiceType.work_order.value:
            wo = db.query(TicketWorkOrder).filter(
                TicketWorkOrder.id == line.item_id,
                TicketWorkOrder.is_deleted == False
            ).first()

            if wo:
                item_no = wo.wo_no
                item_label = f"#{wo.wo_no}"

        # -------- RENT --------
        elif line.code == InvoiceType.rent.value:
            lc = (
                db.query(LeaseCharge)
                .join(Lease, Lease.id == LeaseCharge.lease_id)
                .filter(
                    LeaseCharge.id == line.item_id,
                    Lease.is_deleted == False
                ).first()
            )

            if lc:
                item_no = lc.lease.lease_number
                item_label = f"{lc.period_start:%d %b %Y} - {lc.period_end:%d %b %Y}"

        # -------- OWNER MAINTENANCE --------
        elif line.code == InvoiceType.owner_maintenance.value:
            om = db.query(OwnerMaintenanceCharge).filter(
                OwnerMaintenanceCharge.id == line.item_id,
                OwnerMaintenanceCharge.is_deleted == False
            ).first()

            if om:
                item_no = om.maintenance_no
                item_label = f"{om.period_start:%d %b %Y} - {om.period_end:%d %b %Y}"

        # -------- PARKING PASS --------
        elif line.code == InvoiceType.parking_pass.value:
            pass_obj = db.query(ParkingPass).filter(
                ParkingPass.id == line.item_id,
                ParkingPass.is_deleted == False
            ).first()

            if pass_obj:
                item_no = pass_obj.pass_no
                item_label = f"{pass_obj.valid_from:%d %b %Y} - {pass_obj.valid_to:%d %b %Y}"

        invoice_lines.append(InvoiceLineOut.model_validate({
            **line.__dict__,
            "item_no": item_no,
            "item_label": item_label,
        }))

    # -------------------------------------------------
    # PAYMENTS
    # -------------------------------------------------
    payments = db.query(PaymentAR).filter(
        PaymentAR.invoice_id == invoice.id
    ).all()

    payments_list = [
        {
            "id": p.id,
            "org_id": p.org_id,
            "invoice_id": p.invoice_id,
            "invoice_no": invoice.invoice_no,
            "method": p.method,
            "ref_no": p.ref_no,
            "amount": Decimal(str(p.amount)),
            "paid_at": p.paid_at.date().isoformat() if p.paid_at else None,
            "meta": p.meta
        }
        for p in payments
    ]

    # -------------------------------------------------
    # STATUS
    # -------------------------------------------------
    invoice_amount = float(invoice.totals.get(
        "grand", 0)) if invoice.totals else 0

    actual_status = calculate_invoice_status(
        db=db,
        invoice=invoice
    )

    # -------------------------------------------------
    # RESPONSE
    # -------------------------------------------------
    return InvoiceOut.model_validate({
        **invoice.__dict__,
        "date": invoice.date.isoformat() if invoice.date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "space_name": space_name,
        "site_name": site_name,
        "code": code,
        "user_name": user_name,
        "status": actual_status,
        "is_paid": actual_status == "paid",
        "payments": payments_list,
        "currency": invoice.currency,
        "lines": invoice_lines
    })


def get_invoice_payment_history(
    db: Session,
    auth_db: Session,
    org_id: UUID,
    invoice_id: UUID
) -> InvoicePaymentHistoryOut:

    # -------------------------------------------------
    # FETCH INVOICE (WITH LINES)
    # -------------------------------------------------
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.lines))
        .filter(
            Invoice.id == invoice_id,
            Invoice.org_id == org_id,
            Invoice.is_deleted == False
        )
        .first()
    )

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # -------------------------------------------------
    # CALCULATE TOTALS
    # -------------------------------------------------
    totals = calculate_invoice_totals(
        db,
        InvoiceTotalsRequest(
            billable_item_type=invoice.billable_item_type,
            billable_item_id=invoice.billable_item_id
        )
    )

    # -------------------------------------------------
    # DERIVE CODE + ITEM_NO + USER_NAME (NEW LOGIC)
    # -------------------------------------------------
    code = None
    item_no = None
    user_name = None

    if invoice.lines:
        line = invoice.lines[0]
        code = line.code

        # -------- WORK ORDER --------
        if line.code == InvoiceType.work_order.value:
            wo = db.query(TicketWorkOrder).filter(
                TicketWorkOrder.id == line.item_id,
                TicketWorkOrder.is_deleted == False
            ).first()

            if wo:
                item_no = wo.wo_no

                if wo.requested_by:
                    user = (
                        auth_db.query(Users)
                        .filter(
                            Users.id == wo.requested_by,
                            Users.is_deleted == False
                        )
                        .first()
                    )
                    user_name = user.full_name if user else None

        # -------- RENT --------
        elif line.code == InvoiceType.rent.value:
            lease = db.query(Lease).filter(
                Lease.id == line.item_id,
                Lease.is_deleted == False
            ).first()

            if lease:
                item_no = lease.lease_number

                if lease.tenant_user_id:
                    user = (
                        auth_db.query(Users)
                        .filter(
                            Users.id == lease.tenant_user_id,
                            Users.is_deleted == False
                        )
                        .first()
                    )
                    user_name = user.full_name if user else None

        # -------- PARKING PASS --------
        elif line.code == InvoiceType.parking_pass.value:
            pp = db.query(ParkingPass).filter(
                ParkingPass.id == line.item_id,
                ParkingPass.is_deleted == False
            ).first()

            if pp:
                item_no = pp.pass_no

                if pp.user_id:
                    user = (
                        auth_db.query(Users)
                        .filter(
                            Users.id == pp.user_id,
                            Users.is_deleted == False
                        )
                        .first()
                    )
                    user_name = user.full_name if user else None

        # -------- OWNER MAINTENANCE --------
        elif line.code == InvoiceType.owner_maintenance.value:
            om = db.query(OwnerMaintenanceCharge).filter(
                OwnerMaintenanceCharge.id == line.item_id,
                OwnerMaintenanceCharge.is_deleted == False
            ).first()

            if om:
                item_no = om.maintenance_no

                if om.owner_user_id:
                    user = (
                        auth_db.query(Users)
                        .filter(
                            Users.id == om.owner_user_id,
                            Users.is_deleted == False
                        )
                        .first()
                    )
                    user_name = user.full_name if user else None

    # -------------------------------------------------
    # FETCH PAYMENTS
    # -------------------------------------------------
    payments = db.query(PaymentAR).filter(
        PaymentAR.invoice_id == invoice_id,
        PaymentAR.org_id == org_id,
        PaymentAR.is_deleted == False
    ).order_by(PaymentAR.paid_at.asc()).all()

    payment_out_list = [
        PaymentOut.model_validate({
            "id": p.id,
            "org_id": p.org_id,
            "invoice_id": p.invoice_id,
            "invoice_no": invoice.invoice_no,
            "code": code,
            "item_no": item_no,
            "user_name": user_name,
            "method": p.method,
            "ref_no": p.ref_no,
            "amount": p.amount,
            "paid_at": p.paid_at,
            "meta": p.meta
        })
        for p in payments
    ]

    # -------------------------------------------------
    # FINAL RESPONSE
    # -------------------------------------------------
    return InvoicePaymentHistoryOut(
        invoice_id=invoice.id,
        invoice_no=invoice.invoice_no,
        total_amount=totals.grand_total,
        status=invoice.status,
        code=code,
        item_no=item_no,
        user_name=user_name,
        payments=payment_out_list
    )


def invoice_type_lookup(db: Session, org_id: UUID):
    return [
        {"id": type.value, "name": type.name.replace('_', ' ').title()}
        for type in InvoiceType
    ]


def save_invoice_payment_detail(
    db: Session,
    payload: PaymentCreateWithInvoice,
    current_user: UserToken
):
    try:
        # ---------------------------
        # 0. Validate invoice_id
        # ---------------------------
        if not payload.invoice_id:
            return error_response(message="Invoice is required")

        invoice: Invoice = db.query(Invoice).filter(
            Invoice.id == payload.invoice_id,
            Invoice.is_deleted == False
        ).first()

        if not invoice:
            return error_response(message="Invalid invoice")

        # ---------------------------
        # 1. Validate invoice status
        # ---------------------------
        if invoice.status not in ("issued", "draft", "partial"):
            return error_response(
                message="Payment details can only be added to issued, partial, or draft invoices"
            )

        # ---------------------------
        # 2. Validate ref_no
        # ---------------------------
        if not payload.ref_no:
            return error_response(message="ref_no is mandatory and must be unique per invoice")

        # ---------------------------
        # 3. Determine existing payment
        # ---------------------------
        payment: PaymentAR | None = None
        if payload.id:
            # Update mode
            payment = db.query(PaymentAR).filter(
                PaymentAR.id == payload.id,
                PaymentAR.is_deleted == False
            ).first()
            if not payment:
                return error_response(message="Payment with selected ID not found")

            # Duplicate ref_no check (exclude self)
            duplicate = db.query(PaymentAR).filter(
                PaymentAR.invoice_id == invoice.id,
                PaymentAR.ref_no == payload.ref_no,
                PaymentAR.id != payload.id,
                PaymentAR.is_deleted == False
            ).first()
            if duplicate:
                return error_response(
                    message=f"Duplicate payment ref_no '{payload.ref_no}' for this invoice"
                )

            # Update fields
            payment.method = payload.method or payment.method
            payment.ref_no = payload.ref_no
            if payload.amount is not None:
                payment.amount = float(payload.amount)
            if payload.paid_at:
                payment.paid_at = payload.paid_at
            if payload.meta is not None:
                payment.meta = payload.meta or {}

        else:
            # Create mode: check if payment with same ref_no exists
            payment = db.query(PaymentAR).filter(
                PaymentAR.invoice_id == invoice.id,
                PaymentAR.ref_no == payload.ref_no,
                PaymentAR.is_deleted == False
            ).first()

            if payment:
                # Treat as update
                payment.method = payload.method or payment.method
                if payload.amount is not None:
                    payment.amount = float(payload.amount)
                if payload.paid_at:
                    payment.paid_at = payload.paid_at
                if payload.meta is not None:
                    payment.meta = payload.meta or {}
            else:
                # Truly new payment
                payment = PaymentAR(
                    org_id=current_user.org_id,
                    invoice_id=invoice.id,
                    method=payload.method,
                    ref_no=payload.ref_no,
                    amount=float(payload.amount),
                    paid_at=payload.paid_at or datetime.utcnow(),
                    meta=payload.meta or {}
                )
                db.add(payment)
                db.flush()

                # ---------------------------
                # 4. Notifications for new payment
                # ---------------------------
                line_codes = {line.code.lower() for line in invoice.lines}
                for code in line_codes:
                    if code == "rent":
                        db.add(Notification(
                            user_id=current_user.user_id,
                            type=NotificationType.alert,
                            title="Rent Payment Recorded",
                            message=f"Payment of {payment.amount} recorded for invoice {invoice.invoice_no}",
                            posted_date=datetime.utcnow(),
                            priority=PriorityType.medium,
                            read=False,
                            is_deleted=False,
                            is_email=False
                        ))
                    elif code in ("maintenance", "owner maintenance"):
                        db.add(Notification(
                            user_id=current_user.user_id,
                            type=NotificationType.alert,
                            title="Owner Maintenance Payment Recorded",
                            message=f"Payment of {payment.amount} recorded for invoice {invoice.invoice_no}",
                            posted_date=datetime.utcnow(),
                            priority=PriorityType.medium,
                            read=False,
                            is_deleted=False,
                            is_email=False
                        ))

        # ---------------------------
        # 5. Recalculate invoice status
        # ---------------------------
        payments = db.query(PaymentAR).filter(
            PaymentAR.invoice_id == invoice.id,
            PaymentAR.is_deleted == False
        ).all()

        total_paid = sum(float(p.amount) for p in payments)
        invoice_total = float(invoice.totals.get("grand") or 0)

        if total_paid >= invoice_total - 0.01:
            invoice.status = "paid"
            invoice.is_paid = True
        elif invoice.due_date and invoice.due_date < date.today():
            invoice.status = "overdue"
            invoice.is_paid = False
        elif total_paid > 0:
            invoice.status = "partial"
            invoice.is_paid = False
        else:
            invoice.status = "issued"
            invoice.is_paid = False

        # ---------------------------
        # 6. Full payment notifications
        # ---------------------------
        if invoice.status == "paid":
            line_codes = {line.code.lower() for line in invoice.lines}
            for code in line_codes:
                if code == "rent":
                    db.add(Notification(
                        user_id=current_user.user_id,
                        type=NotificationType.alert,
                        title="Rent Invoice Fully Paid",
                        message=f"Invoice {invoice.invoice_no} has been fully paid. Total: {invoice_total}",
                        posted_date=datetime.utcnow(),
                        priority=PriorityType.medium,
                        read=False,
                        is_deleted=False,
                        is_email=False
                    ))
                elif code in ("maintenance", "owner maintenance"):
                    db.add(Notification(
                        user_id=current_user.user_id,
                        type=NotificationType.alert,
                        title="Owner Maintenance Invoice Fully Paid",
                        message=f"Invoice {invoice.invoice_no} has been fully paid. Total: {invoice_total}",
                        posted_date=datetime.utcnow(),
                        priority=PriorityType.medium,
                        read=False,
                        is_deleted=False,
                        is_email=False
                    ))

        db.commit()
        return success_response(data={"payment_id": str(payment.id)})

    except Exception as e:
        db.rollback()
        raise e


def generate_invoice_number(db: Session, org_id: UUID):
    # Get the maximum existing number
    last_number = (
        db.query(
            func.max(
                cast(func.replace(Invoice.invoice_no, "INV-", ""), Integer)
            )
        )
        .filter(Invoice.org_id == org_id)
        .scalar()
    )

    # Start from 1 if no invoices exist
    next_number = (last_number or 0) + 1

    # Zero-pad only up to 4 digits
    if next_number <= 9999:
        invoice_no = f"INV-{next_number:04d}"
    else:
        invoice_no = f"INV-{next_number}"

    return invoice_no


def apply_advance_to_invoice(db: Session, invoice: Invoice):
    invoice_amount = float(invoice.totals.get("grand", 0))

    advances = db.query(CustomerAdvance).filter(
        CustomerAdvance.user_id == invoice.user_id,
        CustomerAdvance.balance > 0
    ).order_by(CustomerAdvance.created_at).all()

    remaining = invoice_amount

    for adv in advances:
        if remaining <= 0:
            break

        use_amount = min(float(adv.balance), remaining)

        # Record adjustment
        adjustment = AdvanceAdjustment(
            advance_id=adv.id,
            invoice_id=invoice.id,
            amount=use_amount
        )
        db.add(adjustment)

        # Record as payment entry
        payment = PaymentAR(
            org_id=invoice.org_id,
            invoice_id=invoice.id,
            method="advance",
            ref_no=f"ADV-{adv.id}",
            amount=use_amount
        )
        db.add(payment)

        adv.balance -= use_amount
        remaining -= use_amount

    # Update invoice status
    if remaining <= 0:
        invoice.status = "paid"
        invoice.is_paid = True
    elif remaining < invoice_amount:
        invoice.status = "partial"
        invoice.is_paid = False
