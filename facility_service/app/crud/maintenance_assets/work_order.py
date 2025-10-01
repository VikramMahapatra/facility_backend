from sqlalchemy.orm import Session
from sqlalchemy import func,or_,select
from datetime import datetime

from shared.schemas import UserToken
from ...models.maintenance_assets.work_order import WorkOrder
from uuid import UUID
from typing import List, Optional
from ...models.maintenance_assets.assets import Asset
from ...schemas.maintenance_assets.work_order import WorkOrderCreate, WorkOrderUpdate
from fastapi import HTTPException



def get_work_orders_overview(db: Session, org_id: UUID):
    # Total work orders
    total = db.query(func.count(WorkOrder.id)).filter(WorkOrder.org_id == org_id).scalar()
    
    # Open work orders (case-insensitive)
    open_count = db.query(func.count(WorkOrder.id))\
        .filter(
            WorkOrder.org_id == org_id,
            func.lower(WorkOrder.status) == 'open'
        ).scalar()
    
    # In Progress work orders (case-insensitive)
    in_progress_count = db.query(func.count(WorkOrder.id))\
        .filter(
            WorkOrder.org_id == org_id,
            func.lower(WorkOrder.status) == 'in progress'
        ).scalar()
    
    # Overdue work orders (due_at < now)
    overdue_count = db.query(func.count(WorkOrder.id))\
        .filter(WorkOrder.org_id == org_id)\
        .filter(WorkOrder.status != "closed")\
        .filter(WorkOrder.due_at != None)\
        .filter(WorkOrder.due_at < datetime.utcnow())\
        .scalar()
        
    return {
        "total": total,
        "open": open_count,
        "in_progress": in_progress_count,
        "overdue": overdue_count
    }

# ---------------- Filter Work Orders by Status ----------------

def get_work_orders_by_status(db: Session, org_id: UUID, status: str = None):
    query = (
        db.query(
            WorkOrder.id,
            WorkOrder.title,
            WorkOrder.description,
            WorkOrder.priority,
            WorkOrder.status,
            WorkOrder.assigned_to,
            WorkOrder.due_at,
            Asset.name.label("asset_name")
        )
        .join(Asset, WorkOrder.asset_id == Asset.id, isouter=True)  # left join
        .filter(WorkOrder.org_id == org_id)
    )

    if status:  # filter only if status is provided
        query = query.filter(func.lower(WorkOrder.status) == status.lower())

    work_orders = query.all()

    # Convert to list of dicts
    return [
        {
            "id": wo.id,
            "title": wo.title,
            "description": wo.description,
            "priority": wo.priority,
            "status": wo.status,
            "assigned_to": wo.assigned_to,
            "due_at": wo.due_at,
            "asset_name": wo.asset_name
        }
        for wo in work_orders
    ]

# ---------------- Filter Work Orders by Priority ----------------

def get_work_orders_by_priority(db: Session, org_id: UUID, priority: str = None):
    query = (
        db.query(
            WorkOrder.id,
            WorkOrder.title,
            WorkOrder.description,
            WorkOrder.priority,
            WorkOrder.status,
            WorkOrder.assigned_to,
            WorkOrder.due_at,
            Asset.name.label("asset_name")
        )
        .join(Asset, WorkOrder.asset_id == Asset.id, isouter=True)
        .filter(WorkOrder.org_id == org_id)
    )

    if priority:
        query = query.filter(func.lower(WorkOrder.priority) == priority.lower())

    return [
        {
            "id": wo.id,
            "title": wo.title,
            "description": wo.description,
            "priority": wo.priority,
            "status": wo.status,
            "assigned_to": wo.assigned_to,
            "due_at": wo.due_at,
            "asset_name": wo.asset_name
        }
        for wo in query.all()
    ]

# ---------------- Get All ----------------
def get_all_work_orders(db: Session, org_id: UUID):
    orders = db.query(WorkOrder).filter(WorkOrder.org_id == org_id).all()
    result = []

    for o in orders:
        asset_name = None
        if o.asset_id:
            asset = db.query(Asset).filter(Asset.id == o.asset_id).first()
            if asset:
                asset_name = asset.name

        order_data = o.__dict__.copy()
        order_data["asset_name"] = asset_name
        result.append(order_data)

    return result

# ---------------- Create ----------------


def create_work_order(db: Session, work_order: WorkOrderCreate, org_id: UUID, current_user):
    if not getattr(work_order, "site_name", None) and not getattr(work_order, "site_id", None):
        raise HTTPException(status_code=400, detail="site_id is required")

    db_order = WorkOrder(
        org_id=org_id,
        site_id=getattr(work_order, "site_id", None),  # use site_id directly
        asset_id=work_order.asset_id,
        space_id=work_order.space_id or None,
        title=work_order.title,
        description=work_order.description,
        priority=work_order.priority or "medium",
        type=work_order.type or "corrective",
        status=work_order.status or "open",
        due_at=work_order.due_at,
        assigned_to=current_user.user_id,  # from token
        created_by=current_user.user_id    # from token
    )

    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    # Fetch asset name if exists
    asset_name = None
    if db_order.asset_id:
        asset = db.query(Asset).filter(Asset.id == db_order.asset_id).first()
        if asset:
            asset_name = asset.name

    return {
        "id": db_order.id,
        "title": db_order.title,
        "description": db_order.description,
        "priority": db_order.priority,
        "status": db_order.status,
        "asset_name": asset_name,
        "assigned_to": db_order.assigned_to,
        "due_at": db_order.due_at
    }



# ---------------- Update ----------------
def update_work_order(
    db: Session,
    work_order_id: UUID,
    work_order_data: WorkOrderCreate,
    current_user: UserToken
):
    db_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not db_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    # Update fields from input
    for field, value in work_order_data.dict(exclude_unset=True).items():
        setattr(db_order, field, value)

    # Always set assigned_to from current user
    db_order.assigned_to = current_user.user_id

    db.commit()
    db.refresh(db_order)

    # Fetch asset name if exists
    asset_name = None
    if db_order.asset_id:
        asset = db.query(Asset).filter(Asset.id == db_order.asset_id).first()
        if asset:
            asset_name = asset.name

    return {
        "id": db_order.id,
        "title": db_order.title,
        "description": db_order.description,
        "priority": db_order.priority,
        "status": db_order.status,
        "asset_name": asset_name,
        "assigned_to": db_order.assigned_to,
        "due_at": db_order.due_at
    }


# ---------------- Delete ----------------
def delete_work_order(db: Session, work_order_id: UUID) -> bool:
    db_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not db_order:
        return False
    db.delete(db_order)
    db.commit()
    return True
