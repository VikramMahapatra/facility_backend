from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token  
from shared.schemas import Lookup, UserToken
from ...schemas.hospitality.housekeeping_tasks_schemas import (
    HousekeepingTaskCreate, 
    HousekeepingTaskUpdate, 
    HousekeepingTaskOut, 
    HousekeepingTaskRequest,
    HousekeepingTaskListResponse,
    HousekeepingTaskOverview
)
from ...crud.hospitality import housekeeping_tasks_crud as crud

router = APIRouter(prefix="/api/housekeeping-tasks", tags=[" Housekeeping Tasks Management"])




# -------------------- CRUD Endpoints --------------------
@router.get("/all", response_model=HousekeepingTaskListResponse)
def get_housekeeping_tasks_endpoint(
    params: HousekeepingTaskRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_housekeeping_tasks(db, current_user.org_id, params)


# -------------------- Overview --------------------
@router.get("/overview", response_model=HousekeepingTaskOverview)
def get_housekeeping_overview_endpoint(
    db: Session = Depends(get_db),  
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_housekeeping_overview(db, current_user.org_id)  




@router.post("/", response_model=HousekeepingTaskOut)
def create_housekeeping_task_endpoint(
    task: HousekeepingTaskCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.create_housekeeping_task(db, current_user.org_id, task)


@router.put("/", response_model=dict)
def update_housekeeping_task_endpoint(
    task_update: HousekeepingTaskUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.update_housekeeping_task(db, task_update, current_user)

@router.delete("/{task_id}")
def delete_housekeeping_task_endpoint(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    success = crud.delete_housekeeping_task(db, task_id, current_user.org_id)
    if not success:
        raise HTTPException(status_code=404, detail="Housekeeping Task not found")
    return {"message": "Housekeeping Task deleted successfully"}


# ----------------filter(DB)  Status  ----------------
@router.get("/filter-status-lookup", response_model=List[Lookup])
def housekeeping_tasks_filter_status_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.housekeeping_tasks_filter_status_lookup(db, current_user.org_id)

# -------------------- Status Lookup --------------------
@router.get("/status-lookup", response_model=list[Lookup])
def housekeeping_tasks_priority_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.housekeeping_tasks_priority_lookup(current_user.org_id, db)