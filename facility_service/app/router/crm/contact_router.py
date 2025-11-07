from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token
from shared.core.schemas import Lookup, UserToken
from ...crud.crm import contact_crud as crud


router = APIRouter(
    prefix="/api/contacts",
    tags=["contacts"],
    dependencies=[Depends(validate_current_token)]
)


@router.get("/lookup", response_model=List[Lookup])
def get_customer_lookup(
        kind: Optional[str] = Query(None),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_customer_lookup(db, kind, current_user.org_id)
