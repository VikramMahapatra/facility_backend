from datetime import date
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ...schemas.leasing_tenants.lease_charges_schemas import AutoLeaseChargeResponse, LeaseChargeCreate, LeaseChargeListResponse, LeaseChargeRequest, LeaseChargeUpdate, LeaseChargesOverview, LeaseRentAmountResponse, RentAmountRequest
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


@router.post("/auto-generate", response_model=AutoLeaseChargeResponse)
def auto_generate_lease_charges_endpoint(
    target_date: date = Query(
        ..., description="Any date in the month to generate lease charges for"),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.auto_generate_lease_rent_charges(
        db=db,
        auth_db=auth_db,
        input_date=target_date,
        current_user=current_user
    )


@router.get("/all", response_model=LeaseChargeListResponse)
def get_lease_charges(
        params: LeaseChargeRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_lease_charges(db=db, user=current_user, params=params)


@router.get("/overview", response_model=LeaseChargesOverview)
def get_lease_charges_overview(
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_lease_charges_overview(db=db, user=current_user)


@router.post("/", response_model=None)
def create_lease_charge(
        data: LeaseChargeCreate,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token),
        _: UserToken = Depends(allow_admin)
):
    return crud.create_lease_charge(db, data, current_user.user_id)


@router.put("/", response_model=None)
def update_lease_charge(
    data: LeaseChargeUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
    _: UserToken = Depends(allow_admin)

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


@router.get("/tax-code-lookup", response_model=List[Lookup])
def get_tax_code_lookup(
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.tax_code_lookup(db, current_user.org_id)


@router.post("/lease-rent", response_model=LeaseRentAmountResponse)
def get_lease_rent_amount(
    params: RentAmountRequest,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get lease rent amount by lease ID
    Used to auto-fill amount when user selects "Rent" charge code
    """
    result = crud.get_lease_rent_amount(
        db, params.lease_id, params.tax_code_id, params.start_date, params.end_date)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result
