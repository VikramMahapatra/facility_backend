# site_crud.py
from operator import or_
from sqlite3 import IntegrityError
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, and_, distinct, case
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from typing import Dict, Optional

from shared.core.schemas import UserToken
from shared.helpers.property_helper import get_allowed_sites
from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response
from shared.utils.enums import UserAccountType

from ...models.space_sites.buildings import Building
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...models.leasing_tenants.leases import Lease
from ...schemas.space_sites.sites_schemas import SiteCreate, SiteOut, SiteRequest, SiteUpdate
import uuid


def get_sites(db: Session,  user: UserToken, params: SiteRequest):
    now = datetime.utcnow()
    allowed_site_ids = None

    if user.account_type.lower() == UserAccountType.TENANT:
        allowed_sites = get_allowed_sites(db, user)
        allowed_site_ids = [s["site_id"] for s in allowed_sites]

        # Tenant has no access
        if not allowed_site_ids:
            return {"sites": [], "total": 0}
    # --------------------------
    # SUBQUERY: total buildings
    # --------------------------
    buildings_sq = (
        db.query(
            Building.site_id.label("site_id"),
            func.count(Building.id).label("buildings")
        )
        .filter(Building.is_deleted == False)
        .group_by(Building.site_id)
        .subquery()
    )

    # --------------------------
    # SUBQUERY: total spaces
    # --------------------------
    spaces_sq = (
        db.query(
            Space.site_id.label("site_id"),
            func.count(Space.id).label("total_spaces")
        )
        .filter(Space.is_deleted == False)
        .group_by(Space.site_id)
        .subquery()
    )

    # --------------------------
    # SUBQUERY: occupancy count
    # --------------------------
    occupied_sq = (
        db.query(
            Space.site_id.label("site_id"),
            func.count(Lease.id).label("occupied")
        )
        .join(Lease, Lease.space_id == Space.id)
        .filter(
            Space.is_deleted == False,
            Lease.start_date <= now,
            Lease.end_date >= now
        )
        .group_by(Space.site_id)
        .subquery()
    )

    # --------------------------
    # MAIN SITE QUERY
    # --------------------------
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
            func.coalesce(spaces_sq.c.total_spaces, 0).label("total_spaces"),
            func.coalesce(buildings_sq.c.buildings, 0).label("buildings"),
            func.coalesce(occupied_sq.c.occupied, 0).label("occupied")
        )
        .outerjoin(spaces_sq, spaces_sq.c.site_id == Site.id)
        .outerjoin(buildings_sq, buildings_sq.c.site_id == Site.id)
        .outerjoin(occupied_sq, occupied_sq.c.site_id == Site.id)
        .filter( Site.is_deleted == False)
    )

    if allowed_site_ids is not None:
        site_query = site_query.filter(Site.id.in_(allowed_site_ids))
    else:
        site_query = site_query.filter(Site.org_id == user.org_id)
        
    # ------------- Filters --------------
    if params.kind and params.kind.lower() != "all":
        site_query = site_query.filter(
            func.lower(Site.kind) == params.kind.lower()
        )

    if params.search:
        s = f"%{params.search}%"
        site_query = site_query.filter(
            or_(Site.name.ilike(s), Site.code.ilike(s))
        )

    # ----------- Total Count (lightweight) ------------
    total = site_query.with_entities(func.count(Site.id)).scalar()

    # -------- Pagination ----------
    sites = (
        site_query
        .order_by(Site.updated_at.desc(), Site.created_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    # -------- Post-process occupancy percentage --------
    final = []
    for s in sites:
        total_spaces = s.total_spaces or 0
        occupied = s.occupied or 0
        occupied_percent = (
            round((occupied / total_spaces) * 100,
                  2) if total_spaces > 0 else 0
        )

        out = dict(s._mapping)
        out["occupied_percent"] = occupied_percent
        final.append(out)

    return {"sites": final, "total": total}


def get_site_lookup(db: Session, user: UserToken, params: Optional[SiteRequest] = None):
    allowed_site_ids = None

    if user.account_type.lower() == UserAccountType.TENANT:
        allowed_sites = get_allowed_sites(db, user)
        allowed_site_ids = [s["site_id"] for s in allowed_sites]

        # Tenant has no access
        if not allowed_site_ids:
            return {"sites": [], "total": 0}
        
    site_query = db.query(Site.id, Site.name).filter(Site.is_deleted == False)

    
    if allowed_site_ids is not None:
        site_query = site_query.filter(Site.id.in_(allowed_site_ids))
    else:
        site_query = site_query.filter(Site.org_id == user.org_id)

    if params and params.search:
        search_term = f"%{params.search}%"
        site_query = site_query.filter(
            or_(Site.name.ilike(search_term), Site.code.ilike(search_term))
        )
    site_query = site_query.order_by(Site.name.asc())

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

    occupied_percent = round(max(
        0.0, min(100.0, (occupied / total_spaces * 100) if total_spaces else 0.0)),2)

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
    # Print site data before creating
    print("create site data", site.model_dump())

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
