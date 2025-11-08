# site_crud.py
from operator import or_
from sqlite3 import IntegrityError
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, and_, distinct, case
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from typing import Dict, Optional

from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response

from ...models.space_sites.buildings import Building
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...models.leasing_tenants.leases import Lease
from ...schemas.space_sites.sites_schemas import SiteCreate, SiteOut, SiteRequest, SiteUpdate
import uuid


def get_sites(db: Session, org_id: str, params: SiteRequest):
    now = datetime.utcnow()
    site_query = (
        db.query(
            Site.id,
            Site.org_id,
            Site.code,
            Site.name,
            Site.kind,
            Site.geo,
            Site.address,
            Site.opened_on,
            Site.status,
            Site.created_at,
            Site.updated_at,
            func.count(Space.id).label("total_spaces"),
            func.count(Building.id).label("buildings"),
            func.sum(
                case(
                    (
                        (Lease.start_date <= now) & (Lease.end_date >= now),
                        1
                    ),
                    else_=0
                )
            ).label("occupied"),
        )
        .outerjoin(Building, Site.id == Building.site_id)
        .outerjoin(Space, Site.id == Space.site_id)
        .outerjoin(Lease, Space.id == Lease.space_id)
        .filter(
            Site.org_id == org_id,
            Site.is_deleted == False,      # Add this filter
            Building.is_deleted == False,  # Add this filter (for count)
            Space.is_deleted == False      # Add this filter (for count)
        )
    )

    if params.kind and params.kind.lower() != "all":
        site_query = site_query.filter(
            func.lower(Site.kind) == params.kind.lower())

    if params.search:
        search_term = f"%{params.search}%"
        site_query = site_query.filter(
            or_(Site.name.ilike(search_term), Site.code.ilike(search_term)))

    total = site_query.group_by(Site.id).count()
    site_query = site_query.group_by(Site.id).offset(
        params.skip).limit(params.limit)
    sites = site_query.all()
    return {"sites": sites, "total": total}


def get_site_lookup(db: Session, org_id: str, params: Optional[SiteRequest] = None):
    site_query = db.query(Site.id, Site.name).filter(Site.is_deleted == False)

    if org_id:
        site_query = site_query.filter(Site.org_id == org_id)

    if params and params.search:
        search_term = f"%{params.search}%"
        site_query = site_query.filter(
            or_(Site.name.ilike(search_term), Site.code.ilike(search_term))
        )

    if params:
        site_query = site_query.group_by(Site.id)
        if params.skip:
            site_query = site_query.offset(params.skip)
        if params.limit:
            site_query = site_query.limit(params.limit)

    return site_query.all()


def get_site_by_id(db: Session, site_id: str):
    return db.query(Site).filter(
        Site.id == site_id,
        Site.is_deleted == False  # Add this filter
    ).first()


def get_site(db: Session, site_id: str):
    site = get_site_by_id(db, site_id)
    if not site:
        return None

    now = datetime.utcnow()

    # Filter only non-deleted spaces and buildings
    total_spaces = db.query(Space).filter(
        Space.site_id == site_id,
        Space.is_deleted == False
    ).count()

    total_buildings = db.query(Building).filter(
        Building.site_id == site_id,
        Building.is_deleted == False
    ).count()

    # occupied spaces based on Lease (only non-deleted spaces)
    occupied = (
        db.query(func.count(Space.id))
        .join(Lease, Space.id == Lease.space_id)
        .filter(
            Space.site_id == site.id,
            Space.is_deleted == False,  # Add this filter
            Lease.start_date <= now,
            Lease.end_date >= now
        )
        .scalar()
    ) or 0

    occupied_percent = max(
        0.0, min(100.0, (occupied / total_spaces * 100) if total_spaces else 0.0))

    return SiteOut(
        id=site.id,
        org_id=site.org_id,
        name=site.name,
        code=site.code,
        kind=site.kind,
        address=site.address,
        geo=site.geo,
        opened_on=site.opened_on,
        status=site.status,
        total_spaces=total_spaces,
        buildings=total_buildings,
        occupied_percent=occupied_percent,
        created_at=site.created_at,
        updated_at=site.updated_at,
    )


# site_crud.py - Update create_site and update_site functions
def create_site(db: Session, site: SiteCreate):
    # Check for duplicate name
    existing_name = db.query(Site).filter(
        Site.org_id == site.org_id,
        Site.is_deleted == False,
        func.lower(Site.name) == func.lower(site.name)
    ).first()

    # Check for duplicate code
    existing_code = db.query(Site).filter(
        Site.org_id == site.org_id,
        Site.is_deleted == False,
        func.lower(Site.code) == func.lower(site.code)
    ).first()

    # Evaluate the comparisons in Python
    name_match = existing_name and existing_name.name.lower() == site.name.lower()
    code_match = existing_code and existing_code.code.lower() == site.code.lower()

    if name_match:
        return error_response(
            message=f"Site with name '{site.name}' already exists",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )

    if code_match:
        return error_response(
            message=f"Site with code '{site.code}' already exists",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )

    # Create site
    db_site = Site(**site.model_dump())
    db.add(db_site)
    db.commit()
    db.refresh(db_site)
    return get_site(db, db_site.id)


def update_site(db: Session, site: SiteUpdate):
    db_site = get_site_by_id(db, site.id)
    if not db_site:
        return error_response(
            message="Site not found",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=404
        )

    update_data = site.dict(exclude_unset=True)

    # Check for duplicates only if name/code is being updated
    if 'name' in update_data or 'code' in update_data:
        # Check for duplicate name
        if 'name' in update_data:
            existing_name = db.query(Site).filter(
                Site.org_id == db_site.org_id,
                Site.id != site.id,
                Site.is_deleted == False,
                func.lower(Site.name) == func.lower(update_data['name'])
            ).first()

            name_match = existing_name and existing_name.name.lower(
            ) == update_data['name'].lower()
            if name_match:
                return error_response(
                    message=f"Site with name '{update_data['name']}' already exists",
                    status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                    http_status=400
                )

        # Check for duplicate code
        if 'code' in update_data:
            existing_code = db.query(Site).filter(
                Site.org_id == db_site.org_id,
                Site.id != site.id,
                Site.is_deleted == False,
                func.lower(Site.code) == func.lower(update_data['code'])
            ).first()

            code_match = existing_code and existing_code.code.lower(
            ) == update_data['code'].lower()
            if code_match:
                return error_response(
                    message=f"Site with code '{update_data['code']}' already exists",
                    status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                    http_status=400
                )

    # Update site
    for key, value in update_data.items():
        setattr(db_site, key, value)

    db.commit()
    db.refresh(db_site)
    return get_site(db, site.id)


# In site_crud.py - update the delete_site function
def delete_site(db: Session, site_id: str) -> Dict:
    """Delete site with protection - check for active buildings first"""
    site = get_site_by_id(db, site_id)
    if not site:
        return {"success": False, "message": "Site not found"}

    # Check if site has any active buildings
    active_buildings_count = db.query(Building).filter(
        Building.site_id == site_id,
        Building.is_deleted == False
    ).count()

    if active_buildings_count > 0:
        return {
            "success": False,
            "message": f"It contains {active_buildings_count} active building(s). Please contact administrator to delete this site.",
            "active_buildings_count": active_buildings_count
        }

    # Also check for spaces directly under site (without building)
    direct_spaces_count = db.query(Space).filter(
        Space.site_id == site_id,
        Space.building_block_id == None,
        Space.is_deleted == False
    ).count()

    if direct_spaces_count > 0:
        return {
            "success": False,
            "message": f"It contains {direct_spaces_count} space(s) not assigned to any building. Please contact administrator to delete this site.",
            "direct_spaces_count": direct_spaces_count
        }

    # Soft delete the site
    site.is_deleted = True
    db.commit()

    return {"success": True, "message": "Site deleted successfully"}
