from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional

from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token, UserToken

from ...schemas.maintenance_assets.work_order import (
    WorkOrderOverviewResponse,
    WorkOrderCreate,
    WorkOrderBase,
    WorkOrderListResponse,
)
from ...crud.maintenance_assets.work_order import (
    get_work_orders_overview,
    get_work_orders_by_status,
    get_work_orders_by_priority,
    get_all_work_orders,
    create_work_order,
    update_work_order,
    delete_work_order,
)

router = APIRouter(
    prefix="/api/workorders",
    tags=["Work Orders"]
)

# ---------------- Work Orders Overview ----------------
@router.get("/overview", response_model=WorkOrderOverviewResponse)
def overview(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return get_work_orders_overview(db, current_user.org_id)


# ---------------- Filter Work Orders by Status ----------------
@router.get("/filter_by_status", response_model=WorkOrderListResponse)
def filter_by_status(
    status: Optional[str] = Query(None, description="Filter work orders by status"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Fetch work orders filtered by status. If no status is provided, returns all work orders.
    """
    orders = get_work_orders_by_status(db, current_user.org_id, status)
    return {"work_orders": orders}


# ---------------- Filter Work Orders by Priority ----------------
@router.get("/filter_by_priority", response_model=WorkOrderListResponse)
def filter_by_priority(
    priority: Optional[str] = Query(None, description="Filter work orders by priority"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Fetch work orders filtered by priority. If no priority is provided, returns all work orders.
    """
    orders = get_work_orders_by_priority(db, current_user.org_id, priority)
    return {"work_orders": orders}


# ---------------- List Work Orders ----------------
@router.get("/", response_model=WorkOrderListResponse)
def list_work_orders(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    orders = get_all_work_orders(db, current_user.org_id)
    return {"work_orders": orders}


# ---------------- Create Work Order ----------------
@router.post("/", response_model=WorkOrderBase)
def create_work_order_route(
    work_order: WorkOrderCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return create_work_order(db, work_order, current_user.org_id, current_user)


# ---------------- Update Work Order ----------------
@router.put("/{work_order_id}", response_model=WorkOrderBase)
def update_work_order_route(
    work_order_id: UUID,
    work_order_update: WorkOrderCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    updated_order = update_work_order(db, work_order_id, work_order_update, current_user)
    return updated_order


# ---------------- Delete Work Order ----------------
@router.delete("/{work_order_id}")
def delete_work_order_route(
    work_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    success = delete_work_order(db, work_order_id)
    if not success:
        raise HTTPException(status_code=404, detail="Work order not found")
    return {"message": "Work order deleted successfully"}
