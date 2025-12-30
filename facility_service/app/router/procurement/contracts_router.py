# app/routers/contracts.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.utils.app_status_code import AppStatusCode
from shared.core.database import get_facility_db as get_db
from shared.helpers.json_response_helper import error_response, success_response
from shared.core.schemas import Lookup, UserToken
from ...schemas.procurement.contracts_schemas import ContractListResponse, ContractOut, ContractCreate, ContractOverviewResponse, ContractRequest, ContractUpdate
from ...crud.procurement import contracts_crud as crud
from shared.core.auth import allow_admin, validate_current_token
from uuid import UUID


router = APIRouter(prefix="/api/contracts",
                   tags=["contracts"], dependencies=[Depends(validate_current_token)])

# ---------------- List all contracts ----------------


@router.get("/all", response_model=ContractListResponse)
def get_contracts(
    params: ContractRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_contracts(db, current_user.org_id, params)

# -----overview----


@router.get("/overview", response_model=ContractOverviewResponse)
def overview(
    params: ContractRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_contracts_overview(db, current_user.org_id, params)


# --------- Create Contract ---------
@router.post("/", response_model=ContractOut)
def create_contract(
    contract: ContractCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
     _ : UserToken = Depends(allow_admin)
):
    # Assign org_id from current user
    contract.org_id = current_user.org_id
    return crud.create_contract(db, contract)


@router.put("/", response_model=None)
def update_contract_endpoint(
    contract: ContractUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
     _ : UserToken = Depends(allow_admin)
):
    return crud.update_contract(db, contract)


@router.delete("/{contract_id}")
def delete_contract(
    contract_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):

    return crud.delete_contract(db, contract_id, current_user.org_id)
# ----------status_lookup-------------


@router.get("/filter-status-lookup", response_model=List[Lookup])
def contracts_filter_status_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.contracts_filter_status_lookup(db, current_user.org_id)


@router.get("/status-lookup", response_model=List[Lookup])
def contracts_status_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.contracts_status_lookup(db, current_user.org_id)

# ----------filter type_lookup-------------


@router.get("/filter-type-lookup", response_model=List[Lookup])
def contracts_type_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.contracts_filter_type_lookup(db, current_user.org_id)

# ----------type_lookup-------------


@router.get("/type-lookup", response_model=List[Lookup])
def contracts_type_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.contracts_type_lookup(db, current_user.org_id)
