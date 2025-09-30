from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import date, timedelta
from ...models.maintenance_assets.pm_template import PMTemplate
from typing import List, Optional
from ...models.maintenance_assets.asset_category import AssetCategory
from ...schemas.maintenance_assets.pm_template import PMTemplateCreate ,PMTemplateUpdate
from uuid import UUID



def get_pm_templates_overview(db: Session, org_id: UUID):
    # Total templates
    total_templates = db.query(PMTemplate).filter(PMTemplate.org_id == org_id).count()

    # Active templates
    active_templates = db.query(PMTemplate).filter(
        PMTemplate.org_id == org_id, PMTemplate.status == 'active'
    ).count()

    # Dates for current week
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    due_this_week = db.query(PMTemplate).filter(
        PMTemplate.org_id == org_id,
        PMTemplate.next_due >= start_of_week,
        PMTemplate.next_due <= end_of_week
    ).count()

    completed_count = db.query(PMTemplate).filter(
        PMTemplate.org_id == org_id,
        PMTemplate.status == 'completed'
    ).count()

    completion_rate = (completed_count / total_templates * 100) if total_templates else 0

    return {
        "total_templates": total_templates,
        "active_templates": active_templates,
        "due_this_week": due_this_week,
        "completion_rate": round(completion_rate, 2)
    }



# ----------------- Filter by Frequency -----------------
def get_pm_templates_by_frequency(db: Session, frequency: Optional[str] = None, org_id: Optional[UUID] = None):
    query = (
        db.query(
            PMTemplate.id,
            PMTemplate.name,
            PMTemplate.frequency,
            PMTemplate.next_due,
            PMTemplate.checklist,
            PMTemplate.sla,
            PMTemplate.status,
            AssetCategory.name.label("asset_category")
        )
        .outerjoin(AssetCategory, PMTemplate.category_id == AssetCategory.id)
    )
    
    if frequency:
        query = query.filter(PMTemplate.frequency.ilike(f"%{frequency}%"))
    
    if org_id:
        query = query.filter(PMTemplate.org_id == org_id)
    
    return query.all()

# ----------------- Filter by Category -----------------
def get_pm_templates_by_category_name(db: Session, category_name: Optional[str] = None, org_id: Optional[UUID] = None):
    query = (
        db.query(
            PMTemplate.id,
            PMTemplate.name,
            PMTemplate.frequency,
            PMTemplate.next_due,
            PMTemplate.checklist,
            PMTemplate.sla,
            PMTemplate.status,
            AssetCategory.name.label("asset_category")
        )
        .join(AssetCategory, PMTemplate.category_id == AssetCategory.id)
    )
    
    if category_name:
        query = query.filter(AssetCategory.name.ilike(f"%{category_name}%"))
    
    if org_id:
        query = query.filter(PMTemplate.org_id == org_id)
    
    return query.all()


def get_all_pm_templates(db: Session, org_id: Optional[UUID] = None):
    templates = db.query(PMTemplate)
    
    if org_id:
        templates = templates.filter(PMTemplate.org_id == org_id)
    
    templates = templates.all()
    result = []

    for t in templates:
        # Fetch the category name if exists
        category_name = None
        if t.category_id:
            category = db.query(AssetCategory).filter(AssetCategory.id == t.category_id).first()
            if category:
                category_name = category.name

        # Convert to dict and add category_name
        template_data = t.__dict__.copy()
        template_data["asset_category"] = category_name
        result.append(template_data)

    return result

#-_____--------------------crud operation-------

def create_pm_template(db: Session, template: PMTemplateCreate, org_id: UUID):
    db_template = PMTemplate(**template.dict())
    db_template.org_id = org_id  # assign from token
    db.add(db_template)
    db.commit()
    db.refresh(db_template)

    # Fetch category name
    category_name = None
    if db_template.category_id:
        category = db.query(AssetCategory).filter(AssetCategory.id == db_template.category_id).first()
        if category:
            category_name = category.name

    return {
        "id": db_template.id,
        "name": db_template.name,
        "asset_category": category_name,
        "frequency": db_template.frequency,
        "next_due": db_template.next_due,
        "checklist": db_template.checklist,
        "sla": db_template.sla,
        "status": db_template.status,
        "meter_metric": db_template.meter_metric,
        "threshold": db_template.threshold
    }




# ---------------- Update ----------------
def update_pm_template(db: Session, template_id: UUID, template_update: PMTemplateUpdate):
    db_template = db.query(PMTemplate).filter(PMTemplate.id == template_id).first()
    if not db_template:
        return None

    for key, value in template_update.dict(exclude_unset=True).items():
        setattr(db_template, key, value)

    db.commit()
    db.refresh(db_template)

    # Fetch category name
    category_name = None
    if db_template.category_id:
        category = db.query(AssetCategory).filter(AssetCategory.id == db_template.category_id).first()
        if category:
            category_name = category.name

    return {
        "id": db_template.id,
        "name": db_template.name,
        "asset_category": category_name,
        "frequency": db_template.frequency,
        "next_due": db_template.next_due,
        "checklist": db_template.checklist,
        "sla": db_template.sla,
        "status": db_template.status,
        "meter_metric": db_template.meter_metric,
        "threshold": db_template.threshold
    }


# ---------------- Delete ----------------
def delete_pm_template(db: Session, template_id: UUID) -> bool:
    db_template = db.query(PMTemplate).filter(PMTemplate.id == template_id).first()
    if not db_template:
        return False
    db.delete(db_template)
    db.commit()
    return True