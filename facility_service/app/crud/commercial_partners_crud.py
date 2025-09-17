# app/crud/commercial_partners.py
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.commercial_partners import CommercialPartner
from app.schemas.commercial_partners_schemas import CommercialPartnerCreate, CommercialPartnerUpdate

def get_commercial_partners(db: Session, skip: int = 0, limit: int = 100) -> List[CommercialPartner]:
    return db.query(CommercialPartner).offset(skip).limit(limit).all()

def get_commercial_partner_by_id(db: Session, partner_id: str) -> Optional[CommercialPartner]:
    return db.query(CommercialPartner).filter(CommercialPartner.id == partner_id).first()

def create_commercial_partner(db: Session, partner: CommercialPartnerCreate) -> CommercialPartner:
    db_partner = CommercialPartner(id=str(uuid.uuid4()), **partner.dict())
    db.add(db_partner)
    db.commit()
    db.refresh(db_partner)
    return db_partner

def update_commercial_partner(db: Session, partner_id: str, partner: CommercialPartnerUpdate) -> Optional[CommercialPartner]:
    db_partner = get_commercial_partner_by_id(db, partner_id)
    if not db_partner:
        return None
    for k, v in partner.dict(exclude_unset=True).items():
        setattr(db_partner, k, v)
    db.commit()
    db.refresh(db_partner)
    return db_partner

def delete_commercial_partner(db: Session, partner_id: str) -> Optional[CommercialPartner]:
    db_partner = get_commercial_partner_by_id(db, partner_id)
    if not db_partner:
        return None
    db.delete(db_partner)
    db.commit()
    return db_partner
