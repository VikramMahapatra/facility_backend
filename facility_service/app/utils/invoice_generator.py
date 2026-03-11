
from datetime import date, timedelta
from calendar import monthrange
from decimal import Decimal
from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from facility_service.app.crud.financials.bills_crud import generate_bill_number
from facility_service.app.crud.financials.invoices_crud import apply_advance_to_invoice, create_invoice, generate_invoice_number
from facility_service.app.models.financials.bills import Bill, BillLine
from facility_service.app.models.financials.invoices import Invoice, InvoiceLine
from facility_service.app.models.parking_access.parking_pass import ParkingPass
from facility_service.app.models.service_ticket.tickets_work_order import TicketWorkOrder
from facility_service.app.schemas.financials.bills_schemas import AutoBillResponse
from facility_service.app.schemas.financials.invoices_schemas import AutoInvoiceResponse, InvoiceCreate, InvoiceLineCreate

from ..enum.revenue_enum import InvoiceType
from ..models.leasing_tenants.lease_charges import LeaseCharge
from ..models.leasing_tenants.leases import Lease
from ..models.space_sites.owner_maintenances import OwnerMaintenanceCharge
from shared.core.schemas import UserToken


def get_month_range(target_date: date):
    today = target_date
    billing_end = today + timedelta(days=30)
    return today, billing_end


async def auto_generate_monthly_invoices(
    background_tasks: BackgroundTasks,
    db: Session,
    org_id: UUID,
    target_date: date,
    current_user: UserToken
):
    today, billing_end = get_month_range(target_date)

    created = {
        "invoices": [],
    }

    # =====================================================
    # RENT (AR)
    # =====================================================
    rent_charges = db.query(LeaseCharge).join(Lease).filter(
        LeaseCharge.period_start >= today,
        LeaseCharge.period_start <= billing_end,
        LeaseCharge.charge_code == InvoiceType.rent.value,
        LeaseCharge.invoice_id == None,
        LeaseCharge.is_deleted == False,
        Lease.org_id == org_id,
        Lease.is_deleted == False,
        Lease.status == "active"
    ).all()

    print("rent charges", len(rent_charges))

    for charge in rent_charges:
        lease = charge.lease

        invoice = await create_ar_invoice(
            background_tasks=background_tasks,
            db=db,
            org_id=org_id,
            site_id=lease.site_id,
            space_id=lease.space_id,
            user_id=lease.user_id,
            code=InvoiceType.rent.value,
            item_id=charge.id,
            description="Monthly Rent",
            amount=charge.amount,
            due_date=charge.period_end + timedelta(days=7),
            current_user=current_user
        )

        charge.invoice_id = invoice.id
        created["invoices"].append(invoice.invoice_no)

    # =====================================================
    # OWNER MAINTENANCE (AR)
    # =====================================================
    maint = db.query(OwnerMaintenanceCharge).filter(
        OwnerMaintenanceCharge.period_start >= today,
        OwnerMaintenanceCharge.period_start <= billing_end,
        OwnerMaintenanceCharge.invoice_id == None,
        OwnerMaintenanceCharge.org_id == org_id,
        OwnerMaintenanceCharge.is_deleted == False
    ).all()

    for charge in maint:
        space = charge.space

        invoice = await create_ar_invoice(
            background_tasks=background_tasks,
            db=db,
            org_id=org_id,
            user_id=charge.space_owner.owner_user_id,
            site_id=space.site_id,
            space_id=charge.space_id,
            code=InvoiceType.owner_maintenance.value,
            item_id=charge.id,
            description="Owner Maintenance",
            amount=charge.amount,
            due_date=charge.period_end + timedelta(days=7),
            current_user=current_user
        )

        charge.invoice_id = invoice.id
        created["invoices"].append(invoice.invoice_no)

    # =====================================================
    # WORK ORDERS
    # =====================================================
    work_orders = db.query(TicketWorkOrder).filter(
        TicketWorkOrder.created_at >= today,
        TicketWorkOrder.created_at <= billing_end,
        TicketWorkOrder.invoice_id == None,
        TicketWorkOrder.bill_to_type.in_(["tenant", "owner"])
    ).all()

    for wo in work_orders:
        ticket = wo.ticket

        # Vendor → AP Bill
        if wo.bill_to_type in ["tenant", "owner"]:
            invoice = await create_ar_invoice(
                background_tasks=background_tasks,
                db=db,
                org_id=org_id,
                user_id=wo.bill_to_id,
                site_id=ticket.site_id,
                space_id=ticket.space_id,
                code=InvoiceType.work_order.value,
                item_id=wo.id,
                description=f"Work Order #{wo.wo_no}",
                amount=wo.total_amount,
                due_date=date.today() + timedelta(days=7),
                current_user=current_user
            )

            wo.invoice_id = invoice.id
            created["invoices"].append(invoice.invoice_no)

    # =====================================================
    # PARKING PASS (AR)
    # =====================================================
    parking_passes = db.query(ParkingPass).filter(
        ParkingPass.valid_from >= today,
        ParkingPass.valid_from <= billing_end,
        ParkingPass.invoice_id == None
    ).all()

    for p in parking_passes:

        invoice = await create_ar_invoice(
            background_tasks=background_tasks,
            db=db,
            org_id=org_id,
            user_id=p.partner_id,
            site_id=p.site_id,
            space_id=p.space_id,
            code=InvoiceType.parking_pass.value,
            item_id=p.id,
            description="Parking Pass",
            amount=p.charge_amount,
            due_date=date.today() + timedelta(days=7),
            current_user=current_user
        )

        p.invoice_id = invoice.id
        created["invoices"].append(invoice.invoice_no)

    db.commit()

    return AutoInvoiceResponse(
        total_invoice_created=len(created["invoices"])
    )


async def create_ar_invoice(
    background_tasks: BackgroundTasks,
    db: Session,
    org_id: UUID,
    site_id: UUID,
    space_id: UUID,
    user_id: UUID,
    code: str,
    item_id: UUID,
    description: str,
    amount: float,
    due_date: date,
    current_user: UserToken
):
    tax_pct = 5  # or dynamic
    sub = Decimal(amount)
    tax = (sub * Decimal(tax_pct)) / Decimal(100)
    grand = sub + tax

    line = InvoiceLineCreate(
        code=code,
        item_id=item_id,
        description=description,
        amount=amount,
        tax_pct=tax_pct
    )

    invoice = InvoiceCreate(
        org_id=org_id,
        user_id=user_id,
        site_id=site_id,
        space_id=space_id,
        status="issued",
        is_paid=False,
        date=date.today(),
        due_date=due_date,
        totals={
            "sub": float(round(sub, 2)),
            "tax": float(round(tax, 2)),
            "grand": float(round(grand, 2))
        },
        lines=[line],
        send_email=False
    )

    db_invoice = await create_invoice(
        background_tasks, db, org_id, invoice, None, current_user)

    return db_invoice


def auto_generate_monthly_bills(
    db: Session,
    org_id: UUID,
    target_date: date,
    current_user: UserToken
):
    today, billing_end = get_month_range(target_date)

    created = {
        "bills": []
    }

    work_orders = db.query(TicketWorkOrder).filter(
        TicketWorkOrder.created_at >= today,
        TicketWorkOrder.created_at <= billing_end,
        TicketWorkOrder.invoice_id == None,
        TicketWorkOrder.bill_id == None
    ).all()

    for wo in work_orders:
        ticket = wo.ticket

        # Vendor → AP Bill
        if wo.bill_to_type == "vendor":

            bill = create_ap_bill(
                db=db,
                org_id=org_id,
                vendor_id=wo.bill_to_id,
                description=f"Work Order #{wo.wo_no}",
                amount=wo.total_amount
            )

            wo.bill_id = bill.id
            created["bills"].append(bill.bill_no)

    db.commit()

    return AutoBillResponse(
        total_invoice_created=len(created["bills"])
    )


def create_ap_bill(
    db: Session,
    org_id: UUID,
    vendor_id: UUID,
    description: str,
    amount: float
):
    tax_pct = 5  # or dynamic
    sub = Decimal(amount)
    tax = (sub * Decimal(tax_pct)) / Decimal(100)
    grand = sub + tax

    bill = Bill(
        org_id=org_id,
        vendor_id=vendor_id,
        bill_no=generate_bill_number(db, org_id),
        status="issued",
        date=date.today(),
        totals={
            "sub": float(round(sub, 2)),
            "tax": float(round(tax, 2)),
            "grand": float(round(grand, 2))
        }
    )

    db.add(bill)
    db.flush()

    bill_line = BillLine(
        bill_id=bill.id,
        description=description,
        amount=amount
    )

    db.add(bill_line)

    return bill
