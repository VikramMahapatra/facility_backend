import json

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
from shared.core.database import get_facility_db as get_db
from ...schemas.leasing_tenants.leases_schemas import (
    RejectTerminationRequest, LeaseDetailOut, LeaseDetailRequest, LeaseListResponse, LeaseLookup,
    LeaseOut, LeaseCreate, LeaseOverview, LeasePaymentTermCreate, LeasePaymentTermRequest, LeaseRequest, LeaseUpdate, LeaseStatusResponse, LeaseSpaceResponse, TenantSpaceDetailOut, TerminationListRequest, TerminationRequestCreate,
)
from ...crud.leasing_tenants import leases_crud as crud
from shared.core.auth import allow_admin, validate_current_token
from shared.core.schemas import Lookup, UserToken
from typing import List, Optional
from uuid import UUID

router = APIRouter(
    prefix="/api/leases",
    tags=["leases"],
    dependencies=[Depends(validate_current_token)]
)


@router.get("/all", response_model=LeaseListResponse)
def get_leases(
    params: LeaseRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_list(db=db, user=current_user, params=params)


@router.get("/overview", response_model=LeaseOverview)
def get_lease_overview(
    params: LeaseRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_overview(db=db, user=current_user, params=params)


@router.post("/", response_model=None)
def create_lease(
    payload: str = Form(...),
    attachments: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
    _: UserToken = Depends(allow_admin)

):
    lease_dict = json.loads(payload)
    lease_data = LeaseCreate(**lease_dict)
    lease_data.org_id = current_user.org_id
    return crud.create(db, lease_data, attachments)


@router.put("/", response_model=None)
def update_lease(
    payload: str = Form(...),
    attachments: Optional[List[UploadFile]] = File(None),
    removed_attachment_ids: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
    _: UserToken = Depends(allow_admin)
):
    lease_dict = json.loads(payload)
    lease_data = LeaseUpdate(**lease_dict)

    removed_ids = (
        json.loads(removed_attachment_ids)
        if removed_attachment_ids
        else []
    )

    return crud.update(db, lease_data, removed_ids)


@router.delete("/{lease_id}", response_model=None)
def delete_lease(
    lease_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.delete(db, lease_id, current_user.org_id)


@router.get("/lease-lookup", response_model=List[LeaseLookup])
def lease_lookup(
    site_id: Optional[str] = Query(None),
    building_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.lease_lookup(current_user.org_id, site_id, building_id,  db)


@router.get("/default-payer-lookup", response_model=List[Lookup])
def lease_default_payer_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.lease_default_payer_lookup(current_user.org_id, db)


@router.get("/status-lookup", response_model=List[Lookup])
def lease_status_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.lease_status_lookup(current_user.org_id, db)


@router.get("/lease-frequency", response_model=List[Lookup])
def lease_frequency_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.lease_frequency_lookup(current_user.org_id, db)


@router.get("/tenant-lookup", response_model=List[Lookup])
def lease_tenant_lookup(
    site_id: Optional[str] = Query(None),
    space_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.lease_tenant_lookup(current_user.org_id, site_id, space_id, db)


@router.post("/detail", response_model=LeaseDetailOut)
def lease_detail(
    params: LeaseDetailRequest,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):

    return crud.get_lease_detail(
        db=db,
        org_id=current_user.org_id,
        lease_id=params.lease_id
    )


@router.get("/tenant-lease/detail", response_model=TenantSpaceDetailOut)
def tenant_space_detail(
    tenant_id: UUID = Query(...),
    space_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_tenant_space_detail(
        db=db,
        org_id=current_user.org_id,
        tenant_id=tenant_id,
        space_id=space_id
    )


@router.post("/create-lease-payment-term")
def create_lease_payment_term(
    payload: LeasePaymentTermCreate = Body(...),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.create_payment_term(db, payload)


@router.get("/get-payment-terms")
def get_lease_payment_terms(
    params: LeasePaymentTermRequest = Depends(),
    db: Session = Depends(get_db)
):
    return crud.get_lease_payment_terms(db=db, params=params)


@router.get("/termination-requests")
def get_termination_requests(
    params: TerminationListRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_termination_requests(db, current_user.org_id, params)


@router.post("/termination-requests/create")
def create_termination_request(
    payload: TerminationRequestCreate = Body(...),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.create_termination_request(db, current_user.user_id, payload)


@router.post("/termination-requests/${request_id:uuid}/approve")
def approve_termination_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.approve_termination(db, request_id, current_user.user_id)


@router.post("/termination-requests/${request_id:uuid}/reject")
def reject_termination(
    request_id: UUID,
    params: RejectTerminationRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    params.request_id = request_id
    return crud.reject_termination(db, current_user.user_id, params)
