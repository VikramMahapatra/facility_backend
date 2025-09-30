from typing import Optional , List
from fastapi import APIRouter, Depends , Query ,HTTPException
from sqlalchemy.orm import Session
from ...schemas.maintenance_assets.service_request import ServiceRequestOverview ,ServiceRequestListResponse ,ServiceRequestCreate, ServiceRequestUpdate, ServiceRequestOut
from ...crud.maintenance_assets.service_request_crud import ( get_service_request_overview , search_service_requests,
    filter_service_requests_by_status,
    filter_service_requests_by_category ,
    create_service_request,
    get_service_request,
    get_all_service_requests,
    update_service_request,
    delete_service_request   
    )
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token, UserToken
from uuid import UUID


router = APIRouter(prefix="/service-requests", tags=["Service Requests"])

@router.get("/overview", response_model=ServiceRequestOverview)
def service_request_overview(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return get_service_request_overview(db, current_user.org_id)



# Search Service Requests
@router.get("/search_service_request", response_model=ServiceRequestListResponse)
def search_requests(
    query: Optional[str] = Query(None, description="Search text for description or requester"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    requests = search_service_requests(db, current_user.org_id, query)
    return {"requests": requests}

# Filter by Status (optional)
@router.get("/filter_by_status", response_model=ServiceRequestListResponse)
def filter_by_status(
    status: Optional[str] = Query(None, description="Status of the service request"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    requests = filter_service_requests_by_status(db, current_user.org_id, status)
    return {"requests": requests}

# Filter by Category (optional)
@router.get("/filter_by_category", response_model=ServiceRequestListResponse)
def filter_by_category(
    category: Optional[str] = Query(None, description="Category of service request"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    requests = filter_service_requests_by_category(db, current_user.org_id, category)
    return {"requests": requests}

#-----------------CRUD OPERTION-------------------------------------


# Create
@router.post("/", response_model=ServiceRequestOut)
def create_request(
    request: ServiceRequestCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return create_service_request(db, current_user.org_id, request)

# Read single
@router.get("/{request_id}", response_model=ServiceRequestOut)
def read_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    db_request = get_service_request(db, current_user.org_id, request_id)
    if not db_request:
        raise HTTPException(status_code=404, detail="Request not found")
    return db_request

# Read all
@router.get("/", response_model=ServiceRequestListResponse)
def read_all_requests(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    requests = get_all_service_requests(db, current_user.org_id)
    return {"requests": requests}

# Update
@router.put("/{request_id}", response_model=ServiceRequestOut)
def update_request(
    request_id: UUID,
    request_update: ServiceRequestUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    updated = update_service_request(db, current_user.org_id, request_id, request_update)
    if not updated:
        raise HTTPException(status_code=404, detail="Request not found")
    return updated

# Delete
@router.delete("/{request_id}")
def delete_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    success = delete_service_request(db, current_user.org_id, request_id)
    if not success:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"detail": "Request deleted successfully"}
