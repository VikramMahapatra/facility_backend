from datetime import date, timedelta
from typing import Optional
from uuid import UUID
from ...enum.maintenance_assets_enum import PmtemplateFrequency, PmtemplateStatus
from shared.core.schemas import Lookup
from sqlalchemy import func, literal, or_
from sqlalchemy.orm import Session
from typing import List, Dict
from ...models.maintenance_assets.pm_template import PMTemplate
from ...models.maintenance_assets.asset_category import AssetCategory
from ...schemas.maintenance_assets.pm_templates_schemas import (
    PMTemplateCreate,
    PMTemplateUpdate,
    PMTemplateRequest,
    PMTemplateListResponse,
    PMTemplateOut,
)


# ----------------- Update Existing overview Functions with Soft Delete Filter -----------------

def get_pm_templates_overview(db: Session, org_id: UUID, params: PMTemplateRequest):
    filters = build_pm_template_filters(org_id, params)

    # Dates for current week
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    # Total templates with filters (exclude deleted)
    total_templates = db.query(PMTemplate).filter(
        *filters, PMTemplate.is_deleted == False).count()

    # Active templates with filters (exclude deleted)
    active_templates = db.query(PMTemplate).filter(
        *filters,
        PMTemplate.status == 'active',
        PMTemplate.is_deleted == False
    ).count()

    # Due this week with filters (exclude deleted)
    due_this_week = db.query(PMTemplate).filter(
        *filters,
        PMTemplate.next_due >= start_of_week,
        PMTemplate.next_due <= end_of_week,
        PMTemplate.is_deleted == False
    ).count()

    # Completed count with filters (exclude deleted)
    completed_count = db.query(PMTemplate).filter(
        *filters,
        PMTemplate.status == 'completed',
        PMTemplate.is_deleted == False
    ).count()

    # Completion rate with filters
    completion_rate = (completed_count / total_templates *
                       100) if total_templates else 0

    return {
        "total_templates": total_templates,
        "active_templates": active_templates,
        "due_this_week": due_this_week,
        "completion_rate": round(completion_rate, 2)
    }

# ----------------- LOOKUP by Frequency -----------------


def pm_templates_filter_frequency_lookup(db: Session, org_id: str):
    rows = (
        db.query(
            func.lower(PMTemplate.frequency).label("id"),
            func.initcap(PMTemplate.frequency).label("name")
        )
        .filter(
            PMTemplate.org_id == org_id,
            PMTemplate.is_deleted == False  # ✅ Add soft delete filter
        )
        .distinct()
        .order_by(func.lower(PMTemplate.frequency))
        .all()
    )
    return [{"id": r.id, "name": r.name} for r in rows]


# ----------------- Filter by Frequency Enum-----------------
def pm_templates_frequency_lookup(db: Session, org_id: str):
    return [
        Lookup(id=frequency.value, name=frequency.name.capitalize())
        for frequency in PmtemplateFrequency
    ]


# ----------------- Filter by Category -----------------

def pm_templates_category_lookup(db: Session, org_id: str) -> List[Dict]:
    # Query distinct category names
    query = (
        db.query(
            AssetCategory.id.label("id"),
            AssetCategory.name.label("name")
        )
        .join(PMTemplate, PMTemplate.category_id == AssetCategory.id)
        .filter(
            PMTemplate.org_id == org_id,
            PMTemplate.is_deleted == False  # ✅ Add soft delete filter
        )
        .distinct()
        .order_by(AssetCategory.name)
    )

    rows = query.all()
    # Return as list of dicts
    return [{"id": r.id, "name": r.name} for r in rows]

# -----------status_lookup


def pm_templates_filter_status_lookup(db: Session, org_id: str) -> List[Dict]:
    # Query distinct lease statuses for the org
    query = (
        db.query(
            PMTemplate.status.label("id"),
            PMTemplate.status.label("name")
        )
        .filter(
            PMTemplate.org_id == org_id,
            PMTemplate.is_deleted == False  # ✅ Add soft delete filter
        )
        .distinct()
        .order_by(PMTemplate.status)
    )
    rows = query.all()
    return [{"id": r.id, "name": r.name} for r in rows]

# ----------------- Filter by status Enum-----------------


def pm_templates_status_lookup(db: Session, org_id: str):
    return [
        Lookup(id=status.value, name=status.name.capitalize())
        for status in PmtemplateStatus
    ]

# ----------------- Build Filters -----------------


def build_pm_template_filters(org_id: UUID, params: PMTemplateRequest):
    filters = [PMTemplate.org_id == org_id,
               PMTemplate.is_deleted == False  # ✅ Add soft delete filter
               ]

    if params.category_id and params.category_id.lower() != "all":
        filters.append(PMTemplate.category_id == params.category_id)

    if params.frequency and params.frequency.lower() != "all":
        filters.append(func.lower(PMTemplate.frequency)
                       == params.frequency.lower())

    if params.status and params.status.lower() != "all":
        filters.append(func.lower(PMTemplate.status) == params.status.lower())

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(PMTemplate.pm_no.ilike(search_term),
                       PMTemplate.name.ilike(search_term)))

    return filters


def get_pm_template_query(db: Session, org_id: UUID, params: PMTemplateRequest):
    filters = build_pm_template_filters(org_id, params)
    return db.query(PMTemplate).filter(*filters)


# ----------------- Get All Templates -----------------
def get_pm_templates(db: Session, org_id: UUID, params: PMTemplateRequest) -> PMTemplateListResponse:
    base_query = get_pm_template_query(db, org_id, params)
    total = base_query.with_entities(func.count(PMTemplate.id)).scalar()
    templates = (
        base_query
        .order_by(PMTemplate.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )
    results = []
    for t in templates:
        # Get category name if exists
        category_name = (
            db.query(AssetCategory.name)
            .filter(AssetCategory.id == t.category_id)
            .scalar()
        )
        results.append(
            PMTemplateOut.model_validate(
                {**t.__dict__, "asset_category": category_name}
            )
        )
    return {"templates": results, "total": total}

# ----------------- Get By ID -----------------


def get_pm_template_by_id(db: Session, template_id: str) -> Optional[PMTemplate]:
    return db.query(PMTemplate).filter(PMTemplate.id == template_id,
                                       PMTemplate.is_deleted == False  # ✅ Add soft delete filter
                                       ).first()


# ----------------- Create -----------------
def create_pm_template(db: Session, template: PMTemplateCreate) -> PMTemplate:
    # This excludes any fields that weren't explicitly set in the request
    db_template = PMTemplate(
        **template.model_dump(exclude_unset=True, exclude="asset_category"))
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

# ----------------- Update -----------------


def update_pm_template(db: Session, template: PMTemplateUpdate) -> Optional[PMTemplate]:
    db_template = get_pm_template_by_id(db, template.id)
    if not db_template:
        return None
    for k, v in template.dict(exclude_unset=True).items():
        setattr(db_template, k, v)
    db.commit()
    db.refresh(db_template)
    return db_template


# ----------------- Soft Delete PM Template -----------------
def delete_pm_template_soft(db: Session, template_id: UUID, org_id: UUID) -> bool:
    """
    Soft delete PM template
    Returns: True if deleted, False if not found
    """
    db_template = db.query(PMTemplate).filter(
        PMTemplate.id == template_id,
        PMTemplate.org_id == org_id,
        PMTemplate.is_deleted == False
    ).first()

    if not db_template:
        return False

    # ✅ Soft delete
    db_template.is_deleted = True
    db_template.deleted_at = func.now()
    db.commit()
    return True
