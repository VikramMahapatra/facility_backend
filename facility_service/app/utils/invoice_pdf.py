from decimal import Decimal
from io import BytesIO
import os
import tempfile
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib import colors

from ..models.space_sites.orgs import Org
from ..schemas.financials.invoices_schemas import InvoiceCustomerDetail
from ..schemas.system.system_settings_schema import SystemSettingsOut


def generate_invoice_pdf(
    invoice,
    organization: Org,
    customer: InvoiceCustomerDetail,
    payments_total: float,
    advance_used: float,
    balance: float,
    system_settings: SystemSettingsOut
):
    styles = getSampleStyleSheet()
    story = []

    # --------------------------------------------------
    # INVOICE TITLE
    # --------------------------------------------------

    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Title"],
        alignment=1,  # Center
    )

    story.append(Paragraph("INVOICE", title_style))
    story.append(Spacer(1, 20))

    # --------------------------------------------------
    # COMPANY / CUSTOMER / INVOICE META
    # --------------------------------------------------

    org_details = f"""
    <b>{organization.name}</b><br/>
    Phone: {organization.contact_phone or ''}<br/>
    Email: {organization.billing_email or ''}
    """

    bill_to_lines = ["<b>Bill To</b>"]

    if customer.customer_name:
        bill_to_lines.append(customer.customer_name)

    if customer.space_name:
        bill_to_lines.append(f"Unit: {customer.space_name}")

    if customer.customer_address:
        bill_to_lines.append(customer.customer_address)

    if customer.customer_phone:
        bill_to_lines.append(f"Phone: {customer.customer_phone}")

    customer_details = "<br/>".join(bill_to_lines)

    invoice_meta = f"""
    <b>Invoice No:</b> {invoice.invoice_no}<br/>
    <b>Invoice Date:</b> {invoice.date.strftime('%d %b %Y')}<br/>
    """

    if invoice.due_date:
        invoice_meta += f"<b>Due Date:</b> {invoice.due_date.strftime('%d %b %Y')}"

    header_data = [
        [
            Paragraph(org_details, styles["Normal"]),
            Paragraph(customer_details, styles["Normal"]),
            Paragraph(invoice_meta, styles["Normal"]),
        ]
    ]

    header_table = Table(
        header_data,
        colWidths=[220, 180, 160],
        hAlign="LEFT"
    )

    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),

            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),

            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ])
    )

    story.append(header_table)
    story.append(Spacer(1, 25))

    # --------------------------------------------------
    # LINE ITEMS TABLE
    # --------------------------------------------------
    data = [
        ["Type", "Description", "Amount", "Tax %"]
    ]

    subtotal = Decimal("0")
    tax_total = Decimal("0")

    for line in invoice.lines:
        amount = Decimal(line.amount)
        tax_pct = Decimal(line.tax_pct or 0)

        subtotal += amount
        tax_total += (amount * tax_pct) / 100

        data.append([
            line.code,
            line.description or "",
            f"{amount:.2f} {system_settings.general.currency}",
            f"{tax_pct:.2f}%",
        ])

    table = Table(data, colWidths=[80, 240, 100, 80])

    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (2, 1), (3, -1), "RIGHT"),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])
    )

    story.append(table)
    story.append(Spacer(1, 20))

    # --------------------------------------------------
    # TOTALS SECTION
    # --------------------------------------------------
    totals = invoice.totals or {}

    subtotal_val = Decimal(totals.get("sub", subtotal))
    tax_val = Decimal(totals.get("tax", tax_total))
    grand_total = Decimal(totals.get("grand", subtotal_val + tax_val))

    summary_data = [
        ["Subtotal", f"{subtotal_val:.2f} {system_settings.general.currency}"],
        ["Tax", f"{tax_val:.2f} {system_settings.general.currency}"],
        ["Grand Total",
            f"{grand_total:.2f} {system_settings.general.currency}"],
        ["Advance Used",
            f"- {Decimal(advance_used):.2f} {system_settings.general.currency}"],
        ["Payments Received",
            f"- {Decimal(payments_total):.2f} {system_settings.general.currency}"],
        ["Balance Due",
            f"{Decimal(balance):.2f} {system_settings.general.currency}"],
    ]

    summary_table = Table(summary_data, colWidths=[300, 200])

    summary_table.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("FONTNAME", (-1, -1), (-1, -1), "Helvetica-Bold"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ])
    )

    story.append(summary_table)

    story.append(Spacer(1, 30))

    # --------------------------------------------------
    # FOOTER
    # --------------------------------------------------
    story.append(
        Paragraph("This is a system generated customer invoice.",
                  styles["Italic"])
    )

    # --------------------------------------------------
    # BUILD PDF
    # --------------------------------------------------

    safe_invoice_no = invoice.invoice_no.replace("/", "-")

    BASE_DIR = "storage/invoices"
    org_dir = os.path.join(BASE_DIR, str(invoice.org_id))
    os.makedirs(org_dir, exist_ok=True)

    file_path = os.path.join(
        org_dir,
        f"Invoice_{safe_invoice_no}.pdf"
    )

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    doc.build(story)

    return file_path


def generate_payment_receipt_pdf(
    payment,
    invoice,
    organization_name: str,
    customer_name: str,
    balance_after_payment: float,
    system_settings: SystemSettingsOut
):

    styles = getSampleStyleSheet()
    story = []

    # --------------------------------------------------
    # HEADER
    # --------------------------------------------------
    story.append(Paragraph(
        f"<b>{organization_name}</b>",
        styles["Title"]
    ))

    story.append(Spacer(1, 12))

    story.append(Paragraph(
        "<b>PAYMENT RECEIPT</b>",
        styles["Heading2"]
    ))

    story.append(Spacer(1, 12))

    # --------------------------------------------------
    # RECEIPT DETAILS
    # --------------------------------------------------
    receipt_data = [
        ["Receipt No", f"RCPT-{str(payment.id)[:8]}"],
        ["Invoice No", invoice.invoice_no],
        ["Customer", customer_name],
        ["Payment Date", payment.paid_at.strftime("%d %b %Y")],
        ["Payment Method", payment.method.upper()],
        ["Reference No", payment.ref_no or "-"],
    ]

    details_table = Table(receipt_data, colWidths=[160, 340])

    details_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(details_table)
    story.append(Spacer(1, 20))

    # --------------------------------------------------
    # PAYMENT SUMMARY
    # --------------------------------------------------
    grand_total = Decimal(invoice.totals.get("grand", 0))
    paid_amount = Decimal(payment.amount)

    summary_data = [
        ["Invoice Total",
            f"{grand_total:.2f} {system_settings.general.currency}"],
        ["Amount Paid",
            f"{paid_amount:.2f} {system_settings.general.currency}"],
        ["Balance After Payment",
            f"{Decimal(balance_after_payment):.2f} {system_settings.general.currency}"],
    ]

    summary_table = Table(summary_data, colWidths=[300, 200])

    summary_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(summary_table)

    story.append(Spacer(1, 30))

    # --------------------------------------------------
    # FOOTER
    # --------------------------------------------------
    story.append(Paragraph(
        "Payment received with thanks.",
        styles["Italic"]
    ))

    # --------------------------------------------------
    # FILE STORAGE (same pattern as invoice)
    # --------------------------------------------------
    BASE_DIR = "storage/receipts"
    org_dir = os.path.join(BASE_DIR, str(invoice.org_id))
    os.makedirs(org_dir, exist_ok=True)

    receipt_no = f"RCPT-{str(payment.id)[:8]}"

    file_path = os.path.join(
        org_dir,
        f"{receipt_no}.pdf"
    )

    # --------------------------------------------------
    # BUILD PDF
    # --------------------------------------------------
    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    doc.build(story)

    return file_path


def generate_bill_pdf(
    bill,
    organization_name: str,
    vendor_name: str,
    payments_total: float,
    balance: float,
    system_settings: SystemSettingsOut
):
    styles = getSampleStyleSheet()
    story = []

    # --------------------------------------------------
    # HEADER
    # --------------------------------------------------
    story.append(Paragraph(f"<b>{organization_name}</b>", styles["Title"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>VENDOR BILL</b>", styles["Heading2"]))
    story.append(Spacer(1, 10))

    story.append(
        Paragraph(f"<b>Bill No:</b> {bill.bill_no}", styles["Normal"]))
    story.append(Paragraph(f"<b>Vendor:</b> {vendor_name}", styles["Normal"]))
    story.append(
        Paragraph(
            f"<b>Bill Date:</b> {bill.date.strftime('%d %b %Y')}",
            styles["Normal"],
        )
    )

    story.append(Spacer(1, 20))

    # --------------------------------------------------
    # LINE ITEMS
    # --------------------------------------------------
    data = [["Description", "Amount", "Tax %"]]

    subtotal = Decimal("0")
    tax_total = Decimal("0")

    for line in bill.lines:
        amount = Decimal(line.amount)
        tax_pct = Decimal(line.tax_pct or 0)

        subtotal += amount
        tax_total += (amount * tax_pct) / 100

        data.append([
            line.description or "",
            f"{amount:.2f} {system_settings.general.currency}",
            f"{tax_pct:.2f}%"
        ])

    table = Table(data, colWidths=[300, 120, 80])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(table)
    story.append(Spacer(1, 20))

    # --------------------------------------------------
    # TOTALS
    # --------------------------------------------------
    totals = bill.totals or {}

    subtotal_val = Decimal(totals.get("sub", subtotal))
    tax_val = Decimal(totals.get("tax", tax_total))
    grand_total = Decimal(totals.get("grand", subtotal_val + tax_val))

    summary_data = [
        ["Subtotal", f"{subtotal_val:.2f} {system_settings.general.currency}"],
        ["Tax", f"{tax_val:.2f} {system_settings.general.currency}"],
        ["Grand Total",
            f"{grand_total:.2f} {system_settings.general.currency}"],
        ["Payments Made",
            f"- {Decimal(payments_total):.2f} {system_settings.general.currency}"],
        ["Balance Payable",
            f"{Decimal(balance):.2f} {system_settings.general.currency}"],
    ]

    summary_table = Table(summary_data, colWidths=[300, 200])

    summary_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (-1, -1), (-1, -1), "Helvetica-Bold"),
    ]))

    story.append(summary_table)

    story.append(Spacer(1, 30))
    story.append(
        Paragraph("This is a system generated vendor bill.", styles["Italic"])
    )

    # --------------------------------------------------
    # SAVE FILE
    # --------------------------------------------------
    safe_bill_no = bill.bill_no.replace("/", "-")

    base_dir = "storage/bills"
    org_dir = os.path.join(base_dir, str(bill.org_id))
    os.makedirs(org_dir, exist_ok=True)

    file_path = os.path.join(
        org_dir,
        f"Bill_{safe_bill_no}.pdf"
    )

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    doc.build(story)

    return file_path


def generate_bill_payment_pdf(
    payment,
    organization_name: str,
    vendor_name: str,
    bill_no: str,
    system_settings: SystemSettingsOut
):
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>{organization_name}</b>", styles["Title"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>PAYMENT VOUCHER</b>", styles["Heading2"]))
    story.append(Spacer(1, 20))

    data = [
        ["Vendor", vendor_name],
        ["Bill No", bill_no],
        ["Payment Method", payment.method],
        ["Reference No", payment.ref_no or "-"],
        ["Amount Paid",
            f"{payment.amount:.2f} {system_settings.general.currency}"],
        ["Paid At", payment.paid_at.strftime("%d %b %Y %H:%M")],
    ]

    table = Table(data, colWidths=[200, 300])
    story.append(table)

    story.append(Spacer(1, 40))
    story.append(
        Paragraph("Payment successfully recorded.", styles["Italic"])
    )

    # SAVE
    base_dir = "storage/bill_payments"
    org_dir = os.path.join(base_dir, str(payment.org_id))
    os.makedirs(org_dir, exist_ok=True)

    filename = f"Bill_Payment_{payment.id}.pdf"
    file_path = os.path.join(org_dir, filename)

    doc = SimpleDocTemplate(file_path, pagesize=A4)
    doc.build(story)

    return file_path
