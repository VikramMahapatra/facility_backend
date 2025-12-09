from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID

from shared.core.auth import validate_current_token
from shared.core.schemas import UserToken
from shared.core.database import get_facility_db as get_db

from ...schemas.leasing_tenants.lease_charge_code_schemas import LeaseChargeCodeCreate, LeaseChargeCodeOut, LeaseChargeCodeUpdate
from ...crud.leasing_tenants import lease_charge_code_crud as crud

router = APIRouter(prefix="/api/lease-charge-codes",tags=["lease-charge-codes"],dependencies=[Depends(validate_current_token)])


@router.get("/all", response_model=List[LeaseChargeCodeOut])
def get_all_lease_codes(db: Session = Depends(get_db)):
    return crud.get_all_lease_codes(db)


@router.post("/", response_model=LeaseChargeCodeOut)
def create_lease_charge_code(
    lease_charge_code: LeaseChargeCodeCreate, 
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)):
    return crud.create_lease_charge_code(db=db, lease_charge_code=lease_charge_code,org_id=current_user.org_id)

@router.put("/{charge_code_id}", response_model=LeaseChargeCodeOut)
def update_lease_charge_code(
    charge_code_id: UUID,
    charge_code_update: LeaseChargeCodeUpdate, 
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)):  
    return crud.update_lease_charge_code(db=db,charge_code_id=charge_code_id,org_id=current_user.org_id,charge_code_update=charge_code_update)


@router.delete("/{charge_code_id}")
def delete_lease_charge_code(
    charge_code_id: UUID, 
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)):  
    return crud.delete_lease_charge_code(db=db, charge_code_id=charge_code_id,org_id=current_user.org_id)