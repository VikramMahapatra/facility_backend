from sqlalchemy.orm import Session
from sqlalchemy import func, literal, or_, select
from datetime import datetime

from ...models.procurement.vendors import Vendor

from ...enum.maintenance_assets_enum import WorkOrderPriority, WorkOrderStatus
from ...models.space_sites.spaces import Space
from shared.schemas import Lookup, UserToken
from ...models.maintenance_assets.work_order import WorkOrder
from uuid import UUID
from typing import List, Optional
from ...models.maintenance_assets.assets import Asset
from ...schemas.maintenance_assets.work_order_schemas import WorkOrderCreate, WorkOrderListResponse, WorkOrderOut, WorkOrderRequest, WorkOrderUpdate
from fastapi import HTTPException


def build_work_orders_filters(org_id: UUID, params: WorkOrderRequest):
    filters = [WorkOrder.org_id == org_id]

    if params.status and params.status.lower() != "all":
        filters.append(func.lower(WorkOrder.status) == params.status.lower())

    if params.priority and params.priority.lower() != "all":
        filters.append(func.lower(WorkOrder.priority) == params.priority.lower())

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(WorkOrder.wo_no.ilike(search_term), WorkOrder.type.ilike(search_term)))

    return filters

def get_work_orders_overview(db: Session, org_id: UUID, params: WorkOrderRequest):
    filters = build_work_orders_filters(org_id, params)
    
    # Total work orders with filters
    total = db.query(func.count(WorkOrder.id)).filter(*filters).scalar()

    # Open work orders (case-insensitive) with filters
    open_count = db.query(func.count(WorkOrder.id))\
        .filter(
            *filters,
            func.lower(WorkOrder.status) == 'open'
    ).scalar()

    # ✅ FIXED: In Progress work orders - handle both "in_progress" and "in progress"
    in_progress_count = db.query(func.count(WorkOrder.id))\
        .filter(
            *filters,
            func.lower(WorkOrder.status) == 'in progress'
       
    ).scalar()

    # Overdue work orders (due_at < now) with filters
    overdue_count = db.query(func.count(WorkOrder.id))\
        .filter(*filters)\
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
def work_orders_filter_status_lookup(db: Session, org_id: str):
    rows = (
        db.query(
            func.lower(WorkOrder.status).label("id"),
            func.initcap(WorkOrder.status).label("name")
        )
        .filter(WorkOrder.org_id == org_id, WorkOrder.is_deleted == False)  # ✅ Add soft delete filter
        .distinct()
        .order_by(func.lower(WorkOrder.status))
        .all()
    )
    return [{"id": r.id, "name": r.name} for r in rows]


def work_orders_status_lookup(db: Session, org_id: str, status: Optional[str] = None):
    return [
        Lookup(id=kind.value, name=kind.name.capitalize())
        for kind in WorkOrderStatus
    ]
    # query = (
    #     db.query(
    #         WorkOrder.status.label('id'),
    #         WorkOrder.status.label('name')
    #     )
    #     .filter(WorkOrder.org_id == org_id)
    #     .distinct()
    # )
    # return query.all()


# ---------------- Filter Work Orders by Priority ----------------
def work_orders_filter_priority_lookup(db: Session, org_id: str):
    rows = (
        db.query(
            func.lower(WorkOrder.priority).label("id"),
            func.initcap(WorkOrder.priority).label("name")
        )
        .filter(WorkOrder.org_id == org_id, WorkOrder.is_deleted == False)  # ✅ Add soft delete filter
        .distinct()
        .order_by(func.lower(WorkOrder.priority))
        .all()
    )
    return [{"id": r.id, "name": r.name} for r in rows]


def work_orders_priority_lookup(db: Session, org_id: UUID):
    return [
        Lookup(id=order.value, name=order.name.capitalize())
        for order in WorkOrderPriority
    ]
    # query = (
    #     db.query(
    #         WorkOrder.priority.label('id'),
    #         WorkOrder.priority.label('name')
    #     )
    #     .filter(WorkOrder.org_id == org_id)
    #     .distinct()
    # )
    # return query.all()

# ---------------- Get All ----------------


def build_work_orders_filters(org_id: UUID, params: WorkOrderRequest):
    filters = [WorkOrder.org_id == org_id ,
                WorkOrder.is_deleted == False  # ✅ Add soft delete filte
                ]

    if params.status and params.status.lower() != "all":
        filters.append(func.lower(WorkOrder.status) == params.status.lower())

    if params.priority and params.priority.lower() != "all":
        filters.append(func.lower(WorkOrder.priority) == params.priority.lower())

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(WorkOrder.wo_no.ilike(search_term), WorkOrder.type.ilike(search_term)))

    return filters


def get_work_orders_query(db: Session, org_id: UUID, params: WorkOrderRequest):
    filters = build_work_orders_filters(org_id, params)
    return db.query(WorkOrder).filter(*filters)


def get_work_orders(db: Session, org_id: UUID, params: WorkOrderRequest) -> WorkOrderListResponse:
    base_query = (
        db.query(WorkOrder, Asset.name.label('asset_name'), Space.name.label('space_name'), Vendor.name.label('vendor_name'))
        .outerjoin(Asset, WorkOrder.asset_id == Asset.id)
        .outerjoin(Space, WorkOrder.space_id == Space.id)
        .outerjoin(Vendor, WorkOrder.assigned_to == Vendor.id)  # Add this join
        .filter(WorkOrder.org_id == org_id, WorkOrder.is_deleted == False)  # ✅ Add soft delete filter
    )
    
    # Apply your existing filters
    filters = build_work_orders_filters(org_id, params)
    base_query = base_query.filter(*filters)
    
    total = base_query.count()
    
    work_orders = (
        base_query
        .order_by(WorkOrder.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )
    
    results = []
    for wo, asset_name, space_name, vendor_name in work_orders:
        results.append(
            WorkOrderOut.model_validate({
                **wo.__dict__,
                "asset_name": asset_name,
                "space_name": space_name,
                "assigned_to_name": vendor_name  # This will now work
            })
        )

    return {"work_orders": results, "total": total}


def get_work_order_by_id(db: Session, work_order_id: str) -> Optional[WorkOrder]:
    return db.query(WorkOrder).filter(
        WorkOrder.id == work_order_id,
        WorkOrder.is_deleted == False  # ✅ Add soft delete filter
    ).first()
# ---------------- Create ----------------


def create_work_order(db: Session, work_order: WorkOrderCreate, org_id: UUID) -> WorkOrderOut:
    # Add org_id to the work order data
    work_order_data = work_order.model_dump()
    work_order_data['org_id'] = org_id
    
    db_work_order = WorkOrder(**work_order_data)
    db.add(db_work_order)
    db.commit()
    db.refresh(db_work_order)
    
    # ✅ FIXED: Include all related names
    return WorkOrderOut(
        **db_work_order.__dict__,
        assigned_to_name=db_work_order.vendor.name if db_work_order.vendor else None,
        asset_name=db_work_order.asset.name if db_work_order.asset else None,  # ✅ Add asset name
        space_name=db_work_order.space.name if db_work_order.space else None   # ✅ Add space name
    )


def update_work_order(db: Session, work_order: WorkOrderUpdate) -> Optional[WorkOrderOut]:
    db_work_order = get_work_order_by_id(db, work_order.id)
    if not db_work_order:
        return None
    
    for key, value in work_order.model_dump(exclude_unset=True).items():
        setattr(db_work_order, key, value)
    
    db.commit()
    db.refresh(db_work_order)
    
    # ✅ FIXED: Load all related data for the response
    return WorkOrderOut(
        **db_work_order.__dict__,
        assigned_to_name=db_work_order.vendor.name if db_work_order.vendor else None,
        asset_name=db_work_order.asset.name if db_work_order.asset else None,  # ✅ Add asset name
        space_name=db_work_order.space.name if db_work_order.space else None   # ✅ Add space name
    )
# ----------------- Soft Delete Work Order -----------------
def delete_work_order_soft(db: Session, work_order_id: str, org_id: UUID) -> bool:
    """
    Soft delete work order - set is_deleted to True
    Returns: True if deleted, False if not found
    """
    db_work_order = db.query(WorkOrder).filter(
        WorkOrder.id == work_order_id,
        WorkOrder.org_id == org_id,
        WorkOrder.is_deleted == False
    ).first()
    
    if not db_work_order:
        return False
    
    # ✅ Soft delete
    db_work_order.is_deleted = True
    db_work_order.deleted_at = func.now()
    db.commit()
    return True
