from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from shared.core.database import get_auth_db, get_facility_db as get_db
from ...schemas.space_sites.owner_maintenances_schemas import OwnerMaintenanceCreate, OwnerMaintenanceDetailResponse, OwnerMaintenanceListResponse, OwnerMaintenanceRequest, OwnerMaintenanceUpdate
from ...crud.space_sites import owner_maintenances_crud as crud
from shared.core.auth import   validate_current_token  
from shared.core.schemas import Lookup, UserToken


router = APIRouter(
    prefix="/api/owner-maintenances",
    tags=["owner-maintenances"],
    dependencies=[Depends(validate_current_token)]
)


@router.get("/all", response_model=OwnerMaintenanceListResponse)
def get_all_owner_maintenances(
    params: OwnerMaintenanceRequest = Depends(),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Get all owner maintenance records with site filter"""
    return crud.get_owner_maintenances(db=db, auth_db=auth_db, user=current_user, params=params)


@router.get("/{maintenance_id}", response_model=OwnerMaintenanceDetailResponse)
def get_owner_maintenance_by_id(
    maintenance_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Get single owner maintenance record by ID"""
    return crud.get_owner_maintenance_by_id(db=db, maintenance_id=maintenance_id)

@router.post("/", response_model=OwnerMaintenanceDetailResponse)
def create_owner_maintenance(
    maintenance: OwnerMaintenanceCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Create a new owner maintenance record"""
    return crud.create_owner_maintenance(db=db, maintenance=maintenance, user=current_user)
    


@router.put("/", response_model=OwnerMaintenanceDetailResponse)
def update_owner_maintenance(
    maintenance: OwnerMaintenanceUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Update an existing owner maintenance record"""
    return crud.update_owner_maintenance(db=db, maintenance=maintenance)
    


@router.delete("/{maintenance_id}", response_model=OwnerMaintenanceDetailResponse)
def delete_owner_maintenance(
    maintenance_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Soft delete an owner maintenance record"""
    return crud.delete_owner_maintenance(db=db, maintenance_id=maintenance_id)
  