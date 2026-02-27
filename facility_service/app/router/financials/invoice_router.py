import json
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from shared.helpers.json_response_helper import success_response
from ...crud.financials import invoices_crud as crud
from ...schemas.financials.invoices_schemas import AdvancePaymentCreate, AdvancePaymentOut, AdvancePaymentResponse, InvoiceCreate, InvoiceDetailRequest, InvoiceOut, InvoicePaymentHistoryOut, InvoiceTotalsRequest, InvoiceTotalsResponse, InvoiceUpdate, InvoicesOverview, InvoicesRequest, InvoicesResponse, PaymentCreateWithInvoice, PaymentOut, PaymentResponse
from shared.core.database import get_auth_db, get_facility_db as get_db
from shared.core.auth import validate_current_token
from shared.core.schemas import Lookup, UserToken
from uuid import UUID
from fastapi.responses import StreamingResponse
from shared.utils.invoice_pdf import generate_invoice_pdf
from ...crud.financials.invoices_crud import get_invoice_detail

router = APIRouter(
    prefix="/api/invoices",
    tags=["invoices"],
    dependencies=[Depends(validate_current_token)]
)

# -----------------------------------------------------------------


@router.post("/detail", response_model=InvoiceOut)
def invoice_detail(
    params: InvoiceDetailRequest = Depends(),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_invoice_detail(
        db=db,
        auth_db=auth_db,
        org_id=current_user.org_id,
        invoice_id=params.invoice_id
    )


@router.get("/invoice-type", response_model=List[Lookup])
def invoice_type_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.invoice_type_lookup(db, current_user.org_id)


@router.get("/all", response_model=InvoicesResponse)
def get_invoices(
        params: InvoicesRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_invoices(db, current_user.org_id, params)


@router.get("/all-work-order-invoices", response_model=InvoicesResponse)
def get_work_order(
        params: InvoicesRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_work_order_invoices(db, current_user.org_id, params)


@router.get("/all-lease-charge-invoices", response_model=InvoicesResponse)
def get_work_order(
        params: InvoicesRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_lease_charge_invoices(db, current_user.org_id, params)


@router.get("/overview", response_model=InvoicesOverview)
def get_invoices_overview(
        params: InvoicesRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_invoices_overview(db, current_user.org_id, params)


@router.get("/payments", response_model=PaymentResponse)
def get_payments(
        params: InvoicesRequest = Depends(),
        db: Session = Depends(get_db),
        auth_db: Session = Depends(get_auth_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_payments(db=db, auth_db=auth_db, org_id=current_user.org_id, params=params)


@router.get("/customer-pending-charges")
def get_pending_charges_by_customer(
    space_id: UUID = Query(...),
    code: str = Query(...),
    invoice_id: UUID = Query(None),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_pending_charges_by_customer(db, space_id, code, invoice_id)

# ✅ FIXED: Match CRUD parameters


@router.post("/", response_model=InvoiceOut)
def create_invoice(
        invoice: str = Form(...),   # 👈 JSON string
        attachments: Optional[List[UploadFile]] = File(None),
        db: Session = Depends(get_db),
        auth_db: Session = Depends(get_auth_db),
        current_user: UserToken = Depends(validate_current_token)
):
    invoice_dict = json.loads(invoice)
    invoice_data = InvoiceCreate(**invoice_dict)
    return crud.create_invoice(
        db=db,
        auth_db=auth_db,
        org_id=current_user.org_id,
        request=invoice_data,
        attachments=attachments,
        current_user=current_user
    )

# ✅ FIXED: Match CRUD parameters


@router.put("/", response_model=InvoiceOut)
def update_invoice(
        invoice: str = Form(...),   # 👈 JSON string
        attachments: Optional[List[UploadFile]] = File(None),
        removed_attachment_ids: Optional[str] = Form(None),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    invoice_dict = json.loads(invoice)
    invoice_data = InvoiceUpdate(**invoice_dict)

    removed_ids = (
        json.loads(removed_attachment_ids)
        if removed_attachment_ids
        else []
    )

    return crud.update_invoice(db, invoice_data, attachments, removed_ids, current_user)

# ✅ FIXED: Convert UUID to string for CRUD
# ---------------- Delete Invoice (Soft Delete) ----------------


@router.delete("/{invoice_id}")
def delete_invoice_soft(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.delete_invoice_soft(db, invoice_id, current_user.org_id)


@router.get("/invoice-totals", response_model=InvoiceTotalsResponse)
def get_invoice_totals(
    params: InvoiceTotalsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.calculate_invoice_totals(
        db=db,
        params=params
    )


@router.get("/payement-method", response_model=List[Lookup])
def invoice_payement_method_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.invoice_payement_method_lookup(db, current_user.org_id)


@router.get("/{invoice_id}/download")
def download_invoice_pdf(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    # 1️⃣ Fetch invoice data FIRST (DB used here)
    invoice = get_invoice_detail(
        db=db,
        auth_db=auth_db,
        org_id=current_user.org_id,
        invoice_id=invoice_id
    )

    # 2️⃣ Generate PDF in memory (NO DB here)
    pdf_buffer = generate_invoice_pdf(invoice)

    # 3️⃣ 🔥 VERY IMPORTANT: CLOSE DB BEFORE STREAMING
    # db.close()

    print(type(pdf_buffer))
    pdf_buffer.seek(0)
    # 4️⃣ Stream PDF safely
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Invoice_{invoice.invoice_no}.pdf"'
        }
    )


@router.post("/save-invoice-payment", response_model=None)
def save_invoice_payment_detail(
    payload: PaymentCreateWithInvoice,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.save_invoice_payment_detail(db, payload, current_user)


@router.get("/preview-number")
def preview_invoice_number(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    invoice_no = crud.generate_invoice_number(db, current_user.org_id)
    return {"invoice_no": invoice_no}


@router.post("/add-payment", response_model=None)
def add_payment(
    payload: AdvancePaymentCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Record a payment against a bill."""
    return crud.add_payment_detail(
        db=db,
        payload=payload,
        current_user=current_user
    )


@router.get("/customer-advance-payments", response_model=AdvancePaymentResponse)
def get_advance_payments(
        params: InvoicesRequest = Depends(),
        db: Session = Depends(get_db),
        auth_db: Session = Depends(get_auth_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_advance_payments(db=db, auth_db=auth_db, org_id=current_user.org_id, params=params)
