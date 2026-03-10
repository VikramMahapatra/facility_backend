from decimal import Decimal
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from facility_service.app.crud.system.system_settings_crud import get_system_settings
from facility_service.app.enum.revenue_enum import InvoiceType
from facility_service.app.models.financials.customer_advances import AdvanceAdjustment
from facility_service.app.models.financials.invoices import Invoice, PaymentAR
from facility_service.app.models.leasing_tenants.tenants import Tenant
from facility_service.app.models.space_sites.orgs import Org
from facility_service.app.schemas.financials.invoices_schemas import InvoiceCustomerDetail
from shared.helpers.email_helper import EmailHelper
from shared.helpers.json_response_helper import error_response
from shared.helpers.user_helper import get_user_detail
from shared.utils.app_status_code import AppStatusCode
from facility_service.app.utils.invoice_pdf import generate_invoice_pdf


class InvoiceEmailService:

    def __init__(self):
        self.email_helper = EmailHelper()

    def send_invoice_to_customer(
        self,
        db: Session,
        invoice: Invoice,
        customer_email: str
    ):
        # -----------------------------
        # Validate Status
        # -----------------------------
        if invoice.status not in ["issued", "partial", "paid"]:
            return error_response(
                status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
                message="Only issued invoices can be emailed"
            )

        system_settings = get_system_settings(db, invoice.org_id)

        # -----------------------------
        # Organization
        # -----------------------------
        organization = (
            db.query(Org)
            .filter(Org.id == invoice.org_id)
            .first()
        )

        # -----------------------------
        # Customer (User)
        # -----------------------------

        invoice_code = invoice.lines[0].code if invoice.lines else InvoiceType.rent.value

        if invoice_code == InvoiceType.owner_maintenance.value:
            customer = get_user_detail(invoice.user_id)
            customer_detail = InvoiceCustomerDetail(
                customer_name=customer.full_name if customer else "Customer",
                space_name=invoice.space.name,
                customer_phone=customer.phone,
            )
        else:
            customer = get_tenant_detail(db, invoice.user_id)

            customer_detail = InvoiceCustomerDetail(
                customer_name=customer.name if customer else "Customer",
                space_name=invoice.space.name,
                customer_phone=customer.phone,
                customer_address=format_address(customer.address)
            )

        # -----------------------------
        # Invoice Total
        # -----------------------------
        invoice_total = Decimal(invoice.totals.get("grand", 0))

        # -----------------------------
        # Advance Adjusted
        # -----------------------------
        advance_used = (
            db.query(func.coalesce(func.sum(AdvanceAdjustment.amount), 0))
            .filter(AdvanceAdjustment.invoice_id == invoice.id)
            .scalar()
        ) or Decimal("0")

        # -----------------------------
        # Payments Made
        # -----------------------------
        payments_total = (
            db.query(func.coalesce(func.sum(PaymentAR.amount), 0))
            .filter(
                PaymentAR.invoice_id == invoice.id,
                PaymentAR.is_deleted == False
            )
            .scalar()
        ) or Decimal("0")

        # -----------------------------
        # Balance Calculation
        # -----------------------------
        balance = invoice_total - advance_used - payments_total

        # safety
        if balance < 0:
            balance = Decimal("0")

        # -----------------------------
        # Generate Invoice PDF
        # -----------------------------
        pdf_path = generate_invoice_pdf(
            invoice=invoice,
            organization=organization,
            customer=customer_detail,
            payments_total=float(payments_total),
            advance_used=float(advance_used),
            balance=float(balance),
            system_settings=system_settings
        )

        # -----------------------------
        # Decide Email Template
        # -----------------------------
        template_code = self._decide_template(
            float(balance),
            float(advance_used)
        )

        # -----------------------------
        # Email Context
        # -----------------------------
        context = {
            "customer_name": customer.name,
            "invoice_no": invoice.invoice_no,
            "organization_name": organization.name,
            "invoice_total": float(invoice_total),
            "advance_used": float(advance_used),
            "payments_total": float(payments_total),
            "balance": float(balance),
            "due_date": invoice.due_date,
            "currency": invoice.currency,
        }

        subject = f"Invoice {invoice.invoice_no} from {organization.name}"

        print("Sending email...")

        # -----------------------------
        # Send Email
        # -----------------------------
        return self.email_helper.send_email(
            db=db,
            template_code=template_code,
            recipients=[customer_email],
            subject=subject,
            context=context,
            attachments=[pdf_path],
        )

    def _decide_template(self, balance, advance_used):
        """
        Decide which template to use
        """
        if balance <= 0:
            return "invoice_fully_adjusted"

        if advance_used > 0:
            return "invoice_partially_adjusted"

        return "invoice_payment_required"


def get_tenant_detail(db: Session, user_id: UUID):
    tenant = db.query(Tenant).filter(Tenant.user_id ==
                                     user_id, Tenant.is_deleted == False).first()
    return tenant if tenant else None


def format_address(address: dict) -> str:
    if not address:
        return ""

    lines = []

    for key in ["line1", "line2"]:
        if address.get(key):
            lines.append(address[key])

    city_state = ", ".join(
        filter(None, [address.get("city"), address.get("state")])
    )

    if address.get("pincode"):
        city_state = f"{city_state} - {address['pincode']}" if city_state else address["pincode"]

    if city_state:
        lines.append(city_state)

    return "\n".join(lines)
