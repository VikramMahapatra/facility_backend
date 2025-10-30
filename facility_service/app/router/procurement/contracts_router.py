# app/routers/contracts.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.app_status_code import AppStatusCode
from shared.database import get_facility_db as get_db
from shared.json_response_helper import error_response, success_response
from shared.schemas import Lookup, UserToken
from ...schemas.procurement.contracts_schemas import ContractListResponse, ContractOut, ContractCreate, ContractOverviewResponse, ContractRequest, ContractUpdate
from ...crud.procurement import contracts_crud as crud
from shared.auth import validate_current_token
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
    current_user: UserToken = Depends(validate_current_token)
):
    # Assign org_id from current user
    contract.org_id = current_user.org_id
    result = crud.create_contract(db, contract)
    
    # Check if result is an error response
    if hasattr(result, 'status_code') and result.status_code != "100":
        return result
    
    return success_response(
        data=result,
        message="Contract created successfully"
    )


@router.put("/", response_model=None)
def update_contract_endpoint(
    contract: ContractUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    result = crud.update_contract(db, contract)
    
    # Check if result is an error response
    if hasattr(result, 'status_code') and result.status_code != "100":
        return result
    
    if not result:
        return error_response(
            message="Contract not found",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=404
        )
    
    return success_response(
        data={"message": "Contract updated successfully"},
        message="Contract updated successfully"
    )


@router.delete("/{contract_id}")
def delete_contract(
    contract_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    success = crud.delete_contract(db, contract_id, current_user.org_id)
    if not success:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    return success_response(
        data=None,
        message="Contract deleted successfully",
        status_code="200"  # Use the appropriate status code from AppStatusCode
    )

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