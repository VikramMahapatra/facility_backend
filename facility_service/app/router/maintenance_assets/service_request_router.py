from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from shared.json_response_helper import success_response
from shared.schemas import Lookup
from ...schemas.maintenance_assets.service_requests_schemas import (
    ServiceRequestCreate, ServiceRequestListResponse, ServiceRequestOut, ServiceRequestRequest, ServiceRequestUpdate, ServiceRequestOverviewResponse)
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token, UserToken
from uuid import UUID
from ...crud.maintenance_assets import service_request_crud as crud

router = APIRouter(prefix="/api/service-requests", tags=["Service Requests"])


@router.get("/overview", response_model=ServiceRequestOverviewResponse)
def service_request_overview(
    params: ServiceRequestRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_service_request_overview(db, current_user.org_id,params)


# ---------------- List Service Requests ----------------
@router.get("/all", response_model=ServiceRequestListResponse)
def get_service_requests_endpoint(
    params: ServiceRequestRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_service_requests(db, current_user.org_id, params)


@router.put("/", response_model=ServiceRequestOut)
def update_request_route(
    request: ServiceRequestUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    updated_request = crud.update_service_request(
        db=db,
        request_update=request,
        current_user=current_user
    )
    if not updated_request:
        raise HTTPException(status_code=404, detail="Service request not found")
    return updated_request


# ----------------- Create Service Request -----------------
@router.post("/", response_model=ServiceRequestOut)
def create_request_route(
    request: ServiceRequestCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.create_service_request(
        db=db,
        org_id=current_user.org_id,
        request=request,
        current_user=current_user  # Pass current_user to service function
    )

# ---------------- Delete Service Request (Soft Delete) ----------------
@router.delete("/{request_id}")
def delete_service_request_soft(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    success = crud.delete_service_request_soft(db, request_id, current_user.org_id)
    if not success:
        raise HTTPException(status_code=404, detail="Service Request not found")
    
    return success_response(
        data="deleted successfully",
        message="Service Request deleted successfully",
        status_code="200"
    )


@router.get("/service-request-lookup", response_model=List[Lookup])
def service_request_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.service_request_lookup(db, current_user.org_id)

# ----------------  Status Lookup ----------------


@router.get("/status-lookup", response_model=List[Lookup])
def service_request_status_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.service_request_status_lookup(db, current_user.org_id)


# ----------------  Category Lookup ----------------
@router.get("/category-lookup", response_model=List[Lookup])
def service_request_category_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.service_request_category_lookup(db, current_user.org_id)


# ----------------filter  Status Lookup ----------------
@router.get("/filter-status-lookup", response_model=List[Lookup])
def service_request_filter_status_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.service_request_filter_status_lookup(db, current_user.org_id)

# ----------------filter  Category Lookup ----------------


@router.get("/filter-category-lookup", response_model=List[Lookup])
def service_request_filter_category_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.service_request_filter_category_lookup(db, current_user.org_id)

# ----------------  requester_kind Lookup ----------------


@router.get("/requester-kind-lookup", response_model=List[Lookup])
def service_request_requester_kind_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.service_request_requester_kind_lookup(db, current_user.org_id)

# ----------------  channel Lookup ----------------


@router.get("/channel-lookup", response_model=List[Lookup])
def service_request_channel_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.service_request_channel_lookup(db, current_user.org_id)

# ----------------  priority Lookup ----------------


@router.get("/priority-lookup", response_model=List[Lookup])
def service_request_priority_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.service_request_priority_lookup(db, current_user.org_id)

# ----------------filter  workorder Lookup ----------------
@router.get("/filter-workorderid-lookup", response_model=List[Lookup])
def service_request_filter_workorder_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
   
    return crud.service_request_filter_workorder_lookup(db, current_user.org_id)
