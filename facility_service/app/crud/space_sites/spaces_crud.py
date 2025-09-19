import uuid
from typing import List, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func, cast
from sqlalchemy.dialects.postgresql import UUID

from app.models.space_sites.sites import Site
from app.models.space_sites.spaces import Space
from app.models.leasing_tenants.leases import Lease
from app.schemas.space_sites.spaces_schemas import SpaceCreate, SpaceUpdate


# ----------------------------------------------------------------------
# OVERVIEW LOGIC
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# OVERVIEW LOGIC (merged: calculate + get)
# ----------------------------------------------------------------------

def get_single_site_overview(db: Session, org_id: str, site_id: Optional[str] = None):
    """
    Return overview for:
      - a single site (if site_id is provided)
      - all sites under the org (if site_id is None)
    """
    now = datetime.utcnow()

    # -------------------------------
    # Base filters
    # -------------------------------
    filters = [Space.org_id == org_id]
    lease_filters = [Space.org_id == org_id, Lease.start_date <= now, Lease.end_date >= now]

    site = None
    if site_id:
        filters.append(Space.site_id == cast(site_id, UUID))
        lease_filters.append(Space.site_id == cast(site_id, UUID))
        site = db.query(Site).filter(Site.id == site_id, Site.org_id == org_id).first()
        if not site:
            return None

    # -------------------------------
    # Total spaces
    # -------------------------------
    total_spaces = (
        db.query(func.count(Space.id))
        .filter(*filters)
        .scalar()
    ) or 0

    # -------------------------------
    # Total buildings (distinct building_block)
    # -------------------------------
    total_buildings = (
        db.query(func.count(func.distinct(Space.building_block)))
        .filter(*filters, Space.building_block.isnot(None))
        .scalar()
    ) or 0

    # -------------------------------
    # Distinct floors
    # -------------------------------
    distinct_floors = (
        db.query(func.distinct(Space.floor))
        .filter(*filters)
        .all()
    )
    distinct_floors = [f[0] for f in distinct_floors if f[0] is not None]

    # -------------------------------
    # Occupied spaces count (active leases)
    # -------------------------------
    occupied_spaces_count = (
        db.query(func.count(Space.id))
        .join(Lease, Space.id == Lease.space_id)
        .filter(*lease_filters)
        .scalar()
    ) or 0

    # -------------------------------
    # Occupied percentage
    # -------------------------------
    occupied_percentage = round((occupied_spaces_count / total_spaces) * 100, 2) if total_spaces else 0.0

    # -------------------------------
    # Final response
    # -------------------------------
    return {
        "site_id": str(site.id) if site else None,
        "site_name": site.name if site else "All Sites",
        "total_buildings": total_buildings,
        "total_spaces": total_spaces,
        "occupied_spaces_percentage": occupied_percentage,
        "total_floors": distinct_floors,
    }
#_________________________________________________________________________________

# ----------------------------------------------------------------------
# ALL SITES OVERVIEW (optimized for org-wide or single-site)
# ----------------------------------------------------------------------
def get_aggregated_overview(db: Session, org_id: str):
    """
    Return aggregated overview for all sites under a given org.
    """
    now = datetime.utcnow()

    # -------------------------------
    # Base filters (org only)
    # -------------------------------
    filters = [Space.org_id == org_id]
    lease_filters = [
        Space.org_id == org_id,
        Lease.start_date <= now,
        Lease.end_date >= now,
    ]

    # -------------------------------
    # Total spaces
    # -------------------------------
    total_spaces = (
        db.query(func.count(Space.id))
        .filter(*filters)
        .scalar()
    ) or 0

    # -------------------------------
    # Total buildings (distinct building_block)
    # -------------------------------
    total_buildings = (
        db.query(func.count(func.distinct(Space.building_block)))
        .filter(*filters, Space.building_block.isnot(None))
        .scalar()
    ) or 0

    # -------------------------------
    # Distinct floors across org
    # -------------------------------
    distinct_floors = (
        db.query(func.distinct(Space.floor))
        .filter(*filters)
        .all()
    )
    distinct_floors = [f[0] for f in distinct_floors if f[0] is not None]

    # -------------------------------
    # Occupied spaces count (active leases)
    # -------------------------------
    occupied_spaces_count = (
        db.query(func.count(Space.id))
        .join(Lease, Space.id == Lease.space_id)
        .filter(*lease_filters)
        .scalar()
    ) or 0

    # -------------------------------
    # Available + Occupied percentage
    # -------------------------------
    available_spaces = total_spaces - occupied_spaces_count
    occupied_percentage = max(
        0.0,
        min(100.0, (occupied_spaces_count / total_spaces * 100) if total_spaces else 0.0),
    )

    # -------------------------------
    # Final response
    # -------------------------------
    return {
        "site_id": None,
        "site_name": "All Sites",
        "total_buildings": total_buildings,
        "total_spaces": total_spaces,
        "occupied_spaces": occupied_spaces_count,
        "available_spaces": available_spaces,
        "occupied_spaces_percentage": occupied_percentage,
        "total_floors": distinct_floors,
    }

# ----------------------------------------------------------------------
# CRUD OPERATIONS
# ----------------------------------------------------------------------

def get_spaces(db: Session, skip: int = 0, limit: int = 100) -> List[Space]:
    return db.query(Space).offset(skip).limit(limit).all()


def get_space_by_id(db: Session, space_id: str) -> Optional[Space]:
    return db.query(Space).filter(Space.id == space_id).first()


def create_space(db: Session, space: SpaceCreate) -> Space:
    db_space = Space(id=str(uuid.uuid4()), **space.dict())
    db.add(db_space)
    db.commit()
    db.refresh(db_space)
    return db_space


def update_space(db: Session, space_id: str, space: SpaceUpdate) -> Optional[Space]:
    db_space = get_space_by_id(db, space_id)
    if not db_space:
        return None
    for k, v in space.dict(exclude_unset=True).items():
        setattr(db_space, k, v)
    db.commit()
    db.refresh(db_space)
    return db_space


def delete_space(db: Session, space_id: str) -> Optional[Space]:
    db_space = get_space_by_id(db, space_id)
    if not db_space:
        return None
    db.delete(db_space)
    db.commit()
    return db_space

