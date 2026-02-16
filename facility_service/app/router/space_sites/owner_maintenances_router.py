from datetime import date
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from shared.core.database import get_auth_db, get_facility_db as get_db
from ...schemas.space_sites.owner_maintenances_schemas import OwnerMaintenanceAmountRequest, OwnerMaintenanceBySpaceRequest, OwnerMaintenanceBySpaceResponse, OwnerMaintenanceCreate, OwnerMaintenanceDetailResponse, OwnerMaintenanceListResponse, OwnerMaintenanceRequest, OwnerMaintenanceUpdate
from ...crud.space_sites import owner_maintenances_crud as crud
from shared.core.auth import validate_current_token
from shared.core.schemas import Lookup, UserToken


router = APIRouter(
    prefix="/api/owner-maintenances",
    tags=["owner-maintenances"],
    dependencies=[Depends(validate_current_token)]
)


@router.post("/auto-generate-maintenance", response_model=OwnerMaintenanceListResponse)
def auto_generate_maintenance(
    date: date = Query(...,
                       description="Any date of the month to generate maintenance for"),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.auto_generate_owner_maintenance(
        db=db,
        input_date=date,
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


@router.get("/status-lookup", response_model=List[Lookup])
def owner_maintenances_status_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.owner_maintenances_status_lookup(db, current_user.org_id)


@router.get("/space-owner-lookup", response_model=List[Lookup])
def spaces_with_owner_lookup(
    site_id: Optional[str] = Query(None),
    building_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token),
):
    return crud.get_spaces_with_owner_lookup(
        db=db,
        auth_db=auth_db,
        site_id=site_id,
        building_id=building_id,
        org_id=current_user.org_id
    )


@router.get("/by-space", response_model=OwnerMaintenanceBySpaceResponse)
def get_owner_maintenances_by_space(
    params: OwnerMaintenanceBySpaceRequest = Depends(),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Get all owner maintenance records for a specific space"""
    return crud.get_owner_maintenances_by_space(
        db=db,
        auth_db=auth_db,
        params=params,
        user=current_user
    )


@router.post("/", response_model=OwnerMaintenanceDetailResponse)
def create_owner_maintenance(
    maintenance: OwnerMaintenanceCreate,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Create a new owner maintenance record"""
    return crud.create_owner_maintenance(db=db, auth_db=auth_db, maintenance=maintenance, user=current_user)


@router.put("/", response_model=OwnerMaintenanceDetailResponse)
def update_owner_maintenance(
    maintenance: OwnerMaintenanceUpdate,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Update an existing owner maintenance record"""
    return crud.update_owner_maintenance(db=db, auth_db=auth_db, maintenance=maintenance, user=current_user)


@router.get("/{maintenance_id}", response_model=OwnerMaintenanceDetailResponse)
def get_owner_maintenance_by_id(
    maintenance_id: str,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Get single owner maintenance record by ID"""
    return crud.get_owner_maintenance_by_id(db=db, auth_db=auth_db, maintenance_id=maintenance_id)


@router.delete("/{maintenance_id}", response_model=OwnerMaintenanceDetailResponse)
def delete_owner_maintenance(
    maintenance_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """Soft delete an owner maintenance record"""
    return crud.delete_owner_maintenance(db=db, maintenance_id=maintenance_id)


@router.post("/calculated-maintenance-amount", response_model=dict)
def get_calculated_maintenance_amount(
    params: OwnerMaintenanceAmountRequest,
    db: Session = Depends(get_db)
) -> dict:
    """Calculated maintenance amount for a space based on active owner maintenances"""
    return crud.get_calculated_maintenance_amount(
        db=db,
        space_id=params.space_id,
        start_date=params.start_date,
        end_date=params.end_date)
