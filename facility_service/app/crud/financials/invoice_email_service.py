from sqlalchemy.orm import Session

from facility_service.app.models.space_sites.orgs import Org
from shared.helpers.email_helper import EmailHelper
from shared.helpers.json_response_helper import error_response
from shared.utils.app_status_code import AppStatusCode
from shared.utils.invoice_pdf import generate_invoice_pdf


class InvoiceEmailService:

    def __init__(self):
        self.email_helper = EmailHelper()

    def send_invoice_to_customer(
        self,
        db: Session,
        invoice,
        customer_email: str
    ):
        if invoice.status != "issued":
            return error_response(
                status_code=str(AppStatusCode),
                message="Invoice must be issued before sending email"
            )

        # Get organization name
        organization = (
            db.query(Org)
            .filter(Org.id == invoice.org_id)
            .first()
        )

        organization_name = organization.name if organization else "Organization"

        invoice_total = float(invoice.total_amount or 0)
        advance_used = float(invoice.advance_adjusted or 0)
        balance = invoice_total - advance_used

        # Generate PDF
        pdf_path = generate_invoice_pdf(invoice, organization_name)

        template_code = self._decide_template(balance, advance_used)

        context = {
            "customer_name": invoice.customer_name,
            "invoice_no": invoice.invoice_no,
            "organization_name": organization_name,
            "invoice_total": invoice_total,
            "advance_used": advance_used,
            "balance": balance,
            "due_date": invoice.due_date
        }

        subject = f"Invoice {invoice.invoice_no} from {organization_name}"

        return self.email_helper.send_email(
            db=db,
            template_code=template_code,
            recipients=[customer_email],
            subject=subject,
            context=context,
            attachments=[pdf_path]
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
