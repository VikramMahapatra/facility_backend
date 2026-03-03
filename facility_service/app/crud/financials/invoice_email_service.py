from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from facility_service.app.crud.system.system_settings_crud import get_system_settings
from facility_service.app.models.financials.customer_advances import AdvanceAdjustment
from facility_service.app.models.financials.invoices import Invoice, PaymentAR
from facility_service.app.models.space_sites.orgs import Org
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
                status_code=str(AppStatusCode.BAD_REQUEST),
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

        organization_name = organization.name if organization else "Organization"

        # -----------------------------
        # Customer (User)
        # -----------------------------
        customer = get_user_detail(invoice.user_id)
        customer_name = customer.full_name if customer else "Customer"

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
            organization_name=organization_name,
            customer_name=customer_name,
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
            "customer_name": customer_name,
            "invoice_no": invoice.invoice_no,
            "organization_name": organization_name,
            "invoice_total": float(invoice_total),
            "advance_used": float(advance_used),
            "payments_total": float(payments_total),
            "balance": float(balance),
            "due_date": invoice.due_date,
            "currency": invoice.currency,
        }

        subject = f"Invoice {invoice.invoice_no} from {organization_name}"

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
