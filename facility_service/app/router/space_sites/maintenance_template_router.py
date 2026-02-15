from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token
from shared.core.schemas import Lookup, UserToken

from ...schemas.space_sites.maintenance_template_schemas import (
    MaintenanceTemplateCreate,
    MaintenanceTemplateListResponse,
    MaintenanceTemplateRequest,
    MaintenanceTemplateUpdate,
    MaintenanceTemplateResponse
)
from ...crud.space_sites.maintenance_template_crud import (
    create_maintenance_template,
    get_maintenance_template_lookup,
    update_maintenance_template,
    delete_maintenance_template,
    get_all_maintenance_templates
)

# assuming you have auth dependency


router = APIRouter(
    prefix="/maintenance-templates",
    tags=["Maintenance Templates"]
)


@router.get("/all", response_model=MaintenanceTemplateListResponse)
def get_templates(
    params: MaintenanceTemplateRequest = Depends(),
    db: Session = Depends(get_db),
    user: UserToken = Depends(validate_current_token)
):

    result = get_all_maintenance_templates(
        db,
        user.org_id,
        params
    )

    return result


@router.post("/", response_model=MaintenanceTemplateResponse)
def create_template(
    payload: MaintenanceTemplateCreate,
    db: Session = Depends(get_db),
    user: UserToken = Depends(validate_current_token)
):

    result = create_maintenance_template(
        db,
        payload,
        user.org_id
    )

    return result


@router.put("/", response_model=MaintenanceTemplateResponse)
def update_template(
    payload: MaintenanceTemplateUpdate,
    db: Session = Depends(get_db),
    user: UserToken = Depends(validate_current_token)
):

    result = update_maintenance_template(
        db,
        user.org_id,
        payload
    )

    if not result:
        raise HTTPException(status_code=404, detail="Template not found")

    return result


@router.delete("/{template_id}")
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    user: UserToken = Depends(validate_current_token)
):

    success = delete_maintenance_template(
        db,
        template_id,
        user.org_id
    )

    if not success:
        raise HTTPException(status_code=404, detail="Template not found")

    return {"message": "Maintenance template deleted successfully"}


@router.get("/lookup", response_model=List[Lookup])
def get_template_lookup(
    params: MaintenanceTemplateRequest = Depends(),
    db: Session = Depends(get_db),
    user: UserToken = Depends(validate_current_token)
):

    return get_maintenance_template_lookup(
        db,
        user.org_id,
        params
    )
