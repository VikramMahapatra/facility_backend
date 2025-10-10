from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional


from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token, UserToken
from shared.schemas import Lookup

from ...schemas.maintenance_assets.work_order_schemas import (
    WorkOrderListResponse,
    WorkOrderOut,
    WorkOrderOverviewResponse,
    WorkOrderCreate,
    WorkOrderRequest,
    WorkOrderUpdate,
)
from ...crud.maintenance_assets import work_order_crud as crud
from ...crud.maintenance_assets.work_order_crud import (
    create_work_order,
    get_work_orders_overview,
)

router = APIRouter(
    prefix="/api/workorder",
    tags=["Work Orders"],
    dependencies=[Depends(validate_current_token)]
)

@router.get("/all", response_model=WorkOrderListResponse)
def get_work_orders(
    params : WorkOrderRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)) :
    return crud.get_work_orders(db, current_user.org_id, params)

# ---------------- Work Orders Overview ----------------
@router.get("/overview", response_model=WorkOrderOverviewResponse)
def overview(
    params: WorkOrderRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return get_work_orders_overview(db, current_user.org_id, params)


@router.put("/{work_order_id}", response_model=None)
def update_work_order(  
    work_order: WorkOrderUpdate,
    db: Session = Depends(get_db)
):
    db_work_order = crud.update_work_order(db, work_order)
    if not db_work_order:
        raise HTTPException(status_code=404, detail="Work order not found")
    return {"message": "Work order updated successfully"}

@router.post("/", response_model=WorkOrderOut)
def create_work_order_endpoint(
    work_order: WorkOrderCreate, 
    db: Session = Depends(get_db),
    current_user : UserToken = Depends(validate_current_token)):
    work_order.org_id = current_user.org_id
    return create_work_order(db, work_order)

@router.delete("/{work_order_id}", response_model=None)
def delete_work_order(work_order_id: str, db: Session = Depends(get_db)):
    db_work_order = crud.delete_work_order(db, work_order_id)
    if not db_work_order:
        raise HTTPException(status_code=404, detail="work order not found")
    return db_work_order

# ---------------- Filter Work Orders by Status ----------------
@router.get("/filter-status-lookup", response_model=List[Lookup])
def work_orders_filter_status_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.work_orders_filter_status_lookup(db, current_user.org_id)


@router.get("/status-lookup", response_model=List[Lookup])
def work_orders_status_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.work_orders_status_lookup(db, current_user.org_id)

# ---------------- Filter Work Orders by Priority ----------------
@router.get("/filter-priority-lookup", response_model=List[Lookup])
def work_order_filter_priority_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.work_orders_filter_priority_lookup(db, current_user.org_id)


@router.get("/priority-lookup", response_model=List[Lookup])
def work_order_priority_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.work_orders_priority_lookup(db, current_user.org_id)
