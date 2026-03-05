from datetime import date
import json
import os
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from facility_service.app.utils.invoice_generator import auto_generate_monthly_invoices
from shared.helpers.json_response_helper import success_response
from ...crud.financials import invoices_crud as crud
from ...schemas.financials.invoices_schemas import AdvancePaymentCreate, AdvancePaymentOut, AdvancePaymentResponse, AutoInvoiceResponse, InvoiceCreate, InvoiceDetailRequest, InvoiceOut, InvoiceTotalsRequest, InvoiceTotalsResponse, InvoiceUpdate, InvoicesOverview, InvoicesRequest, InvoicesResponse, PaymentCreateWithInvoice, PaymentOut, PaymentResponse
from shared.core.database import get_auth_db, get_facility_db as get_db
from shared.core.auth import validate_current_token
from shared.core.schemas import Lookup, UserToken
from uuid import UUID
from fastapi.responses import FileResponse, StreamingResponse
from facility_service.app.utils.invoice_pdf import generate_invoice_pdf
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
    return crud.get_payments(
        db=db,
        auth_db=auth_db,
        org_id=current_user.org_id,
        current_user=current_user,
        params=params
    )


@router.post("/payments", response_model=List[PaymentOut])
def get_payments(
        params: InvoicesRequest = Depends(),
        db: Session = Depends(get_db),
        auth_db: Session = Depends(get_auth_db),
        current_user: UserToken = Depends(validate_current_token)):
    payment_response = crud.get_payments(
        db=db,
        auth_db=auth_db,
        org_id=current_user.org_id,
        current_user=current_user,
        params=params
    )
    return payment_response.payments


@router.get("/payment-history/{invoice_id}", response_model=List[PaymentOut])
def invoice_payment_history(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_payment_history(
        db=db,
        invoice_id=invoice_id
    )


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


@router.post("/create", response_model=InvoiceOut)
async def create_invoice(
        invoice: str = Form(...),   # 👈 JSON string
        attachments: Optional[List[UploadFile]] = File(None),
        db: Session = Depends(get_db),
        auth_db: Session = Depends(get_auth_db),
        current_user: UserToken = Depends(validate_current_token)
):
    invoice_dict = json.loads(invoice)
    invoice_data = InvoiceCreate(**invoice_dict)
    return await crud.create_invoice(
        db=db,
        org_id=current_user.org_id,
        request=invoice_data,
        attachments=attachments,
        current_user=current_user
    )

# ✅ FIXED: Match CRUD parameters


@router.post("/update", response_model=InvoiceOut)
async def update_invoice(
        invoice: str = Form(...),
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

    return await crud.update_invoice(db, invoice_data, attachments, removed_ids, current_user)

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

    file_path, filename = crud.download_invoice_pdf(
        db, invoice_id, current_user)

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail="Invoice PDF not found"
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=filename
    )


@router.get("/payment-receipt/{payment_id:uuid}/download")
def download_payment_recipt_pdf(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):

    file_path = crud.download_payment_recipt_pdf(
        db, payment_id, current_user)

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail="Invoice PDF not found"
        )

    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=os.path.basename(file_path)
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


@router.post("/auto-generate", response_model=AutoInvoiceResponse)
def auto_generate_lease_charges_endpoint(
    date: date = Query(
        ..., description="Any date in the month to generate lease charges for"),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return auto_generate_monthly_invoices(
        db=db,
        org_id=current_user.org_id,
        target_date=date,
        current_user=current_user
    )
