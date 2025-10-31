from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from shared.app_status_code import AppStatusCode
from shared.json_response_helper import error_response, success_response
from ...crud.financials import tax_codes_crud as crud
from ...schemas.financials.tax_codes_schemas import (
    TaxCodeCreate, TaxCodeOut, TaxCodeUpdate, TaxOverview, TaxCodesRequest, TaxCodesResponse, TaxReturnResponse
)
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token #for dependicies 
from shared.schemas import Lookup, UserToken
from uuid import UUID

router = APIRouter(
    prefix="/api/tax-codes",
    tags=["tax-codes"],
    dependencies=[Depends(validate_current_token)]
)

#-----------------------------------------------------------------
@router.get("/all", response_model=TaxCodesResponse)
def get_tax_codes(
    params : TaxCodesRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)) :
    return crud.get_tax_codes(db, current_user.org_id, params)

@router.get("/overview", response_model=TaxOverview)
def get_tax_overview(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)) :
    return crud.get_tax_overview(db, current_user.org_id)

@router.get("/returns", response_model=TaxReturnResponse)
def get_tax_returns(
    params : TaxCodesRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)) :
    return crud.get_tax_returns(db, current_user.org_id, params)


@router.post("/", response_model=None)
def create_tax_code(
    tax: TaxCodeCreate, 
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)):
    
    tax.org_id = current_user.org_id
    result = crud.create_tax_code(db, tax)
    
    # Check if result is an error response
    if hasattr(result, 'status_code') and result.status_code != "100":
        return result
    
    return success_response(
        data=result,
        message="Tax code created successfully"
    )


@router.put("/", response_model=None)
def update_tax_code(
    tax: TaxCodeUpdate, 
    db: Session = Depends(get_db)):
    
    result = crud.update_tax_code(db, tax)
    
    # Check if result is an error response
    if hasattr(result, 'status_code') and result.status_code != "100":
        return result
    
    if not result:
        return error_response(
            message="Tax code not found",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=404
        )
    
    return success_response(
        data=result,
        message="Tax code updated successfully"
    )


@router.delete("/{tax_code_id}", response_model=None)
def delete_tax_code(tax_code_id: str, db: Session = Depends(get_db)):
    db_tax = crud.delete_tax_code(db, tax_code_id)
    if not db_tax:
        raise HTTPException(status_code=404, detail="Tax code not found")
    return db_tax

