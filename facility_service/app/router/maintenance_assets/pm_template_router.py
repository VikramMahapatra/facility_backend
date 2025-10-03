from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from shared.auth import validate_current_token #for dependicies 
from shared.database import get_facility_db as get_db
from shared.schemas import Lookup, UserToken
from facility_service.app.schemas.maintenance_assets.pm_templates_schemas import (
    PMTemplateCreate,
    PMTemplateOverviewResponse,
    PMTemplateUpdate,
    PMTemplateOut,
    PMTemplateRequest,
    PMTemplateListResponse,
)
from facility_service.app.crud.maintenance_assets import pm_template_crud as crud

router = APIRouter(prefix="/api/pm_templates", tags=["PM Templates"])


# ---------------- List templates ----------------
@router.get("/all", response_model=PMTemplateListResponse)
def get_pm_templates(
    params: PMTemplateRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_pm_templates(db, current_user.org_id, params)

# ---------------- Overview ----------------
@router.get("/overview", response_model=PMTemplateOverviewResponse)
def overview(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_pm_templates_overview(db, current_user.org_id)

# ---------------- Update template ----------------
@router.put("/", response_model=None)
def update_pm_template(
    template: PMTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    db_template = crud.update_pm_template(db, template)
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Pm_templater updated successfully"}


# ---------------- Create template ----------------
@router.post("/", response_model=PMTemplateOut)
def create_pm_template(
    template: PMTemplateCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    template.org_id = current_user.org_id
    return crud.create_pm_template(db, template)


# ---------------- Delete template ----------------
@router.delete("/{template_id}")
def delete_pm_template_route(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    success = crud.delete_pm_template(db, template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "PM Template deleted successfully"}


# ---------------- Frequency Lookup ----------------
@router.get("/frequency-lookup", response_model=List[Lookup])
def pm_template_frequency_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.pm_templates_frequency_lookup(db, current_user.org_id)


# ---------------- Category Lookup ----------------
@router.get("/category-lookup", response_model=List[Lookup])
def pm_template_category_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.pm_templates_category_lookup(db, current_user.org_id)

# ----------------  Status Lookup ----------------
@router.get("/status-lookup", response_model=List[Lookup])
def pm_templates_status_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.pm_template_status_lookup(db, current_user.org_id)