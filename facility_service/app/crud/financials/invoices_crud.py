from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import Date, and_, func, cast, literal, or_, case, Numeric, text
from sqlalchemy.dialects.postgresql import JSONB
from facility_service.app.models.leasing_tenants.leases import Lease
from facility_service.app.models.leasing_tenants.tenant_spaces import TenantSpace
from facility_service.app.models.space_sites.owner_maintenances import OwnerMaintenanceCharge
from facility_service.app.models.space_sites.space_owners import SpaceOwner
from facility_service.app.models.space_sites.spaces import Space
from facility_service.app.models.system.notifications import Notification, NotificationType, PriorityType
from shared.helpers.json_response_helper import error_response
from shared.models.users import Users

from ...enum.revenue_enum import InvoicePayementMethod, InvoiceType

from ...models.parking_access.parking_pass import ParkingPass
from ...models.space_sites.sites import Site
from shared.core.schemas import Lookup, UserToken

from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.service_ticket.tickets_work_order import TicketWorkOrder
from ...models.service_ticket.tickets import Ticket
from ...models.financials.invoices import Invoice, PaymentAR
from ...schemas.financials.invoices_schemas import InvoiceCreate, InvoiceOut, InvoicePaymentHistoryOut, InvoiceTotalsRequest, InvoiceTotalsResponse, InvoiceUpdate, InvoicesRequest, InvoicesResponse, PaymentCreateWithInvoice, PaymentOut
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

            elif invoice.billable_item_type == "rent":
                lease = db.query(Lease).filter(
                    Lease.id == invoice.billable_item_id,
                    Lease.is_deleted == False
                ).first()
                if lease:
                    lease_no = lease.lease_number
                    if lease.start_date and lease.end_date:
                        start_str = lease.start_date.strftime("%d %b %Y")
                        end_str = lease.end_date.strftime("%d %b %Y")
                        month_year = lease.start_date.strftime("%b %Y")
                        billable_item_name = f"Rent | Lease {lease_no} | {start_str} - {end_str}"
                    else:
                        billable_item_name = f"Rent | Lease {lease_no}"

            elif invoice.billable_item_type == "parking pass":
                parking_pass = db.query(ParkingPass).filter(
                    ParkingPass.id == invoice.billable_item_id,
                    ParkingPass.is_deleted == False
                ).first()

                if parking_pass:
                    if parking_pass.start_date and parking_pass.end_date:
                        start_str = parking_pass.start_date.strftime(
                            "%d %b %Y")
                        end_str = parking_pass.end_date.strftime("%d %b %Y")
                        billable_item_name = (
                            f"Parking Pass | {parking_pass.pass_no} | "
                            f"{start_str}–{end_str}"
                        )
                    else:
                        billable_item_name = f"Parking Pass | {parking_pass.pass_no}"

            elif invoice.billable_item_type == "owner maintenance":
                owner_maintenance = db.query(OwnerMaintenanceCharge).filter(
                    OwnerMaintenanceCharge.id == invoice.billable_item_id,
                    OwnerMaintenanceCharge.is_deleted == False
                ).first()

                if owner_maintenance:
                    # Get space info
                    space = db.query(Space).filter(
                        Space.id == owner_maintenance.space_id).first()

                    if owner_maintenance.period_start and owner_maintenance.period_end:
                        start_str = owner_maintenance.period_start.strftime(
                            "%d %b %Y")
                        end_str = owner_maintenance.period_end.strftime(
                            "%d %b %Y")
                        space_name = space.name
                        billable_item_name = (
                            f"OM| {space_name} | {start_str} - {end_str} |{owner_maintenance.maintenance_no}")
                    else:
                        billable_item_name = f"OM | {owner_maintenance.maintenance_no}"

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


def get_payments(db: Session, auth_db: Session, org_id: str, params: InvoicesRequest):
    total = (
        db.query(func.count(PaymentAR.id))
        .join(Invoice, PaymentAR.invoice_id == Invoice.id)
        .filter(
            PaymentAR.org_id == org_id,
            Invoice.is_deleted == False  # ✅ ADD THIS
        )
        .scalar()
    )

    base_query = (
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
        customer_name = None

        if invoice.billable_item_type and invoice.billable_item_id:
            if invoice.billable_item_type == "work order":
                ticket_work_order = db.query(TicketWorkOrder).filter(
                    TicketWorkOrder.id == invoice.billable_item_id,
                    TicketWorkOrder.is_deleted == False
                ).first()
                if ticket_work_order:
                    ticket = db.query(Ticket).filter(
                        Ticket.id == ticket_work_order.ticket_id
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

            elif invoice.billable_item_type == "rent":
                lease = db.query(Lease).filter(
                    Lease.id == invoice.billable_item_id,
                    Lease.is_deleted == False
                ).first()
                if lease:
                    lease_no = lease.lease_number
                    if lease.start_date and lease.end_date:
                        start_str = lease.start_date.strftime("%d %b %Y")
                        end_str = lease.end_date.strftime("%d %b %Y")
                        month_year = lease.start_date.strftime("%b %Y")
                        billable_item_name = f"Rent | Lease {lease_no} | {start_str} - {end_str}"
                    else:
                        billable_item_name = f"Rent | Lease {lease_no}"

                    # Get customer name from lease
                    if lease.tenant:
                        tenant = lease.tenant
                        customer_name = tenant.name or tenant.legal_name

            elif invoice.billable_item_type == "parking pass":
                parking_pass = db.query(ParkingPass).filter(
                    ParkingPass.id == invoice.billable_item_id,
                    ParkingPass.is_deleted == False
                ).first()

                if parking_pass:
                    if parking_pass.start_date and parking_pass.end_date:
                        start_str = parking_pass.start_date.strftime(
                            "%d %b %Y")
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

            elif invoice.billable_item_type == "owner maintenance":
                owner_maintenance = db.query(OwnerMaintenanceCharge).filter(
                    OwnerMaintenanceCharge.id == invoice.billable_item_id,
                    OwnerMaintenanceCharge.is_deleted == False
                ).first()

                if owner_maintenance:
                    # Get space info
                    space = db.query(Space).filter(
                        Space.id == owner_maintenance.space_id).first()

                    if owner_maintenance.period_start and owner_maintenance.period_end:
                        start_str = owner_maintenance.period_start.strftime(
                            "%d %b %Y")
                        end_str = owner_maintenance.period_end.strftime(
                            "%d %b %Y")
                        space_name = space.name
                        billable_item_name = (
                            f"OM | {space_name} | {start_str} - {end_str} |{owner_maintenance.maintenance_no}")
                    else:
                        billable_item_name = f"OM | {owner_maintenance.maintenance_no}"

                    customer_name = None

                    if owner_maintenance.space_owner_id:
                        space_owner = (
                            db.query(SpaceOwner)
                            .filter(
                                SpaceOwner.id == owner_maintenance.space_owner_id
                            )
                            .first()
                        )

                        if space_owner and space_owner.owner_user_id:
                            user = (
                                auth_db.query(Users)
                                .filter(
                                    Users.id == space_owner.owner_user_id,
                                    Users.is_deleted == False
                                )
                                .first()
                            )

                            if user:
                                customer_name = user.full_name

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

    total_payments = float(
        total_payments_result) if total_payments_result else 0.0

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

    elif request.billable_item_type == "rent":
        lease = db.query(Lease).filter(
            Lease.id == request.billable_item_id,
            Lease.is_deleted == False
        ).first()

        if not lease:
            raise HTTPException(status_code=404, detail="Lease not found")

        # Keep same behaviour: formatted billable item name
        if lease.start_date and lease.end_date:
            lease_no = lease.lease_number
            start_str = lease.start_date.strftime("%d %b %Y")
            end_str = lease.end_date.strftime("%d %b %Y")
            month_year = lease.start_date.strftime("%b %Y")

            billable_item_name = (
                f"RENT | Lease {lease_no} | {start_str} - {end_str}"
            )
        else:
            billable_item_name = f" RENT | Lease {lease.lease_number} "

    elif request.billable_item_type == "parking pass":
        parking_pass = db.query(ParkingPass).filter(
            ParkingPass.id == request.billable_item_id,
            ParkingPass.is_deleted == False
        ).first()

        if not parking_pass:
            raise HTTPException(
                status_code=404, detail="Parking pass not found")

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

    elif request.billable_item_type == "owner maintenance":
        owner_maintenance = db.query(OwnerMaintenanceCharge).filter(
            OwnerMaintenanceCharge.id == request.billable_item_id,
            OwnerMaintenanceCharge.is_deleted == False
        ).first()

        if not owner_maintenance:
            raise HTTPException(
                status_code=404, detail="Owner maintenance charge not found")

        # Get space and site info for notification
        space = db.query(Space).filter(
            Space.id == owner_maintenance.space_id).first()
        site = db.query(Site).filter(
            Site.id == space.site_id).first() if space else None

        # Get owner info
        space_owner = db.query(SpaceOwner).filter(
            SpaceOwner.id == owner_maintenance.space_owner_id,
            SpaceOwner.is_active == True
        ).first()

        # Build billable item name
        if owner_maintenance.period_start and owner_maintenance.period_end:
            start_str = owner_maintenance.period_start.strftime("%d %b %Y")
            end_str = owner_maintenance.period_end.strftime("%d %b %Y")
            space_name = space.name
            billable_item_name = (
                f"OM | {space_name} | {start_str} - {end_str} |{owner_maintenance.maintenance_no}")
        else:
            billable_item_name = f"OM | {owner_maintenance.maintenance_no}"

    else:
        raise error_response(
            message="Invalid module_type. Must be 'work order', 'rent', 'parking pass', or 'owner maintenance'"
        )

    invoice_data = request.model_dump(exclude={"org_id"})
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

        invoice_amount = float(db_invoice.totals.get(
            "grand", 0)) if db_invoice.totals else 0

        # ADD THIS: Notification for invoice creation (lease charge only)
        if request.billable_item_type == "rent" and lease:
            # 1. Notification for invoice creation against admin
            invoice_notification = Notification(
                user_id=current_user.user_id,
                type=NotificationType.alert,
                title="Rent Invoice Created",
                message=f"Invoice {db_invoice.invoice_no} created for {billable_item_name}. Amount: {invoice_amount}",
                posted_date=datetime.utcnow(),
                priority=PriorityType.medium,
                read=False,
                is_deleted=False,
                is_email=False
            )
            db.add(invoice_notification)

            # ADD THIS: Notification for owner maintenance invoice
        elif request.billable_item_type == "owner maintenance" and space_owner:
            # 1. Notification for invoice creation
            invoice_notification = Notification(
                user_id=current_user.user_id,
                type=NotificationType.alert,
                title="Owner Maintenance Invoice Created",
                message=f"Invoice {db_invoice.invoice_no} created for {billable_item_name}. Amount: {invoice_amount}",
                posted_date=datetime.utcnow(),
                priority=PriorityType.medium,
                read=False,
                is_deleted=False,
                is_email=False
            )
            db.add(invoice_notification)

        # ADD THIS: Update owner maintenance charge with invoice_id
        if request.billable_item_type == "owner maintenance" and owner_maintenance:
            owner_maintenance.invoice_id = db_invoice.id
            owner_maintenance.status = "invoiced"

        # Single commit for everything
        db.commit()

        # Build response
        site_name = db_invoice.site.name if db_invoice.site else None
        payments_list = []
        invoice_dict = {
            **db_invoice.__dict__,
            "date": db_invoice.date.isoformat() if db_invoice.date else None,
            "due_date": db_invoice.due_date.isoformat() if db_invoice.due_date else None,
            "billable_item_name": billable_item_name,
            "site_name": site_name,
            "status": db_invoice.status,
            "is_paid": (db_invoice.status == "paid"),
            "payments": payments_list
        }
        invoice_out = InvoiceOut.model_validate(invoice_dict)
        return invoice_out

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


def update_invoice(db: Session, invoice_update: InvoiceUpdate, current_user):
    db_invoice = db.query(Invoice).filter(
        Invoice.id == invoice_update.id,
        Invoice.org_id == current_user.org_id,
        Invoice.is_deleted == False
    ).first()

    if not db_invoice:
        return error_response(
            message="Invoice not found"
        )

    # Validate totals if payments exist
    has_existing_payments = db.query(PaymentAR).filter(
        PaymentAR.invoice_id == db_invoice.id
    ).first() is not None

    if has_existing_payments and 'totals' in invoice_update.model_dump(exclude_unset=True):
        current_total = float(db_invoice.totals.get(
            "grand", 0.0)) if db_invoice.totals else 0.0
        new_total = float(invoice_update.totals.get(
            "grand", 0.0)) if invoice_update.totals else 0.0

        if new_total < current_total:
            return error_response(
                message="Cannot decrease invoice total after payments have been made"
            )

    # Update invoice fields (exclude id, payments, status)
    update_data = invoice_update.model_dump(
        exclude_unset=True, exclude={"id", "status"})
    for k, v in update_data.items():
        setattr(db_invoice, k, v)

    # 6️⃣ Recalculate invoice amount from updated totals
    invoice_amount = 0.0
    if db_invoice.totals and "grand" in db_invoice.totals:
        invoice_amount = float(db_invoice.totals.get("grand", 0.0))

    #  Store old status
    old_status = db_invoice.status

    #  Calculate new status
    new_status = calculate_invoice_status(
        db=db,
        invoice_id=db_invoice.id,
        invoice_amount=invoice_amount,
        due_date=db_invoice.due_date
    )

    db_invoice.status = new_status
    db_invoice.is_paid = (new_status == "paid")

    #  Commit all changes
    db.commit()
    db.refresh(db_invoice)

    #  Prepare response
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

        elif db_invoice.billable_item_type == "rent":
            lease = db.query(Lease).filter(
                Lease.id == db_invoice.billable_item_id,
                Lease.is_deleted == False
            ).first()

            if not lease:
                raise HTTPException(status_code=404, detail="Lease not found")

            # Keep same behaviour: formatted billable item name
            if lease.start_date and lease.end_date:
                lease_no = lease.lease_number
                start_str = lease.start_date.strftime("%d %b %Y")
                end_str = lease.end_date.strftime("%d %b %Y")
                month_year = lease.start_date.strftime("%b %Y")

                billable_item_name = (
                    f"RENT | Lease {lease_no} | {start_str} - {end_str}"
                )
            else:
                billable_item_name = f" RENT | Lease {lease.lease_number} "

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

        elif db_invoice.billable_item_type == "owner maintenance":
            owner_maintenance = db.query(OwnerMaintenanceCharge).filter(
                OwnerMaintenanceCharge.id == db_invoice.billable_item_id,
                OwnerMaintenanceCharge.is_deleted == False
            ).first()

            if owner_maintenance:
                space = db.query(Space).filter(
                    Space.id == owner_maintenance.space_id).first()
                if owner_maintenance.period_start and owner_maintenance.period_end:
                    start_str = owner_maintenance.period_start.strftime(
                        "%d %b %Y")
                    end_str = owner_maintenance.period_end.strftime("%d %b %Y")
                    space_name = space.name
                    billable_item_name = (
                        f"OM | {space_name} | {start_str} - {end_str} |{owner_maintenance.maintenance_no}")
                else:
                    billable_item_name = f"OM | {owner_maintenance.maintenance_no}"

    payments_list = []

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
                    func.lower(Ticket.status) == "open"
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

    elif billable_item_type == "rent":
        leases = db.query(Lease).filter(
            Lease.is_deleted == False,

            # Exclude leases already invoiced for rent
            ~Lease.id.in_(
                db.query(Invoice.billable_item_id).filter(
                    Invoice.org_id == org_id,
                    Invoice.billable_item_type == "rent charge",
                    Invoice.is_deleted == False,
                    Invoice.status != "void"
                )
            ),

            Lease.site_id == site_id,
            Lease.org_id == org_id
        ).all()

        for lease in leases:
            if lease.start_date and lease.end_date:
                formatted_name = (
                    f"RENT | Lease {lease.lease_number} | "
                    f"{lease.start_date:%d %b %Y} - {lease.end_date:%d %b %Y}"
                )
            else:
                formatted_name = f"RENT | Lease {lease.lease_number}"

            entities.append(
                Lookup(
                    id=str(lease.id),
                    name=formatted_name
                )
            )

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
    elif billable_item_type == "owner maintenance":
        owner_maintenances = db.query(OwnerMaintenanceCharge).filter(
            OwnerMaintenanceCharge.is_deleted == False,
            ~OwnerMaintenanceCharge.id.in_(
                db.query(Invoice.billable_item_id)
                .filter(
                    Invoice.org_id == org_id,
                    Invoice.billable_item_type == "owner maintenance",
                    Invoice.is_deleted == False,
                    Invoice.status != "void"
                )
            ),
            OwnerMaintenanceCharge.space.has(site_id=site_id),
            OwnerMaintenanceCharge.space.has(org_id=org_id)
        ).all()

        for om in owner_maintenances:
            space = db.query(Space).filter(Space.id == om.space_id).first()
            space_name = space.name
            if om.period_start and om.period_end:
                start_str = om.period_start.strftime("%d %b %Y")
                end_str = om.period_end.strftime("%d %b %Y")
                formatted_name = (
                    f"OM | {space_name} | {start_str} - {end_str} |{om.maintenance_no}")
            else:
                formatted_name = f"OM | {om.maintenance_no}"

            entities.append(Lookup(
                id=str(om.id),
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

    elif item_type == "rent":
        # Get lease
        lease = db.query(Lease).filter(
            Lease.id == billable_item_id,
            Lease.is_deleted == False
        ).first()

        if not lease:
            raise HTTPException(status_code=404, detail="Lease not found")

        # Calculate totals using rent_amount
        subtotal = lease.rent_amount
        tax = Decimal('0')
        grand_total = subtotal

    elif item_type == "owner maintenance":
        maintenance = db.query(OwnerMaintenanceCharge).filter(
            OwnerMaintenanceCharge.id == billable_item_id,
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


def build_invoice_billable_item_name(db, item_type, item_id):
    #  RENT (instead of lease charge)
    if item_type == "rent":
        lease = db.query(Lease).filter(
            Lease.id == item_id,
            Lease.is_deleted == False
        ).first()

        if lease:
            lease_no = lease.lease_number

            if lease.start_date and lease.end_date:
                return (
                    f"RENT | Lease {lease_no} | "
                    f"{lease.start_date:%d %b %Y} - {lease.end_date:%d %b %Y}"
                )

            return f"RENT | Lease {lease_no}"

    elif item_type == "work order":
        wo = db.query(TicketWorkOrder).filter(
            TicketWorkOrder.id == item_id
        ).first()
        if wo:
            ticket = db.query(Ticket).filter(
                Ticket.id == wo.ticket_id
            ).first()
            return f"{wo.wo_no} | Ticket {ticket.ticket_no}" if ticket else wo.wo_no

    elif item_type == "parking pass":
        pass_ = db.query(ParkingPass).filter(
            ParkingPass.id == item_id
        ).first()
        if pass_:
            return f"Parking Pass | {pass_.pass_no}"

    elif item_type == "owner maintenance":
        owner_maintenance = db.query(OwnerMaintenanceCharge).filter(
            OwnerMaintenanceCharge.id == item_id,
            OwnerMaintenanceCharge.is_deleted == False
        ).first()
        for om in owner_maintenance:
            space = db.query(Space).filter(Space.id == om.space_id).first()
            space_name = space.name
            if om.period_start and om.period_end:
                start_str = om.period_start.strftime("%d %b %Y")
                end_str = om.period_end.strftime("%d %b %Y")
                formatted_name = (
                    f"OM | {space_name} | {start_str} - {end_str} |{om.maintenance_no}")
            else:
                formatted_name = f"OM | {om.maintenance_no}"
            return formatted_name

    return None


def get_invoice_detail(db: Session, auth_db: Session, org_id: UUID, invoice_id: UUID) -> InvoiceOut:
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.site))
        .filter(
            Invoice.id == invoice_id,
            Invoice.org_id == org_id,
            Invoice.is_deleted == False
        )
        .first()
    )

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    site_name = invoice.site.name if invoice.site else None
    billable_item_name = None
    customer_name = None

    # -------------------------------------------------
    # BILLABLE ITEM + CUSTOMER
    # -------------------------------------------------
    if invoice.billable_item_type and invoice.billable_item_id:

        # ---------- WORK ORDER ----------
        if invoice.billable_item_type == "work order":
            wo = db.query(TicketWorkOrder).filter(
                TicketWorkOrder.id == invoice.billable_item_id,
                TicketWorkOrder.is_deleted == False
            ).first()

            if wo:
                ticket = db.query(Ticket).filter(
                    Ticket.id == wo.ticket_id
                ).first()

                billable_item_name = (
                    f"{wo.wo_no} | Ticket {ticket.ticket_no}"
                    if ticket and ticket.ticket_no
                    else wo.wo_no
                )

                if ticket:
                    if ticket.tenant:
                        customer_name = ticket.tenant.name or ticket.tenant.legal_name

        # ---------- LEASE CHARGE ----------
        elif invoice.billable_item_type == "rent":
            lease = db.query(Lease).filter(
                Lease.id == invoice.billable_item_id,
                Lease.is_deleted == False
            ).first()

            if lease:
                lease_no = lease.lease_number
                if lease.start_date and lease.end_date:
                    start_str = lease.start_date.strftime("%d %b %Y")
                    end_str = lease.end_date.strftime("%d %b %Y")
                    month_year = lease.start_date.strftime("%b %Y")
                    billable_item_name = f"Rent | Lease {lease_no} | {start_str} - {end_str}"
                else:
                    billable_item_name = f"Rent |Lease {lease_no}"

                # ✅ CUSTOMER (ALWAYS RUNS)
                if lease.tenant:
                    tenant = lease.tenant
                    customer_name = tenant.name or tenant.legal_name

        # ---------- PARKING PASS ----------
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
                        f"Parking Pass | {parking_pass.pass_no} | {start_str}–{end_str}"
                    )
                else:
                    billable_item_name = f"Parking Pass | {parking_pass.pass_no}"

                # ✅ CUSTOMER (ALWAYS RUNS)
                if parking_pass.pass_holder_name:
                    customer_name = parking_pass.pass_holder_name
                elif parking_pass.space and parking_pass.space.tenant:
                    customer_name = parking_pass.space.tenant.name or parking_pass.space.tenant.legal_name

        elif invoice.billable_item_type == "owner maintenance":
            owner_maintenance = db.query(OwnerMaintenanceCharge).filter(
                OwnerMaintenanceCharge.id == invoice.billable_item_id,
                OwnerMaintenanceCharge.is_deleted == False
            ).first()

            if owner_maintenance:
                space = db.query(Space).filter(
                    Space.id == owner_maintenance.space_id).first()
                if owner_maintenance.period_start and owner_maintenance.period_end:
                    start_str = owner_maintenance.period_start.strftime(
                        "%d %b %Y")
                    end_str = owner_maintenance.period_end.strftime("%d %b %Y")
                    space_name = space.name
                    billable_item_name = (
                        f"OM | {space_name} | {start_str} - {end_str} |{owner_maintenance.maintenance_no}")
                else:
                    billable_item_name = f"OM | {owner_maintenance.maintenance_no}"

                customer_name = None

                if owner_maintenance.space_owner_id:
                    space_owner = (
                        db.query(SpaceOwner)
                        .filter(
                            SpaceOwner.id == owner_maintenance.space_owner_id
                        )
                        .first()
                    )

                    if space_owner and space_owner.owner_user_id:
                        user = (
                            auth_db.query(Users)
                            .filter(
                                Users.id == space_owner.owner_user_id,
                                Users.is_deleted == False
                            )
                            .first()
                        )

                        if user:
                            customer_name = user.full_name

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
            "billable_item_name": billable_item_name,
            "method": p.method,
            "ref_no": p.ref_no,
            "amount": Decimal(str(p.amount)),
            "paid_at": p.paid_at.date().isoformat() if p.paid_at else None,
            "meta": p.meta,
            "customer_name": customer_name
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
        invoice_id=invoice.id,
        invoice_amount=invoice_amount,
        due_date=invoice.due_date
    )

    return InvoiceOut.model_validate({
        **invoice.__dict__,
        "date": invoice.date.isoformat() if invoice.date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "site_name": site_name,
        "billable_item_name": billable_item_name,
        "customer_name": customer_name,
        "status": actual_status,
        "is_paid": actual_status == "paid",
        "payments": payments_list,
        "currency": "INR"
    })


def get_invoice_payment_history(
    db: Session,
    auth_db: Session,
    org_id: UUID,
    invoice_id: UUID
) -> InvoicePaymentHistoryOut:

    #  Fetch invoice
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.org_id == org_id,
        Invoice.is_deleted == False
    ).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Calculate totals (grand_total)
    totals = calculate_invoice_totals(
        db,
        InvoiceTotalsRequest(
            billable_item_type=invoice.billable_item_type,
            billable_item_id=invoice.billable_item_id
        )
    )

    #  Derive billable_item_name (SAME logic you already use)
    billable_item_name = None
    customer_name = None

    if invoice.billable_item_type == "work order":
        wo = db.query(TicketWorkOrder).filter(
            TicketWorkOrder.id == invoice.billable_item_id,
            TicketWorkOrder.is_deleted == False
        ).first()
        if wo:
            ticket = db.query(Ticket).filter(
                Ticket.id == wo.ticket_id
            ).first()
            if ticket and ticket.ticket_no:
                billable_item_name = f"{wo.wo_no} | Ticket {ticket.ticket_no}"
            else:
                billable_item_name = wo.wo_no

        # Get customer name from ticket
        if ticket.tenant:
            customer_name = f"{ticket.tenant.name}"
        elif ticket.vendor:
            customer_name = ticket.vendor.name
        elif ticket.space and ticket.space.tenant:
            # Fallback: get from space tenant
            space_tenant = ticket.space.tenant
            customer_name = f"{space_tenant.name} {space_tenant.name}"

    elif invoice.billable_item_type == "rent":
        lc = db.query(Lease).filter(
            Lease.id == invoice.billable_item_id,
            Lease.is_deleted == False
        ).first()
        if lc:
            billable_item_name = f"Rent | Lease {lc.lease_number}"
            # Get customer name from lease
            if lc.tenant:
                customer_name = lc.tenant.name or lc.tenant.legal_name

    elif invoice.billable_item_type == "parking pass":
        pp = db.query(ParkingPass).filter(
            ParkingPass.id == invoice.billable_item_id,
            ParkingPass.is_deleted == False
        ).first()
        if pp:
            billable_item_name = f"Parking Pass | {pp.pass_no}"
        # Get customer name
        if pp.pass_holder_name:
            customer_name = pp.pass_holder_name
        elif pp.space and pp.space.tenant:
            # Fallback to space tenant
            space_tenant = pp.space.tenant
            customer_name = f"{space_tenant.name} {space_tenant.name}"

    elif invoice.billable_item_type == "owner maintenance":
        owner_maintenance = db.query(OwnerMaintenanceCharge).filter(
            OwnerMaintenanceCharge.id == invoice.billable_item_id,
            OwnerMaintenanceCharge.is_deleted == False
        ).first()

        if owner_maintenance:
            space = db.query(Space).filter(
                Space.id == owner_maintenance.space_id).first()
            if owner_maintenance.period_start and owner_maintenance.period_end:
                start_str = owner_maintenance.period_start.strftime("%d %b %Y")
                end_str = owner_maintenance.period_end.strftime("%d %b %Y")
                space_name = space.name
                billable_item_name = (
                    f"OM | {space_name} | {start_str} - {end_str} |{owner_maintenance.maintenance_no}")
            else:
                billable_item_name = f"OM | {owner_maintenance.maintenance_no}"

                customer_name = None

                if owner_maintenance.space_owner_id:
                    space_owner = (
                        db.query(SpaceOwner)
                        .filter(
                            SpaceOwner.id == owner_maintenance.space_owner_id
                        )
                        .first()
                    )

                    if space_owner and space_owner.owner_user_id:
                        user = (
                            auth_db.query(Users)
                            .filter(
                                Users.id == space_owner.owner_user_id,
                                Users.is_deleted == False
                            )
                            .first()
                        )

                        if user:
                            customer_name = user.full_name

    # Fetch payments
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
            "billable_item_name": billable_item_name,
            "method": p.method,
            "ref_no": p.ref_no,
            "amount": p.amount,
            "paid_at": p.paid_at,
            "meta": p.meta,
            "customer_name": customer_name
        })
        for p in payments
    ]

    # Final response
    return InvoicePaymentHistoryOut(
        invoice_id=invoice.id,
        invoice_no=invoice.invoice_no,
        total_amount=totals.grand_total,
        status=invoice.status,
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
        # 0 Validate invoice_id
        if not payload.invoice_id:
            return error_response(message="Invoice is required")

        # 1 Fetch & validate invoice
        invoice = db.query(Invoice).filter(
            Invoice.id == payload.invoice_id,
            Invoice.is_deleted == False
        ).first()

        if not invoice:
            return error_response(message="Invalid invoice")

        # 2 Allow only valid lease states
        if invoice.status not in ("issued", "draft", "partial"):
            return error_response(
                message="Payment details can only be added to issued,partial or draft invoices"
            )

        # ref_no is mandatory
        if not payload.ref_no:
            error_response(
                message="ref_no is mandatory and must be unique per invoice")

        # Duplicate in DB for SAME invoice
        existing_payment = db.query(PaymentAR).filter(
            PaymentAR.invoice_id == payload.invoice_id,
            PaymentAR.ref_no == payload.ref_no
        ).first()

        if existing_payment:
            error_response(
                message=f"Payment ref_no '{payload.ref_no}' already exists")

        if payload.id:
            existing_payment = db.query(PaymentAR).filter(
                PaymentAR.id == payload.id,
                PaymentAR.is_deleted == False
            ).first()

            if not existing_payment:
                return error_response(
                    message=f"Payment with selected ID not found"
                )

            # ✅ DB duplicate check ONLY for updates
            duplicate = db.query(PaymentAR).filter(
                PaymentAR.invoice_id == payload.id,
                PaymentAR.ref_no == payload.ref_no,
                PaymentAR.id != payload.id
            ).first()

            if duplicate:
                return error_response(
                    message=f"Duplicate payment ref_no '{payload.ref_no}' for this invoice"
                )

            # Update fields
            existing_payment.method = payload.method or existing_payment.method
            existing_payment.ref_no = payload.ref_no
            if payload.amount is not None:
                existing_payment.amount = float(payload.amount)
            if payload.paid_at:
                existing_payment.paid_at = payload.paid_at
            if payload.meta is not None:
                existing_payment.meta = payload.meta or {}

        else:
            # 🔍 Check if payment already exists by ref_no for this invoice
            existing_payment = db.query(PaymentAR).filter(
                PaymentAR.invoice_id == payload.invoice_id,
                PaymentAR.ref_no == payload.ref_no
            ).first()

            if existing_payment:
                # 🔁 Treat as UPDATE (not create)
                existing_payment.method = payload.method or existing_payment.method
                if payload.amount is not None:
                    existing_payment.amount = float(payload.amount)
                if payload.paid_at:
                    existing_payment.paid_at = payload.paid_at
                if payload.meta is not None:
                    existing_payment.meta = payload.meta or {}

            else:
                # ➕ Truly NEW payment
                payment_ar = PaymentAR(
                    org_id=current_user.org_id,
                    invoice_id=payload.invoice_id,
                    method=payload.method,
                    ref_no=payload.ref_no,
                    amount=float(payload.amount),
                    paid_at=payload.paid_at or datetime.utcnow(),
                    meta=payload.meta or {}
                )

                db.add(payment_ar)
                db.flush()

                if invoice.billable_item_type == "rent":
                    # Notification for EACH payment (if any payments) in create mode

                    payment_notification = Notification(
                        user_id=current_user.user_id,
                        type=NotificationType.alert,
                        title="Rent Payment Recorded",
                        message=f"Payment of {payment_ar.amount} recorded for invoice {invoice.invoice_no}",
                        posted_date=datetime.utcnow(),
                        priority=PriorityType.medium,
                        read=False,
                        is_deleted=False,
                        is_email=False
                    )
                    db.add(payment_notification)
                    # ADD THIS: Notification for owner maintenance invoice
                elif invoice.billable_item_type == "owner maintenance":  # and space_owner:

                    payment_notification = Notification(
                        user_id=current_user.user_id,
                        type=NotificationType.alert,
                        title="Owner Maintenance Payment Recorded",
                        message=f"Payment of {payment_ar.amount} recorded for invoice {invoice.invoice_no}",
                        posted_date=datetime.utcnow(),
                        priority=PriorityType.medium,
                        read=False,
                        is_deleted=False,
                        is_email=False
                    )
                    db.add(payment_notification)

        # Calculate invoice amount
        invoice_amount = invoice.totals.get(
            "grand") if invoice.totals else None

        payments_created = db.query(PaymentAR).filter(
            PaymentAR.invoice_id == payload.id,
            PaymentAR.is_deleted == False
        ).all()

        total_payments = sum(float(p.amount) for p in payments_created)

        # Calculate status (payments are in session but not yet committed)
        if payments_created:

            # Use Decimal for comparison
            invoice_decimal = Decimal(str(invoice_amount))
            payments_decimal = Decimal(str(total_payments))

            if payments_decimal >= invoice_decimal - Decimal('0.01'):
                actual_status = "paid"
            elif invoice.due_date and invoice.due_date < date.today():
                actual_status = "overdue"
            else:
                actual_status = "partial"
        else:
            actual_status = "issued"

        # Update invoice with correct status
        invoice.status = actual_status
        invoice.is_paid = (actual_status == "paid")

        if invoice.billable_item_type == "rent":

            if actual_status == "paid":
                full_payment_notification = Notification(
                    user_id=current_user.user_id,
                    type=NotificationType.alert,
                    title="Rent Invoice Fully Paid",
                    message=f"Invoice {invoice.invoice_no} has been fully paid. Total: {invoice_amount}",
                    posted_date=datetime.utcnow(),
                    priority=PriorityType.medium,
                    read=False,
                    is_deleted=False,
                    is_email=False
                )
                db.add(full_payment_notification)

                # ADD THIS: Notification for owner maintenance invoice
        elif invoice.billable_item_type == "owner maintenance":  # and space_owner:
            # 3. Notification for FULL PAYMENT
            if actual_status == "paid":
                full_payment_notification = Notification(
                    user_id=current_user.user_id,
                    type=NotificationType.alert,
                    title="Owner Maintenance Invoice Fully Paid",
                    message=f"Invoice {invoice.invoice_no} has been fully paid. Total: {invoice_amount}",
                    posted_date=datetime.utcnow(),
                    priority=PriorityType.medium,
                    read=False,
                    is_deleted=False,
                    is_email=False
                )
                db.add(full_payment_notification)

        db.commit()

    except Exception as e:
        db.rollback()
        raise e
