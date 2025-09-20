from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...models.leasing_tenants.leases import Lease

def get_aggregate_overview(db: Session, org_id: str, site_id: Optional[str] = None):
    """
    Return site overview:
      - for a single site if site_id exists and belongs to the org
      - for all sites under the org if site_id is None or invalid
    Includes:
      - total buildings (distinct building_block_id)
      - total spaces
      - occupied spaces count
      - available spaces count
      - occupied spaces percentage
      - list of distinct floors
    """
    now = datetime.utcnow()

    # -------------------------------
    # Check if site_id is valid for this org
    # -------------------------------
    site = None
    if site_id:
        site = db.query(Site).filter(Site.id == site_id, Site.org_id == org_id).first()
        if not site:
            site_id = None  # invalid site_id -> include all sites

    # Base filters
   
    space_filters = [Space.org_id == org_id]
    lease_filters = [Space.org_id == org_id, Lease.start_date <= now, Lease.end_date >= now]

    if site_id:
        space_filters.append(Space.site_id == site_id)
        lease_filters.append(Space.site_id == site_id)

    # Total spaces
  
    total_spaces = db.query(func.count(Space.id)).filter(*space_filters).scalar() or 0

    # Total buildings (distinct building_block_id) - FIXED THIS LINE

    total_buildings = (
        db.query(func.count(func.distinct(Space.building_block_id)))  
        .filter(*space_filters, Space.building_block_id.isnot(None))  
        .scalar()
    ) or 0
    # Distinct floors
    
    distinct_floors = db.query(func.distinct(Space.floor)).filter(*space_filters).all()
    distinct_floors = [f[0] for f in distinct_floors if f[0] is not None]

    # -------------------------------
    # Occupied spaces count (active leases)
    # -------------------------------
    occupied_spaces_count = (
        db.query(func.count(func.distinct(Space.id)))
        .join(Lease, Space.id == Lease.space_id)
        .filter(*lease_filters)
        .scalar()
    ) or 0

    # -------------------------------
    # Available + Occupied percentage
    # -------------------------------
    available_spaces = total_spaces - occupied_spaces_count
    occupied_percentage = round((occupied_spaces_count / total_spaces * 100) if total_spaces else 0.0, 2)

    # -------------------------------
    # Final response
    # -------------------------------
    return {
        "total_spaces": total_spaces,
        "occupied_spaces": occupied_spaces_count,
        "available_spaces": available_spaces,
        "occupied_spaces_percentage": occupied_percentage,
        "total_floors": distinct_floors,
        "total_buildings": total_buildings,
    }