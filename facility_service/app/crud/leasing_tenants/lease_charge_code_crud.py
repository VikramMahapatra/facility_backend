from typing import List, Optional
from uuid import UUID
from sqlalchemy import func
from sqlalchemy.orm import Session

from shared.helpers.json_response_helper import error_response

from ...models.leasing_tenants.lease_charge_code import LeaseChargeCode
from ...schemas.leasing_tenants.lease_charge_code_schemas import LeaseChargeCodeCreate, LeaseChargeCodeUpdate



def create_lease_charge_code(db: Session, lease_charge_code: LeaseChargeCodeCreate, org_id: UUID) -> LeaseChargeCode:
    existing = db.query(LeaseChargeCode).filter(
        LeaseChargeCode.org_id == org_id,
        LeaseChargeCode.is_deleted == False,
        func.lower(LeaseChargeCode.code) == func.lower(lease_charge_code.code)
    ).first()
    
    if existing:
        return error_response(
            message=f"Lease charge code '{lease_charge_code.code}' already exists"
        )
    data = lease_charge_code.model_dump()
    data["org_id"] = org_id
    db_lease_charge_code = LeaseChargeCode(**data)
    db.add(db_lease_charge_code)
    db.commit()
    db.refresh(db_lease_charge_code)
    return db_lease_charge_code



def update_lease_charge_code(db: Session, charge_code_id: UUID, org_id: UUID, charge_code_update: LeaseChargeCodeUpdate) -> Optional[LeaseChargeCode]:  
    db_charge_code = db.query(LeaseChargeCode).filter(
        LeaseChargeCode.id == charge_code_id,
        LeaseChargeCode.org_id == org_id,
        LeaseChargeCode.is_deleted == False
    ).first()
    
    if not db_charge_code:
        return None
    
    update_data = charge_code_update.model_dump(exclude_unset=True)
    if 'code' in update_data and update_data['code'].lower() != db_charge_code.code.lower():
        existing = db.query(LeaseChargeCode).filter(
            LeaseChargeCode.org_id == org_id,
            LeaseChargeCode.id != charge_code_id,
            LeaseChargeCode.is_deleted == False,
            func.lower(LeaseChargeCode.code) == func.lower(update_data['code'])
        ).first()
        
        if existing:
            return error_response(
            message=f"Lease charge code '{update_data['code']}' already exists"
        )
    
    for key, value in update_data.items():
        setattr(db_charge_code, key, value)
    
    db.commit()
    db.refresh(db_charge_code)
    return db_charge_code


def delete_lease_charge_code(db: Session, charge_code_id: UUID, org_id: UUID) -> bool:
    db_charge_code = db.query(LeaseChargeCode).filter(
        LeaseChargeCode.id == charge_code_id,
        LeaseChargeCode.org_id == org_id,
        LeaseChargeCode.is_deleted == False
    ).first()
    
    if not db_charge_code:
        return False
    db_charge_code.is_deleted = True
    db.commit()
    return True

def get_all_lease_codes(db: Session, org_id: UUID, search: Optional[str] = None) -> List[LeaseChargeCode]:
    query = db.query(LeaseChargeCode).filter(
        LeaseChargeCode.org_id == org_id,
        LeaseChargeCode.is_deleted == False
    )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(LeaseChargeCode.code.ilike(search_term))
        
    query = query.order_by(LeaseChargeCode.updated_at.desc())
    return query.all()