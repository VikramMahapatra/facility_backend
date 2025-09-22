from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.models.space_sites.spaces import Space
from app.schemas.space_sites.space_filter_schemas import SpaceFilterBase, SpaceOverview
from app.models.space_sites.sites import Site

# --- Get all spaces or filtered by site/status/kind ---
def get_spaces(db: Session, site_id: Optional[UUID] = None, status: Optional[str] = None, kind: Optional[str] = None) -> List[SpaceFilterBase]:
    query = db.query(Space)

    if site_id:
        query = query.filter(Space.site_id == site_id)
    if status:
        query = query.filter(Space.status == status)
    if kind:
        query = query.filter(Space.kind == kind)

    return query.all()


# --- Calculate site overview (optional, if needed) ---
def calculate_site_overview(db: Session, site: Site) -> SpaceOverview:
    """
    Example: calculate counts of spaces by kind and status
    """
    overview = {
        "total_spaces": db.query(Space).filter(Space.site_id == site.id).count(),
        "apartments": db.query(Space).filter(Space.site_id == site.id, Space.kind == "apartment").count(),
        "shops": db.query(Space).filter(Space.site_id == site.id, Space.kind == "shop").count(),
        "offices": db.query(Space).filter(Space.site_id == site.id, Space.kind == "office").count(),
        "parking": db.query(Space).filter(Space.site_id == site.id, Space.kind == "parking").count(),
        "hotel_rooms": db.query(Space).filter(Space.site_id == site.id, Space.kind == "hotel_room").count(),
        "meeting_rooms": db.query(Space).filter(Space.site_id == site.id, Space.kind == "meeting_room").count(),
        # optionally add status breakdown
        "occupied": db.query(Space).filter(Space.site_id == site.id, Space.status == "occupied").count(),
        "available": db.query(Space).filter(Space.site_id == site.id, Space.status == "available").count(),
    }

    return overview
