from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from shared.helpers.json_response_helper import success_response
from ...crud.financials import invoices_crud as crud
from ...schemas.financials.invoices_schemas import InvoiceCreate, InvoiceDetailRequest, InvoiceOut, InvoicePaymentHistoryOut, InvoiceTotalsRequest, InvoiceTotalsResponse, InvoiceUpdate, InvoicesOverview, InvoicesRequest, InvoicesResponse, PaymentOut, PaymentResponse
from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token
from shared.core.schemas import Lookup, UserToken
from uuid import UUID

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
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_invoice_detail(
        db=db,
        org_id=current_user.org_id,
        invoice_id=params.invoice_id
    )


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
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_payments(db, current_user.org_id, params)


@router.get("/entity-lookup", response_model=List[Lookup]) 
def get_invoice_lookup(
    site_id: UUID = Query(...),
    billable_item_type: str = Query(...),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_invoice_entities_lookup(db, current_user.org_id, site_id, billable_item_type)

# ✅ FIXED: Match CRUD parameters


@router.post("/", response_model=InvoiceOut)
def create_invoice(
        invoice: InvoiceCreate,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.create_invoice(
        db=db,
        org_id=current_user.org_id,
        request=invoice,
        current_user=current_user
    )

# ✅ FIXED: Match CRUD parameters


@router.put("/", response_model=InvoiceOut)
def update_invoice(
        invoice: InvoiceUpdate,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.update_invoice(db, invoice, current_user)

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


@router.get("/payment-history/{invoice_id}",response_model=InvoicePaymentHistoryOut)
def invoice_payment_history(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_invoice_payment_history(
        db=db,
        org_id=current_user.org_id,
        invoice_id=invoice_id
    )
