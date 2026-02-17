# site_crud.py
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, and_, distinct, case
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from typing import Dict, List, Optional

from facility_service.app.models.financials.tax_codes import TaxCode
from facility_service.app.models.space_sites.maintenance_templates import MaintenanceTemplate
from facility_service.app.models.space_sites.sites import Site
from facility_service.app.schemas.space_sites.maintenance_template_schemas import MaintenanceTemplateCreate, MaintenanceTemplateRequest, MaintenanceTemplateResponse, MaintenanceTemplateUpdate
from shared.core.schemas import UserToken
from shared.helpers.property_helper import get_allowed_sites
from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response


def get_all_maintenance_templates(
    db: Session,
    org_id: UUID,
    params: MaintenanceTemplateRequest
):

    base_query = (
        db.query(
            MaintenanceTemplate,
            Site.name.label("site_name"),
            TaxCode.rate.label("tax_rate")
        )
        .join(Site, Site.id == MaintenanceTemplate.site_id)
        .outerjoin(TaxCode, MaintenanceTemplate.tax_code_id == TaxCode.id)
        .filter(
            MaintenanceTemplate.org_id == org_id,
            MaintenanceTemplate.is_deleted == False
        )
    )

    if params.search:
        search_term = f"%{params.search}%"
        base_query = base_query.filter(
            MaintenanceTemplate.name.ilike(search_term)
        )

    if params.site_id and params.site_id.lower() != "all":
        base_query = base_query.filter(
            MaintenanceTemplate.site_id == params.site_id
        )

    if params.category and params.category.lower() != "all":
        base_query = base_query.filter(
            MaintenanceTemplate.category == params.category
        )

    if params.kind and params.kind.lower() != "all":
        base_query = base_query.filter(
            MaintenanceTemplate.kind == params.kind
        )

    # ✅ COUNT (no order_by)
    total = base_query.with_entities(
        func.count(MaintenanceTemplate.id)
    ).scalar()

    # ✅ Data query with ordering + pagination
    results = (
        base_query
        .order_by(
            MaintenanceTemplate.updated_at.desc(),
            MaintenanceTemplate.created_at.desc()
        )
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    response = []
    for template, site_name, tax_rate in results:
        template.site_name = site_name
        template.tax_rate = tax_rate
        response.append(template)

    return {"templates": response, "total": total}


def create_maintenance_template(
    db: Session,
    maintenance_template: MaintenanceTemplateCreate,
    org_id: UUID
) -> MaintenanceTemplate:

    # Check duplicate name inside org (case-insensitive)
    existing = db.query(MaintenanceTemplate).filter(
        MaintenanceTemplate.org_id == org_id,
        MaintenanceTemplate.is_deleted == False,
        func.lower(MaintenanceTemplate.name) == func.lower(
            maintenance_template.name)
    ).first()

    if existing:
        return error_response(
            message=f"Maintenance template '{maintenance_template.name}' already exists"
        )

    data = maintenance_template.model_dump()
    data["org_id"] = org_id

    db_template = MaintenanceTemplate(**data)

    db.add(db_template)
    db.commit()
    db.refresh(db_template)

    return db_template


def update_maintenance_template(
    db: Session,
    org_id: UUID,
    template_update: MaintenanceTemplateUpdate
) -> Optional[MaintenanceTemplate]:

    db_template = db.query(MaintenanceTemplate).filter(
        MaintenanceTemplate.id == template_update.id,
        MaintenanceTemplate.org_id == org_id,
        MaintenanceTemplate.is_deleted == False
    ).first()

    if not db_template:
        return None

    update_data = template_update.model_dump(exclude_unset=True)

    # Duplicate name validation if name changed
    if 'name' in update_data and update_data['name'].lower() != db_template.name.lower():

        existing = db.query(MaintenanceTemplate).filter(
            MaintenanceTemplate.org_id == org_id,
            MaintenanceTemplate.id != template_update.id,
            MaintenanceTemplate.is_deleted == False,
            func.lower(MaintenanceTemplate.name) == func.lower(
                update_data['name'])
        ).first()

        if existing:
            return error_response(
                message=f"Maintenance template '{update_data['name']}' already exists"
            )

    for key, value in update_data.items():
        setattr(db_template, key, value)

    db.commit()
    db.refresh(db_template)

    # ✅ fetch site_name
    site_name = None
    if db_template.site_id:
        site_name = db.query(Site.name).filter(
            Site.id == db_template.site_id
        ).scalar()

    # attach dynamically for response schema
    db_template.site_name = site_name

    return db_template


def delete_maintenance_template(
    db: Session,
    template_id: UUID,
    org_id: UUID
) -> bool:

    db_template = db.query(MaintenanceTemplate).filter(
        MaintenanceTemplate.id == template_id,
        MaintenanceTemplate.org_id == org_id,
        MaintenanceTemplate.is_deleted == False
    ).first()

    if not db_template:
        return False

    db_template.is_deleted = True

    db.commit()

    return True


def get_maintenance_template_lookup(
        db: Session,
        org_id: str,
        params: MaintenanceTemplateRequest):
    query = (
        db.query(
            MaintenanceTemplate.id,
            MaintenanceTemplate.name,
        )
        .outerjoin(Site, Site.id == MaintenanceTemplate.site_id)
        .filter(
            MaintenanceTemplate.org_id == org_id,
            MaintenanceTemplate.is_deleted == False
        )
    )

    if params.search:
        search_term = f"%{params.search}%"
        query = query.filter(
            MaintenanceTemplate.name.ilike(search_term)
        )

    if params.site_id:
        query = query.filter(
            MaintenanceTemplate.site_id == params.site_id
        )

    if params.category:
        query = query.filter(
            MaintenanceTemplate.category == params.category
        )

    if params.kind:
        query = query.filter(
            MaintenanceTemplate.kind == params.kind
        )

    query = query.order_by(MaintenanceTemplate.created_at.desc())

    return query.all()
