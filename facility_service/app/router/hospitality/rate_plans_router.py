from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from shared.utils.app_status_code import AppStatusCode
from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token
from shared.helpers.json_response_helper import error_response, success_response
from shared.core.schemas import Lookup, UserToken
from ...schemas.hospitality.rate_plans_schemas import (
    RatePlanCreate,
    RatePlanUpdate,
    RatePlanOut,
    RatePlanRequest,
    RatePlanListResponse,
    RatePlanOverview
)
from ...crud.hospitality import rate_plans_crud as crud

router = APIRouter(prefix="/api/rate-plans", tags=["Rate Plan Management"])


# ---------------- List Rate Plans ----------------
@router.get("/all", response_model=RatePlanListResponse)
def get_rate_plans_endpoint(
    params: RatePlanRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_rate_plans(db, current_user.org_id, params)

# ---------------- Overview -----------------


@router.get("/overview", response_model=RatePlanOverview)
def get_rate_plan_overview(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_rate_plan_overview(db, current_user.org_id)


# ----------------- Create Rate Plan -----------------
@router.post("/", response_model=RatePlanOut)
def create_rate_plan_route(
    rate_plan: RatePlanCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.create_rate_plan(db, current_user.org_id, rate_plan)

# ----------------- Update Rate Plan -----------------


@router.put("/", response_model=None)
def update_rate_plan_route(
    rate_plan_update: RatePlanUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    result = crud.update_rate_plan(db, rate_plan_update, current_user)

    if not result:
        return error_response(
            message="Rate Plan not found",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=404
        )
    return result

# ---------------- Delete Rate Plan ----------------


@router.delete("/{rate_plan_id}")
def delete_rate_plan_route(
    rate_plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
): return crud.delete_rate_plan(db, rate_plan_id, current_user.org_id)


# ----------------filter(DB)  Status  ----------------
@router.get("/filter-status-lookup", response_model=List[Lookup])
def rate_plan_filter_status_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.rate_plan_filter_status_lookup(db, current_user.org_id)

# -------------------- Rate Plan Status Lookup --------------------


@router.get("/status-lookup", response_model=list[Lookup])
def get_rate_plan_status_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.Rate_Plan_Status_lookup(current_user.org_id, db)


# -------------------- Rate Plan Meal Plan Lookup --------------------
@router.get("/meal-plans-lookup", response_model=list[Lookup])
def get_rate_plan_meal_plan_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.Rate_Plan_Meal_Plan_lookup(current_user.org_id, db)
