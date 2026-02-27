import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session
from uuid import UUID

from facility_service.app.schemas.financials.invoices_schemas import InvoicesRequest, PaymentResponse
# from shared.helpers.json_response_helper import success_response
from ...crud.financials import bills_crud as crud
from ...schemas.financials.bills_schemas import (
    BillCreate, BillOut, BillUpdate, BillsOverview,
    BillsRequest, BillsResponse, BillPaymentCreate, BillPaymentOut
)
from shared.core.database import get_auth_db, get_facility_db as get_db
from shared.core.auth import validate_current_token
from shared.core.schemas import UserToken

router = APIRouter(
    prefix="/api/bills",
    tags=["bills"],
    dependencies=[Depends(validate_current_token)]
)


@router.post("/create", response_model=BillOut)
async def create_bill(
    bill: str = Form(...),   # 👈 JSON string
    attachments: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    bill_dict = json.loads(bill)
    bill_data = BillCreate(**bill_dict)
    return await crud.create_bill(
        db=db,
        org_id=current_user.org_id,
        request=bill_data,
        attachments=attachments,
        current_user=current_user
    )


@router.get("/all", response_model=BillsResponse)
def get_bills(
    params: BillsRequest = Depends(),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Fetch all bills for the data table."""
    return crud.get_bills(
        db=db,
        auth_db=auth_db,
        org_id=current_user.org_id,
        params=params
    )


@router.get("/overview", response_model=BillsOverview)
def get_bills_overview(
    params: BillsRequest = Depends(),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Fetch aggregated data for the top 4 summary cards."""
    return crud.get_bills_overview(
        db=db,
        auth_db=auth_db,
        org_id=current_user.org_id,
        params=params
    )


@router.get("/{bill_id:uuid}", response_model=BillOut)
def get_bill_detail(
    bill_id: UUID,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Fetch details for a single bill."""
    return crud.get_bill_detail(
        db=db,
        auth_db=auth_db,
        org_id=current_user.org_id,
        bill_id=bill_id
    )


@router.post("/update", response_model=BillOut)
async def update_bill(
    bill: str = Form(...),
    attachments: Optional[List[UploadFile]] = File(None),
    removed_attachment_ids: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    bill_dict = json.loads(bill)
    bill_data = BillUpdate(**bill_dict)

    removed_ids = (
        json.loads(removed_attachment_ids)
        if removed_attachment_ids
        else []
    )

    """Update an existing bill."""
    return await crud.update_bill(
        db=db,
        request=bill_data,
        attachments=attachments,
        removed_attachment_ids=removed_ids,
        current_user=current_user
    )


@router.delete("/{bill_id:uuid}")
def delete_bill(
    bill_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Soft delete a bill."""
    return crud.delete_bill(
        db=db,
        bill_id=bill_id,
        org_id=current_user.org_id
    )

# Payments


@router.post("/save-payment", response_model=None)
def save_bill_payment(
    payload: BillPaymentCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Record a payment against a bill."""
    return crud.save_bill_payment(
        db=db,
        payload=payload,
        current_user=current_user
    )


@router.get("/workorder-vendor-lookup")
def workorder_vendor_lookup(
    space_id: UUID = Query(...),
    db: Session = Depends(get_db)
):
    return crud.workorder_vendor_lookup(db, space_id)


@router.get("/pending-workorder-lookup")
def pending_workorder_for_vendor_lookup(
    space_id: UUID = Query(...),
    vendor_id: UUID = Query(...),
    bill_id: UUID = Query(None),
    db: Session = Depends(get_db)
):
    return crud.get_pending_work_orders_for_vendor(db, space_id, vendor_id, bill_id)


@router.get("/preview-number")
def preview_bill_number(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Generate the next sequential bill number."""
    bill_no = crud.generate_bill_number(db, current_user.org_id)
    return {"bill_no": bill_no}


@router.get("/payments", response_model=PaymentResponse)
def get_payments(
        params: InvoicesRequest = Depends(),
        db: Session = Depends(get_db),
        auth_db: Session = Depends(get_auth_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_payments(db=db, auth_db=auth_db, org_id=current_user.org_id, params=params)
