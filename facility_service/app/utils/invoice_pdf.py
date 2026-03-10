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
from num2words import num2words

from ..models.space_sites.orgs import Org
from ..schemas.financials.invoices_schemas import InvoiceCustomerDetail
from ..schemas.system.system_settings_schema import SystemSettingsOut


def generate_invoice_pdf(
    invoice,
    organization,
    customer,
    payments_total: float,
    advance_used: float,
    balance: float,
    system_settings
):
    styles = getSampleStyleSheet()
    story = []

    # A4 Page Width is ~595. With 40pt margins on both sides, usable width is 515.
    PAGE_WIDTH = 515

    # --------------------------------------------------
    # 1. HEADER (Organization Details Centered)
    # --------------------------------------------------
    org_name = organization.name or "Organization"
    org_phone = organization.contact_phone or ""
    org_email = organization.billing_email or ""

    header_html = f"""
    <para align='center'>
        <b><font size='18'>{org_name}</font></b><br/><br/>
        <font size='10'>Phone: {org_phone} | Email: {org_email}</font><br/><br/>
    </para>
    """
    story.append(Paragraph(header_html, styles["Normal"]))
    story.append(Spacer(1, 13))

    line_table = Table([['']], colWidths=[PAGE_WIDTH], rowHeights=[2])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#003b46")),
        ('PADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 15))

    # --------------------------------------------------
    # 2. CUSTOMER & INVOICE DETAILS GRID BOX
    # --------------------------------------------------
    info_data = [
        ["Owner", f": {customer.customer_name}", "Invoice Number", f": {invoice.invoice_no}"],
        ["House", f": {customer.space_name}", "Invoice Date", f": {invoice.date.strftime('%d %b %Y')}"],
        ["Phone", f": {customer.customer_phone}", "Due Date", f": {invoice.due_date.strftime('%d %b %Y') if invoice.due_date else ''}"],
        ["Owner Address", f": {customer.customer_address}", "", ""],
    ]

    info_table = Table(info_data, colWidths=[90, 180, 100, 145])
    info_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 15))

    # --------------------------------------------------
    # 3. TITLE BAR
    # --------------------------------------------------
    invoice_type_label = 'GENERAL'
    if invoice.lines and len(invoice.lines) > 0 and invoice.lines[0].code:
        raw_code = str(invoice.lines[0].code)
        invoice_type_label = raw_code.replace('_', ' ').replace('-', ' ').upper()
    
    title_text = f"{invoice_type_label} DETAILS"
    
    title_table = Table([[title_text]], colWidths=[PAGE_WIDTH])
    title_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#003b46")),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(title_table)

    # --------------------------------------------------
    # 4. LINE ITEMS TABLE
    # --------------------------------------------------
    item_data = [
        ['Description', 'Tax %', 'Amount']
    ]

    subtotal = Decimal("0")
    tax_total = Decimal("0")

    for line in invoice.lines:
        amount = Decimal(line.amount)
        tax_pct = Decimal(line.tax_pct or 0)
        subtotal += amount
        tax_total += (amount * tax_pct) / 100

        desc = line.description or invoice_type_label
        item_data.append([
            Paragraph(desc, styles["Normal"]),
            f"{tax_pct:.2f}%",
            f"{amount:.2f}"
        ])

    totals = invoice.totals or {}
    subtotal_val = Decimal(totals.get("sub", subtotal))
    tax_val = Decimal(totals.get("tax", tax_total))
    grand_total = Decimal(totals.get("grand", subtotal_val + tax_val))

    item_data.append(['', '', ''])
    item_data.append(['', 'SUB TOTAL', f"{subtotal_val:.2f}"])
    
    if tax_val > 0:
        item_data.append(['', 'TAX', f"{tax_val:.2f}"])

    item_table = Table(item_data, colWidths=[335, 80, 100])
    item_table.setStyle(TableStyle([
        ('LINELEFT', (0, 0), (-1, -1), 0.5, colors.grey),
        ('LINERIGHT', (0, 0), (-1, -1), 0.5, colors.grey),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor("#003b46")),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEABOVE', (1, -2), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (1, -2), (1, -1), 'Helvetica-Bold'), 
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(item_table)

    # --------------------------------------------------
    # 5. TOTAL BAR
    # --------------------------------------------------
    total_data = [['TOTAL', f"{grand_total:.2f} {system_settings.general.currency}"]]
    total_table = Table(total_data, colWidths=[415, 100])
    total_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#003b46")),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 13),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(total_table)

    # --------------------------------------------------
    # 6. IN WORDS BOX
    # --------------------------------------------------
    amount_in_words = num2words(float(grand_total)).replace('-', ' ').title()
    words_text = f"In Words: <b>{amount_in_words} {system_settings.general.currency} Only</b>"

    words_table = Table([[Paragraph(words_text, styles["Normal"])]], colWidths=[PAGE_WIDTH])
    words_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ]))
    story.append(words_table)

    # --------------------------------------------------
    # 7. FOOTER
    # --------------------------------------------------
    story.append(Spacer(1, 5))
    story.append(Paragraph(
        "<para align='right'><font color='#555555'><i>This is a computer generated invoice and requires no authentication.</i></font></para>", 
        styles["Normal"]
    ))
    story.append(Spacer(1, 15))

    # --------------------------------------------------
    # 8. PAYMENT SUMMARY
    # --------------------------------------------------
    summary_title = Table([["PAYMENT SUMMARY"]], colWidths=[PAGE_WIDTH])
    summary_title.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#003b46")),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(summary_title)

    summary_data = [
        ["Advance Used", "Payments Received", "Balance Due"],
        [
            f"{Decimal(advance_used):.2f} {system_settings.general.currency}", 
            f"{Decimal(payments_total):.2f} {system_settings.general.currency}", 
            f"{Decimal(balance):.2f} {system_settings.general.currency}"
        ]
    ]
    summary_table = Table(summary_data, colWidths=[171, 172, 172])
    summary_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(summary_table)

    # --------------------------------------------------
    # 9. NOTES / TERMS
    # --------------------------------------------------
    notes_text = ""
    if invoice.meta and isinstance(invoice.meta, dict):
        notes_text = invoice.meta.get("notes", "")

    if notes_text:
        story.append(Spacer(1, 20))
        notes_text = notes_text.replace("\n", "<br/>")
        story.append(Paragraph(f"<b>Notes / Terms:</b><br/><br/>{notes_text}", styles["Normal"]))

    # --------------------------------------------------
    # 10. BUILD PDF
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
    system_settings
):
    styles = getSampleStyleSheet()
    story = []

    PAGE_WIDTH = 515

    # --------------------------------------------------
    # 1. HEADER (Organization Details Centered)
    # --------------------------------------------------
    header_html = f"""
    <para align='center'>
        <b><font size='18'>{organization_name}</font></b><br/><br/>
    </para>
    """
    story.append(Paragraph(header_html, styles["Normal"]))
    story.append(Spacer(1, 5))

    line_table = Table([['']], colWidths=[PAGE_WIDTH], rowHeights=[2])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#1E5631")),
        ('PADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 15))

    # --------------------------------------------------
    # 2. CUSTOMER & RECEIPT DETAILS GRID BOX
    # --------------------------------------------------
    info_data = [
        ["Customer", f": {customer_name}", "Receipt No", f": RCPT-{str(payment.id)[:8]}"],
        ["Invoice No", f": {invoice.invoice_no}", "Payment Date", f": {payment.paid_at.strftime('%d %b %Y')}"],
        ["Pay Method", f": {payment.method.upper()}", "Reference No", f": {payment.ref_no or '-'}"],
    ]

    info_table = Table(info_data, colWidths=[90, 180, 100, 145])
    info_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 15))

    # --------------------------------------------------
    # 3. TITLE BAR
    # --------------------------------------------------
    title_table = Table([["PAYMENT RECEIPT"]], colWidths=[PAGE_WIDTH])
    title_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#1E5631")),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(title_table)

    # --------------------------------------------------
    # 4. PAYMENT AMOUNT TABLE
    # --------------------------------------------------
    paid_amount = Decimal(payment.amount)
    grand_total = Decimal(invoice.totals.get("grand", 0)) if invoice.totals else Decimal("0")

    item_data = [
        ['Description', 'Amount']
    ]

    desc = f"Payment received towards Invoice: {invoice.invoice_no}"
    item_data.append([
        Paragraph(desc, styles["Normal"]),
        f"{paid_amount:.2f}"
    ])
    
    item_data.append(['', ''])

    item_table = Table(item_data, colWidths=[415, 100])
    item_table.setStyle(TableStyle([
        ('LINELEFT', (0, 0), (-1, -1), 0.5, colors.grey),
        ('LINERIGHT', (0, 0), (-1, -1), 0.5, colors.grey),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor("#1E5631")),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 20),
    ]))
    story.append(item_table)

    # --------------------------------------------------
    # 5. TOTAL PAID BAR
    # --------------------------------------------------
    total_data = [['TOTAL PAID', f"{paid_amount:.2f} {system_settings.general.currency}"]]
    
    total_table = Table(total_data, colWidths=[415, 100])
    total_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#1E5631")),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(total_table)

    # --------------------------------------------------
    # 6. IN WORDS BOX
    # --------------------------------------------------
    amount_in_words = num2words(float(paid_amount)).replace('-', ' ').title()
    words_text = f"In Words: <b>{amount_in_words} {system_settings.general.currency} Only</b>"

    words_table = Table([[Paragraph(words_text, styles["Normal"])]], colWidths=[PAGE_WIDTH])
    words_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ]))
    story.append(words_table)
    story.append(Spacer(1, 20))

    # --------------------------------------------------
    # 7. INVOICE BALANCE SUMMARY
    # --------------------------------------------------
    summary_title = Table([["INVOICE BALANCE SUMMARY"]], colWidths=[PAGE_WIDTH])
    summary_title.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#1E5631")),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(summary_title)

    summary_data = [
        ["Invoice Total", "Amount Paid", "Balance After Payment"],
        [
            f"{grand_total:.2f} {system_settings.general.currency}", 
            f"{paid_amount:.2f} {system_settings.general.currency}", 
            f"{Decimal(balance_after_payment):.2f} {system_settings.general.currency}"
        ]
    ]
    summary_table = Table(summary_data, colWidths=[171, 172, 172])
    summary_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(summary_table)

    # --------------------------------------------------
    # 8. FOOTER
    # --------------------------------------------------
    story.append(Spacer(1, 15))
    story.append(Paragraph(
        "<para align='right'><font color='#555555'><i>Payment received with thanks.<br/>This is a computer generated receipt and requires no authentication.</i></font></para>", 
        styles["Normal"]
    ))

    # --------------------------------------------------
    # 9. BUILD PDF
    # --------------------------------------------------
    BASE_DIR = "storage/receipts"
    org_dir = os.path.join(BASE_DIR, str(invoice.org_id))
    os.makedirs(org_dir, exist_ok=True)

    receipt_no = f"RCPT-{str(payment.id)[:8]}"

    file_path = os.path.join(
        org_dir,
        f"{receipt_no}.pdf"
    )

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=30,
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
