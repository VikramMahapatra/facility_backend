# app/routers/contracts.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from ...schemas.procurement.contracts_schemas import ContractOut, ContractCreate, ContractUpdate
from ...crud.procurement import contracts_crud as crud
from shared.auth import validate_current_token

router = APIRouter(prefix="/api/contracts", tags=["contracts"],dependencies=[Depends(validate_current_token)])

@router.get("/", response_model=List[ContractOut])
def read_contracts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_contracts(db, skip=skip, limit=limit)

@router.get("/{contract_id}", response_model=ContractOut)
def read_contract(contract_id: str, db: Session = Depends(get_db)):
    db_contract = crud.get_contract_by_id(db, contract_id)
    if not db_contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return db_contract

@router.post("/", response_model=ContractOut)
def create_contract(contract: ContractCreate, db: Session = Depends(get_db)):
    return crud.create_contract(db, contract)

@router.put("/{contract_id}", response_model=ContractOut)
def update_contract(contract_id: str, contract: ContractUpdate, db: Session = Depends(get_db)):
    db_contract = crud.update_contract(db, contract_id, contract)
    if not db_contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return db_contract

@router.delete("/{contract_id}", response_model=ContractOut)
def delete_contract(contract_id: str, db: Session = Depends(get_db)):
    db_contract = crud.delete_contract(db, contract_id)
    if not db_contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return db_contract
