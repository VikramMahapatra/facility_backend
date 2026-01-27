from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors


def generate_invoice_pdf(invoice):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # -------- HEADER --------
    elements.append(Paragraph("<b>INVOICE RECEIPT</b>", styles["Title"]))
    elements.append(
        Paragraph(f"Invoice No: {invoice.invoice_no}", styles["Normal"]))
    elements.append(
        Paragraph(f"Invoice Date: {invoice.date}", styles["Normal"]))
    elements.append(
        Paragraph(f"Due Date: {invoice.due_date}", styles["Normal"]))
    elements.append(
        Paragraph(f"Status: {invoice.status.upper()}", styles["Normal"]))
    elements.append(Paragraph("<br/>", styles["Normal"]))

    # -------- CUSTOMER --------
    elements.append(Paragraph("<b>Customer</b>", styles["Heading2"]))
    elements.append(Paragraph("-", styles["Normal"]))
    elements.append(
        Paragraph(f"Site: {invoice.site_name or '-'}", styles["Normal"]))
    elements.append(Paragraph("<br/>", styles["Normal"]))

    # -------- BILLABLE ITEM --------
    elements.append(Paragraph("<b>Billable Item</b>", styles["Heading2"]))
    elements.append(
        Paragraph(invoice.billable_item_name or "-", styles["Normal"]))
    elements.append(Paragraph("<br/>", styles["Normal"]))

    # -------- TOTALS --------
    totals = invoice.totals or {}
    totals_table = Table([
        ["Subtotal", f"₹ {totals.get('sub', 0)}"],
        ["Tax", f"₹ {totals.get('tax', 0)}"],
        ["Grand Total", f"₹ {totals.get('grand', 0)}"],
    ])

    totals_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
        ("BACKGROUND", (0, 2), (-1, 2), colors.lightgrey),
    ]))
    elements.append(totals_table)
    elements.append(Paragraph("<br/>", styles["Normal"]))

    # -------- PAYMENTS --------
    if invoice.payments:
        elements.append(Paragraph("<b>Payments</b>", styles["Heading2"]))
        rows = [["Date", "Method", "Ref No", "Amount"]]

        for p in invoice.payments:
            rows.append([
                p.paid_at,
                p.method,
                p.ref_no,
                f"₹ {p.amount}"
            ])

        payment_table = Table(rows)
        payment_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
        ]))
        elements.append(payment_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer
