from sqlalchemy.orm import Session
from sqlalchemy import func, or_, cast, Text, case
from typing import Dict, List, Optional
from datetime import date, datetime
from sqlalchemy.dialects.postgresql import UUID

from shared.schemas import Lookup
from ...models.hospitality.rate_plans import RatePlan
from ...models.hospitality.rates import Rate
from ...schemas.hospitality.rate_plans_schemas import (
    RatePlanCreate, RatePlanOut, RatePlanUpdate, RatePlanRequest, 
    RatePlanListResponse, RatePlanOverview
)
from ...enum.hospitality_enum import RatePlansMealPlan ,RatePlanStatus
# ----------------- Overview Calculation -----------------
def get_rate_plan_overview(
    db: Session, 
    org_id: UUID, 
    site_id: UUID = None
) -> RatePlanOverview:
    # Base filters for organization and optional site
    filters = [RatePlan.org_id == org_id]
    if site_id:
        filters.append(RatePlan.site_id == site_id)

    # Get today's date for active rate calculations
    today = date.today()

    # 1. TOTAL RATE PLANS - Count all rate plans in the organization
    total_rate_plans = db.query(func.count(RatePlan.id))\
        .filter(*filters)\
        .scalar() or 0

    # 2. ACTIVE PLANS - Count plans that have rates in the future
    active_plans_subquery = db.query(Rate.rate_plan_id)\
        .filter(Rate.date >= today)\
        .distinct()\
        .subquery()
    
    active_plans = db.query(func.count(RatePlan.id))\
        .join(active_plans_subquery, RatePlan.id == active_plans_subquery.c.rate_plan_id)\
        .filter(*filters)\
        .scalar() or 0

    # 3. AVG. BASE PLANS - Calculate average price of all future rates
    avg_base_plans = db.query(func.coalesce(func.avg(Rate.price), 0))\
        .join(RatePlan, Rate.rate_plan_id == RatePlan.id)\
        .filter(
            *filters,
            Rate.date >= today
        )\
        .scalar() or 0

    # 4. CORPORATE PLANS - Count plans with corporate-related names
    corporate_plans = db.query(func.count(RatePlan.id))\
        .filter(
            *filters,
            or_(
                func.lower(RatePlan.name).like('%corp%'),
                func.lower(RatePlan.name).like('%corporate%'),
                func.lower(RatePlan.name).like('%company%')
            )
        )\
        .scalar() or 0

    return {
        "totalRatePlans": int(total_rate_plans),
        "activePlans": int(active_plans),
        "avgBasePlans": float(avg_base_plans),
        "corporatePlans": int(corporate_plans)
    }


def rate_plan_filter_status_lookup(db: Session, org_id: str) -> List[Dict]:
    query = (
        db.query(
            RatePlan.status.label("id"),
            RatePlan.status.label("name")
        )
        .filter(RatePlan.org_id == org_id)
        .distinct()
        .order_by(RatePlan.status)
    )
    rows = query.all()
    return [{"id": r.id, "name": r.name} for r in rows]


# --------------------Rate_Plan_Status_lookup(hardcode) by Enum -----------

def Rate_Plan_Status_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=status.value, name=status.name.capitalize())
        for status in RatePlanStatus
    ]

# --------------------Rate_Plan_MealPlan_lookup(hardcode) by Enum -----------

def Rate_Plan_Meal_Plan_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=meal_plan.value, name=meal_plan.name.capitalize())
        for meal_plan in RatePlansMealPlan
    ]


# ----------------- Build Filters -----------------
def build_rate_plan_filters(org_id: UUID, params: RatePlanRequest):
    filters = [RatePlan.org_id == org_id]

    if params.meal_plan and params.meal_plan.lower() != "all":
        filters.append(func.lower(RatePlan.meal_plan) == params.meal_plan.lower())

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(
            or_(
                RatePlan.name.ilike(search_term),
                cast(RatePlan.id, Text).ilike(search_term),
            )
        )
    return filters


def get_rate_plan_query(db: Session, org_id: UUID, params: RatePlanRequest):
    filters = build_rate_plan_filters(org_id, params)
    return db.query(RatePlan).filter(*filters)


# ----------------- Get All Rate Plans -----------------
def get_rate_plans(db: Session, org_id: UUID, params: RatePlanRequest) -> RatePlanListResponse:
    base_query = get_rate_plan_query(db, org_id, params)
    total = base_query.with_entities(func.count(RatePlan.id)).scalar()

    #  NEW ENTRIES SHOW FIRST
    rate_plans = (
        base_query
        .order_by(RatePlan.created_at.desc())  # Newest rate plans first
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    results = []
    for rate_plan in rate_plans:
        results.append(RatePlanOut.model_validate(rate_plan.__dict__))

    return {"rate_plans": results, "total": total}


# ----------------- Get Single Rate Plan -----------------
def get_rate_plan(db: Session, rate_plan_id: UUID, org_id: UUID) -> Optional[RatePlan]:
    return db.query(RatePlan).filter(
        RatePlan.id == rate_plan_id,
        RatePlan.org_id == org_id
    ).first()


# ----------------- Create Rate Plan -----------------
def create_rate_plan(db: Session, org_id: UUID, rate_plan: RatePlanCreate) -> RatePlan:
    db_rate_plan = RatePlan(
        org_id=org_id,
        **rate_plan.dict(exclude={"org_id"})
    )
    db.add(db_rate_plan)
    db.commit()
    db.refresh(db_rate_plan)
    return db_rate_plan


# ----------------- Update Rate Plan -----------------
def update_rate_plan(db: Session, rate_plan_update: RatePlanUpdate, current_user) -> Optional[RatePlan]:
    db_rate_plan = db.query(RatePlan).filter(
        RatePlan.id == rate_plan_update.id,
        RatePlan.org_id == current_user.org_id
    ).first()

    if not db_rate_plan:
        return None

    # Update only fields provided
    update_data = rate_plan_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_rate_plan, key, value)

    db.commit()
    db.refresh(db_rate_plan)
    return db_rate_plan


# ----------------- Delete Rate Plan -----------------
def delete_rate_plan(db: Session, rate_plan_id: UUID, org_id: UUID) -> bool:
    db_rate_plan = db.query(RatePlan).filter(
        RatePlan.id == rate_plan_id,
        RatePlan.org_id == org_id
    ).first()
    
    if not db_rate_plan:
        return False
        
    db.delete(db_rate_plan)
    db.commit()
    return True