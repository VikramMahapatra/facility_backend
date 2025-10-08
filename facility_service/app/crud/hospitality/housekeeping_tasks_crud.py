from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, cast, String, case
from uuid import UUID
from typing import Dict, Optional, List

from shared.schemas import Lookup

from ...models.hospitality.housekeeping_tasks import HousekeepingTask
from ...schemas.hospitality.housekeeping_tasks_schemas import (
    HousekeepingTaskCreate,
    HousekeepingTaskOut, 
    HousekeepingTaskUpdate, 
    HousekeepingTaskRequest, 
    HousekeepingTaskListResponse,
    HousekeepingTaskOverview
)

from ...enum.hospitality_enum import HousekeepingTaskPriority

# ----------------- Overview Calculation -----------------
def get_housekeeping_overview(db: Session, org_id: UUID) -> HousekeepingTaskOverview:
    
    counts = (
        db.query(
            func.count(HousekeepingTask.id).label("total_tasks"),
            func.count(case((HousekeepingTask.status == "clean", 1))).label("clean_rooms"),
            func.count(case((HousekeepingTask.status.in_(["cleaning", "inspected"]), 1))).label("in_progress"),
            func.avg(
                case(
                    (HousekeepingTask.status == "clean" and HousekeepingTask.completed_at.isnot(None), 
                     func.extract('epoch', HousekeepingTask.completed_at - HousekeepingTask.created_at) / 3600),  # hours
                    else_=None
                )
            ).label("avg_time")
        )
        .filter(HousekeepingTask.org_id == org_id)  # Only org filter
        .one()
    )

    return {
        "totalTasks": counts.total_tasks or 0,
        "cleanRooms": counts.clean_rooms or 0,
        "inProgress": counts.in_progress or 0,
        "avgTime": round(float(counts.avg_time or 0), 2)
    }


# ----------------- Build Filters -----------------
def build_housekeeping_filters(org_id: UUID, params: HousekeepingTaskRequest):
    filters = [HousekeepingTask.org_id == org_id]

    if params.status and params.status.lower() != "all":
        filters.append(HousekeepingTask.status == params.status)

    if params.priority and params.priority.lower() != "all":  
        filters.append(HousekeepingTask.priority == params.priority)

    if params.task_date:
        filters.append(HousekeepingTask.task_date == params.task_date)

    if params.site_id:
        filters.append(HousekeepingTask.site_id == params.site_id)

    if params.space_id:
        filters.append(HousekeepingTask.space_id == params.space_id)

    if params.assigned_to:
        filters.append(HousekeepingTask.assigned_to == params.assigned_to)

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(
            or_(
                HousekeepingTask.notes.ilike(search_term),
                cast(HousekeepingTask.id, String).ilike(search_term),
                cast(HousekeepingTask.assigned_to, String).ilike(search_term),
            )
        )
    return filters


def get_housekeeping_query(db: Session, org_id: UUID, params: HousekeepingTaskRequest):
    filters = build_housekeeping_filters(org_id, params)
    return db.query(HousekeepingTask).filter(*filters)


# ----------------- Get All Tasks -----------------
def get_housekeeping_tasks(db: Session, org_id: UUID, params: HousekeepingTaskRequest) -> HousekeepingTaskListResponse:
    base_query = get_housekeeping_query(db, org_id, params)
    total = base_query.with_entities(func.count(HousekeepingTask.id)).scalar()

    # NEW ENTRIES SHOW FIRST - ordered by created_at descending
    tasks = (
        base_query
        .order_by(HousekeepingTask.created_at.desc())  # Newest first
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    results = []
    for task in tasks:
        results.append(HousekeepingTaskOut.model_validate(task.__dict__))

    return {"tasks": results, "total": total}



# ----------------- Create Task -----------------
def create_housekeeping_task(db: Session, org_id: UUID, task: HousekeepingTaskCreate) -> HousekeepingTask:
    task_data = task.model_dump(exclude={"org_id"})
    
    # AUTO-SET completed_at IF TASK IS CREATED AS "clean"
    if task_data.get('status') == 'clean' and 'completed_at' not in task_data:
        task_data['completed_at'] = func.now()
    
    db_task = HousekeepingTask(
        org_id=org_id,
        **task_data
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


# ----------------- Update Task -----------------
def update_housekeeping_task(db: Session, task_update: HousekeepingTaskUpdate, current_user) -> Optional[HousekeepingTask]:
    db_task = db.query(HousekeepingTask).filter(
        HousekeepingTask.id == task_update.id,
        HousekeepingTask.org_id == current_user.org_id
    ).first()

    if not db_task:
        return None

    #  AUTO-SET completed_at WHEN STATUS CHANGES TO "clean"
    if (task_update.status == "clean" and 
        db_task.status != "clean" and 
        db_task.completed_at is None):
        db_task.completed_at = func.now()  # Set completion time to current time
    
    #  AUTO-CLEAR completed_at IF STATUS CHANGES FROM "clean"
    elif (task_update.status != "clean" and 
          db_task.status == "clean" and 
          db_task.completed_at is not None):
        db_task.completed_at = None

    # Update only fields provided
    update_data = task_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_task, key, value)

    db.commit()
    db.refresh(db_task)
    return db_task


# ----------------- Delete Task -----------------
def delete_housekeeping_task(db: Session, task_id: UUID, org_id: UUID) -> bool:
    db_task = db.query(HousekeepingTask).filter(
        HousekeepingTask.id == task_id,
        HousekeepingTask.org_id == org_id
    ).first()
    
    if not db_task:
        return False
        
    db.delete(db_task)
    db.commit()
    return True

#-----------filter status----------------

def housekeeping_tasks_filter_status_lookup(db: Session, org_id: str) -> List[Dict]:
    query = (
        db.query(
            HousekeepingTask.status.label("id"),
            HousekeepingTask.status.label("name")
        )
        .filter(HousekeepingTask.org_id == org_id)
        .distinct()
        .order_by(HousekeepingTask.status)
    )
    rows = query.all()
    return [{"id": r.id, "name": r.name} for r in rows]

#------------------priority lookup enum 

def housekeeping_tasks_priority_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=priority.value, name=priority.name.capitalize())
        for priority in HousekeepingTaskPriority
    ]