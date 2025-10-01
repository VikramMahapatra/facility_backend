from fastapi import APIRouter, Depends, HTTPException,Query, Path
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from typing import List, Optional
from uuid import UUID
from ...schemas.maintenance_assets.pm_template import (
    PMTemplateBase, PMTemplateCreate, PMTemplateUpdate, PMTemplateListResponse, PMTemplateOverviewResponse, PMTemplateUpdateResponse
)
from ...crud.maintenance_assets.pm_template import (
    create_pm_template, get_all_pm_templates,
    update_pm_template, delete_pm_template,
    get_pm_templates_overview, get_pm_templates_by_frequency, get_pm_templates_by_category_name
)
from shared.auth import validate_current_token
from shared.schemas import  UserToken




router = APIRouter(
    prefix="/api/pmtemplates",
    tags=["PM Templates"]
)

# ---------------- Overview ----------------
@router.get("/overview", response_model=PMTemplateOverviewResponse)
def overview(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return get_pm_templates_overview(db, current_user.org_id)


# ---------------- Filter by frequency ----------------
@router.get("/filter_by_frequency", response_model=PMTemplateListResponse)
def filter_by_frequency(
    frequency: Optional[str] = Query(None, description="Filter by frequency"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    templates = get_pm_templates_by_frequency(db, frequency, current_user.org_id)
    return {"templates": templates}


# ---------------- Filter by asset category ----------------
@router.get("/filter_by_asset_category", response_model=PMTemplateListResponse)
def filter_by_asset_category(
    category_name: Optional[str] = Query(None, description="Filter by category name"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    templates = get_pm_templates_by_category_name(db, category_name, current_user.org_id)
    return {"templates": templates}


# ---------------- List templates ----------------
@router.get("/", response_model=PMTemplateListResponse)
def list_templates(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    templates = get_all_pm_templates(db, current_user.org_id)
    return {"templates": templates}


# ---------------- Create template ----------------
@router.post("/", response_model=PMTemplateBase)
def create_template(
    template: PMTemplateCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return create_pm_template(db, template, current_user.org_id)



# ---------------- Update template ----------------
@router.put("/{template_id}", response_model=PMTemplateUpdateResponse)
def update_template_route(
    template_id: UUID,
    template_update: PMTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    updated_template = update_pm_template(db, template_id, template_update)
    if not updated_template:
        raise HTTPException(status_code=404, detail="Template not found")
    return updated_template


# ---------------- Delete template ----------------
@router.delete("/{template_id}")
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    success = delete_pm_template(db, template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template deleted successfully"}