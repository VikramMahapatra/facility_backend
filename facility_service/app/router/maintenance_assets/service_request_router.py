from typing import Optional , List
from fastapi import APIRouter, Depends , Query ,HTTPException
from sqlalchemy.orm import Session

from shared.schemas import Lookup
from ...schemas.maintenance_assets.service_requests_schemas import (ServiceRequestCreate, ServiceRequestListResponse, ServiceRequestOut, ServiceRequestRequest, ServiceRequestUpdate ,ServiceRequestOverviewResponse)
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token, UserToken
from uuid import UUID
from ...crud.maintenance_assets import service_request_crud as crud

router = APIRouter(prefix="/api/service-requests", tags=["Service Requests"])

@router.get("/overview", response_model=ServiceRequestOverviewResponse)
def service_request_overview(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_service_request_overview(db, current_user.org_id)


# ---------------- List Service Requests ----------------
@router.get("/all", response_model=ServiceRequestListResponse)
def get_service_requests_endpoint(
    params: ServiceRequestRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_service_requests(db, current_user.org_id, params)



# ----------------- Update Service Request -----------------
@router.put("/", response_model=None)
def update_service_request_route(
    request_update: ServiceRequestUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    updated = crud.update_service_request(db, request_update, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Service Request not found")
    return {"message": "Service Request updated successfully"}


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
        user_id=current_user.user_id,   # requester_id always from token
        request=request
    )

# ---------------- Delete service request ----------------
@router.delete("/{request_id}")
def delete_service_request_route(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    success = crud.delete_service_request(db, request_id)
    if not success:
        raise HTTPException(status_code=404, detail="Service Request not found")
    return {"message": "Service Request deleted successfully"}

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
