from sqlalchemy.orm import Session
from sqlalchemy import func, literal, or_, select
from datetime import datetime
from ...models.space_sites.spaces import Space
from shared.schemas import UserToken
from ...models.maintenance_assets.work_order import WorkOrder
from uuid import UUID
from typing import List, Optional
from ...models.maintenance_assets.assets import Asset
from ...schemas.maintenance_assets.work_order_schemas import WorkOrderCreate, WorkOrderListResponse, WorkOrderOut, WorkOrderRequest, WorkOrderUpdate
from fastapi import HTTPException


def get_work_orders_overview(db: Session, org_id: UUID):
    # Total work orders
    total = db.query(func.count(WorkOrder.id)).filter(
        WorkOrder.org_id == org_id).scalar()

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


def work_orders_status_lookup(db: Session, org_id: str, status: Optional[str] = None):
    query = (
        db.query(
            WorkOrder.status.label('id'),
            WorkOrder.status.label('name')
        )
        .filter(WorkOrder.org_id == org_id)
        .distinct()
    )
    return query.all()


# ---------------- Filter Work Orders by Priority ----------------


def work_orders_priority_lookup(db: Session, org_id: UUID):
    query = (
        db.query(
            WorkOrder.priority.label('id'),
            WorkOrder.priority.label('name')
        )
        .filter(WorkOrder.org_id == org_id)
        .distinct()
    )
    return query.all()

# ---------------- Get All ----------------


def build_work_orders_filters(org_id: UUID, params: WorkOrderRequest):
    filters = [WorkOrder.org_id == org_id]

    if params.status and params.status.lower() != "all":
        filters.append(WorkOrder.status.lower() == params.status.lower())

    if params.priority and params.priority.lower() != "all":
        filters.append(WorkOrder.priority.lower() == params.priority.lower())

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(WorkOrder.title.ilike(search_term),
                       WorkOrder.type.ilike(search_term)))

    return filters


def get_work_orders_query(db: Session, org_id: UUID, params: WorkOrderRequest):
    filters = build_work_orders_filters(org_id, params)
    return db.query(WorkOrder).filter(*filters)


def get_work_orders(db: Session, org_id: UUID, params: WorkOrderRequest) -> WorkOrderListResponse:
    base_query = get_work_orders_query(db, org_id, params)
    total = base_query.with_entities(func.count(WorkOrder.id)).scalar()
    work_orders = (
        base_query
        .order_by(WorkOrder.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )
    print(total)
    results = []
    for wo in work_orders:
        asset_name = (
            db.query(Asset.name)
            .filter(Asset.id == wo.asset_id)
            .scalar()
        )
        space_name = (
            db.query(Space.name)
            .filter(Space.id == wo.space_id)
            .scalar()
        )
        results.append(
            WorkOrderOut.model_validate({
                **wo.__dict__,
                "asset_name": asset_name,
                "space_name": space_name
            })
        )

    return {"work_orders": results, "total": total}


def get_work_order_by_id(db: Session, work_order_id: str) -> Optional[WorkOrder]:
    return db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
# ---------------- Create ----------------


def create_work_order(db: Session, work_order: WorkOrderCreate):
    db_work_order = WorkOrder(**work_order.model_dump())
    db.add(db_work_order)
    db.commit()
    db.refresh(db_work_order)
    return db_work_order


def update_work_order(db: Session, work_order: WorkOrderUpdate) -> Optional[WorkOrder]:
    db_work_order = get_work_order_by_id(db, work_order.id)
    if not db_work_order:
        return None
    for key, value in work_order.dict(exclude_unset=True).items():
        setattr(db_work_order, key, value)
    db.commit()
    db.refresh(db_work_order)
    return db_work_order


def delete_work_order(db: Session, work_order_id: str) -> Optional[WorkOrder]:
    db_work_order = get_work_order_by_id(db, work_order_id)
    if not db_work_order:
        return None
    db.delete(db_work_order)
    db.commit()
    return True
