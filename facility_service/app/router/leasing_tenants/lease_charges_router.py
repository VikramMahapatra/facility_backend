from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ...schemas.leasing_tenants.lease_charges_schemas import LeaseChargeCreate, LeaseChargeListResponse, LeaseChargeRequest, LeaseChargeUpdate, LeaseChargesOverview
from ...crud.leasing_tenants import lease_charges_crud as crud
from shared.core.database import get_facility_db as get_db
from shared.core.auth import allow_admin, validate_current_token  # for dependicies
from shared.core.schemas import Lookup, UserToken
from uuid import UUID

router = APIRouter(
    prefix="/api/lease-charges",
    tags=["lease-charges"],
    dependencies=[Depends(validate_current_token)]
)

# -----------------------------------------------------------------


@router.get("/all", response_model=LeaseChargeListResponse)
def get_lease_charges(
        params: LeaseChargeRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_lease_charges(db, current_user, params)


@router.get("/overview", response_model=LeaseChargesOverview)
def get_lease_charges_overview(
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_lease_charges_overview(db, current_user.org_id)


@router.post("/", response_model=None)
def create_lease_charge(
        data: LeaseChargeCreate,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token),
        _ : UserToken = Depends(allow_admin)
):        
    return crud.create_lease_charge(db, data)


@router.put("/", response_model=None)
def update_lease_charge(
    data: LeaseChargeUpdate, 
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
    _ : UserToken = Depends(allow_admin)
                        
):                        
    return crud.update_lease_charge(db, data)


@router.delete("/{id}", response_model=None)
def delete_lease_charge(
    id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
): return crud.delete_lease_charge(db, id, current_user.org_id)


@router.get("/month-lookup", response_model=List[Lookup])
def get_month_lookup(
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.lease_charge_month_lookup(db, current_user.org_id)


@router.get("/charge-code-lookup", response_model=List[Lookup])
def get_charge_code_lookup(
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.lease_charge_code_lookup(db, current_user.org_id)
