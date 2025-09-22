# app/routers/orgs.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from shared.database import get_facility_db as get_db
from ...schemas.orgs_schemas import OrgOut, OrgCreate, OrgUpdate
from ...crud.space_sites import orgs_crud as crud_orgs
from shared.auth import validate_current_token
from shared.schemas import UserToken


router = APIRouter(
    prefix="/api/orgs",
    tags=["orgs"],
    # dependencies=[Depends(validate_current_token)]
)


@router.get("/getall", response_model=List[OrgOut])
def read_orgs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud_orgs.get_orgs(db, skip=skip, limit=limit)

@router.get("/", response_model=OrgOut)
def read_org(db: Session = Depends(get_db), current_user : UserToken = Depends(validate_current_token)):
    db_org = crud_orgs.get_org_by_id(db, current_user.org_id)
    if not db_org:
        raise HTTPException(status_code=404, detail="Org not found")
    return db_org

@router.post("/", response_model=OrgOut)
def create_org(org: OrgCreate, db: Session = Depends(get_db)):
    return crud_orgs.create_org(db, org)

@router.put("/", response_model=OrgOut)
def update_org(org: OrgUpdate, db: Session = Depends(get_db)):
    db_org = crud_orgs.update_org(db, org)
    if not db_org:
        raise HTTPException(status_code=404, detail="Org not found")
    return db_org

@router.delete("/{org_id}", response_model=OrgOut)
def delete_org(org_id: str, db: Session = Depends(get_db)):
    db_org = crud_orgs.delete_org(db, org_id)
    if not db_org:
        raise HTTPException(status_code=404, detail="Org not found")
    return db_org
