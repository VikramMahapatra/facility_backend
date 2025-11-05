from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from shared.json_response_helper import success_response
from ...crud.financials import invoices_crud as crud
from ...schemas.financials.invoices_schemas import InvoiceCreate, InvoiceOut, InvoiceUpdate, InvoicesOverview, InvoicesRequest, InvoicesResponse, PaymentOut, PaymentResponse
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token
from shared.schemas import Lookup, UserToken
from uuid import UUID

router = APIRouter(
    prefix="/api/invoices",
    tags=["invoices"],
    dependencies=[Depends(validate_current_token)]
)

#-----------------------------------------------------------------
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
    current_user: UserToken = Depends(validate_current_token)):
    return crud.get_payments(db, current_user.org_id, params)

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
    db_invoice = crud.update_invoice(db, invoice, current_user)
    if not db_invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return db_invoice

# ✅ FIXED: Convert UUID to string for CRUD
# ---------------- Delete Invoice (Soft Delete) ----------------
@router.delete("/{invoice_id}")
def delete_invoice_soft(
    invoice_id: str, 
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
): return  crud.delete_invoice_soft(db, invoice_id, current_user.org_id)