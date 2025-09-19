# app/crud/contracts.py
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.contracts import Contract
from ..schemas.contracts_schemas import ContractCreate, ContractUpdate

def get_contracts(db: Session, skip: int = 0, limit: int = 100) -> List[Contract]:
    return db.query(Contract).offset(skip).limit(limit).all()

def get_contract_by_id(db: Session, contract_id: str) -> Optional[Contract]:
    return db.query(Contract).filter(Contract.id == contract_id).first()

def create_contract(db: Session, contract: ContractCreate) -> Contract:
    db_contract = Contract(id=str(uuid.uuid4()), **contract.dict())
    db.add(db_contract)
    db.commit()
    db.refresh(db_contract)
    return db_contract

def update_contract(db: Session, contract_id: str, contract: ContractUpdate) -> Optional[Contract]:
    db_contract = get_contract_by_id(db, contract_id)
    if not db_contract:
        return None
    for k, v in contract.dict(exclude_unset=True).items():
        setattr(db_contract, k, v)
    db.commit()
    db.refresh(db_contract)
    return db_contract

def delete_contract(db: Session, contract_id: str) -> Optional[Contract]:
    db_contract = get_contract_by_id(db, contract_id)
    if not db_contract:
        return None
    db.delete(db_contract)
    db.commit()
    return db_contract
