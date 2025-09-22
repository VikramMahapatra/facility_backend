# app/crud/space_sites/space_filters_crud.py
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from ...models.space_sites.spaces import Space

def get_spaces_by_kind(
    db: Session,
    org_id: UUID,
    site_id: Optional[UUID] = None,
    kind: Optional[str] = None,
):
    query = db.query(Space).filter(Space.org_id == org_id)

    if site_id:
        query = query.filter(Space.site_id == site_id)

    if kind:
        query = query.filter(Space.kind == kind)

    return query.all()
