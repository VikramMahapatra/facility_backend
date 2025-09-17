# app/routers/commercial_partners.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.auth import get_current_token
from app.core.databases import get_db
from app.schemas.commercial_partners_schemas import CommercialPartnerOut, CommercialPartnerCreate, CommercialPartnerUpdate
from app.crud import commercial_partners_crud as crud

router = APIRouter(prefix="/api/commercial-partners", tags=["commercial_partners"],dependencies=[Depends(get_current_token)])

@router.get("/", response_model=List[CommercialPartnerOut])
def read_partners(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_commercial_partners(db, skip=skip, limit=limit)

@router.get("/{partner_id}", response_model=CommercialPartnerOut)
def read_partner(partner_id: str, db: Session = Depends(get_db)):
    db_partner = crud.get_commercial_partner_by_id(db, partner_id)
    if not db_partner:
        raise HTTPException(status_code=404, detail="CommercialPartner not found")
    return db_partner

@router.post("/", response_model=CommercialPartnerOut)
def create_partner(partner: CommercialPartnerCreate, db: Session = Depends(get_db)):
    return crud.create_commercial_partner(db, partner)

@router.put("/{partner_id}", response_model=CommercialPartnerOut)
def update_partner(partner_id: str, partner: CommercialPartnerUpdate, db: Session = Depends(get_db)):
    db_partner = crud.update_commercial_partner(db, partner_id, partner)
    if not db_partner:
        raise HTTPException(status_code=404, detail="CommercialPartner not found")
    return db_partner

@router.delete("/{partner_id}", response_model=CommercialPartnerOut)
def delete_partner(partner_id: str, db: Session = Depends(get_db)):
    db_partner = crud.delete_commercial_partner(db, partner_id)
    if not db_partner:
        raise HTTPException(status_code=404, detail="CommercialPartner not found")
    return db_partner
