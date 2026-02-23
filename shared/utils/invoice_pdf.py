from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib import colors


def generate_invoice_pdf(invoice, organization_name):
    file_path = f"/tmp/invoice_{invoice.invoice_no}.pdf"

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>{organization_name}</b>", styles["Title"]))
    story.append(Spacer(1, 10))

    story.append(
        Paragraph(f"Invoice No: {invoice.invoice_no}", styles["Normal"]))
    story.append(
        Paragraph(f"Customer: {invoice.customer_name}", styles["Normal"]))
    story.append(Paragraph(f"Date: {invoice.created_at}", styles["Normal"]))
    story.append(Spacer(1, 20))

    data = [
        ["Description", "Amount"],
    ]

    for item in invoice.items:
        data.append([item.name, f"₹{item.amount}"])

    data.append(["Total", f"₹{invoice.total_amount}"])

    table = Table(data)
    story.append(table)

    doc = SimpleDocTemplate(file_path)
    doc.build(story)

    return file_path


def get_invoice_email_template(
    customer_name,
    invoice_no,
    organization_name,
    total,
    advance_used,
    balance,
    due_date
):
    if balance <= 0:
        message = f"""
        <p>Advance has been fully adjusted against this invoice.</p>
        <p><strong>No payment is required.</strong></p>
        """
    elif advance_used > 0:
        message = f"""
        <p>Invoice Total: <strong>₹{total}</strong></p>
        <p>Advance Adjusted: <strong>₹{advance_used}</strong></p>
        <p>Remaining Balance: <strong>₹{balance}</strong></p>
        """
    else:
        message = f"""
        <p>Total Amount Due: <strong>₹{total}</strong></p>
        """

    return f"""
    <html>
    <body style="font-family: Arial; background:#f5f7fb; padding:20px;">
        <div style="max-width:600px;background:white;padding:30px;border-radius:10px;">
            
            <h2 style="color:#2b2f36;">{organization_name}</h2>

            <p>Hi <strong>{customer_name}</strong>,</p>

            <p>Your invoice <strong>{invoice_no}</strong> has been issued.</p>

            {message}

            <p>Due Date: <strong>{due_date}</strong></p>

            <p>Please find the attached invoice PDF.</p>

            <hr/>

            <p style="color:gray;font-size:12px;">
            This is an automated message from {organization_name}
            </p>

        </div>
    </body>
    </html>
    """


def generate_invoice_pdf_old(invoice):
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Right", alignment=TA_RIGHT))
    elements = []

    # ==================================================
    # HEADER
    # ==================================================
    header = Table(
        [[
            Paragraph("<b>COMPANY NAME</b><br/>Property Management",
                      styles["Normal"]),
            Paragraph(
                f"<b>INVOICE</b><br/>"
                f"Invoice No: {invoice.invoice_no}<br/>"
                f"Invoice Date: {invoice.date}<br/>"
                f"Due Date: {invoice.due_date or '-'}<br/>"
                f"Status: {invoice.status.upper()}",
                styles["Right"],
            )
        ]],
        colWidths=[300, 200]
    )
    elements.append(header)
    elements.append(Spacer(1, 20))

    # ==================================================
    # BILL TO
    # ==================================================
    elements.append(Paragraph("<b>Bill To</b>", styles["Heading2"]))

    bill_to = Table(
        [
            ["Site", invoice.site_name or "-"],
            ["Invoice Type", invoice.billable_item_type or "-"],
            ["Currency", invoice.currency],
        ],
        colWidths=[150, 350]
    )

    bill_to.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(bill_to)
    elements.append(Spacer(1, 20))

    # ==================================================
    # DESCRIPTION TABLE (WITH PERIOD)
    # ==================================================
    elements.append(Paragraph("<b>Description</b>", styles["Heading2"]))

    description_table = Table(
        [
            ["Description", "Period", "Amount"],
            [
                "Rent",
                invoice.billable_item_name.replace(
                    "Rent | ", "") if invoice.billable_item_name else "-",
                f"₹ {invoice.totals.get('sub', 0):,.2f}",
            ],
        ],
        colWidths=[220, 160, 120]
    )

    description_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(description_table)
    elements.append(Spacer(1, 15))

    # ==================================================
    # TOTALS + GST BREAKUP (ALIGNED)
    # ==================================================
    totals = invoice.totals or {}
    subtotal = totals.get("sub", 0)
    tax = totals.get("tax", 0)
    grand = totals.get("grand", 0)

    cgst = tax / 2
    sgst = tax / 2

    totals_table = Table(
        [
            ["", "Subtotal", f"₹ {subtotal:,.2f}"],
            ["", "CGST (9%)", f"₹ {cgst:,.2f}"],
            ["", "SGST (9%)", f"₹ {sgst:,.2f}"],
            ["", "GRAND TOTAL", f"₹ {grand:,.2f}"],
        ],
        colWidths=[220, 160, 120]
    )

    totals_table.setStyle(TableStyle([
        ("GRID", (1, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("BACKGROUND", (1, -1), (-1, -1), colors.lightgrey),
        ("FONT", (1, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(totals_table)
    elements.append(Spacer(1, 20))

    # ==================================================
    # PAYMENTS (SAME WIDTH)
    # ==================================================
    if invoice.payments:
        elements.append(Paragraph("<b>Payments</b>", styles["Heading2"]))

        payment_rows = [["Date", "Method", "Reference", "Amount"]]
        for p in invoice.payments:
            payment_rows.append([
                p.paid_at or "-",
                p.method.upper(),
                p.ref_no or "-",
                f"₹ {p.amount:,.2f}",
            ])

        payments_table = Table(
            payment_rows,
            colWidths=[150, 150, 80, 120]
        )

        payments_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
            ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))

        elements.append(payments_table)

    # ==================================================
    doc.build(elements)
    buffer.seek(0)
    return buffer
