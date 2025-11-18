from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...schemas.parking_access.visitor_schemas import VisitorCreate, VisitorOverview, VisitorRequest, VisitorUpdate, VisitorsResponse
from ...crud.parking_access import visitor_crud as crud
from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token  # for dependicies
from shared.core.schemas import Lookup, UserToken
from uuid import UUID

router = APIRouter(
    prefix="/api/visitors",
    tags=["visitors"],
    dependencies=[Depends(validate_current_token)]
)

# -----------------------------------------------------------------


@router.get("/all", response_model=VisitorsResponse)
def get_visitors(
        params: VisitorRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_visitors(db, current_user.org_id, params)


@router.get("/overview", response_model=VisitorOverview)
def get_visitor_overview(
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_visitor_overview(db, current_user.org_id)


@router.post("/", response_model=None)
def create_visitor_log(
        data: VisitorCreate,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    data.org_id = current_user.org_id
    return crud.create_visitor_log(db, data)


@router.put("/", response_model=None)
def update_visitor_log(data: VisitorUpdate, db: Session = Depends(get_db)):
    return crud.update_visitor_log(db, data)


@router.delete("/{id}", response_model=None)
def delete_visitor_log(id: str, db: Session = Depends(get_db)):
    model = crud.delete_visitor_log(db, id)
    if not model:
        raise HTTPException(status_code=404, detail="Visitor not found")
    return model
