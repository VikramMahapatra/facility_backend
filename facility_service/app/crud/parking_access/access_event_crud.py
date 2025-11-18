import uuid
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import Date, func, cast, or_, case, literal, Numeric, and_
from dateutil.relativedelta import relativedelta
from sqlalchemy.dialects.postgresql import UUID

from ...models.space_sites.sites import Site

from ...models.parking_access.access_events import AccessEvent
from ...schemas.parking_access.access_event_schemas import AccessEventOut, AccessEventRequest, AccessEventsResponse


def build_access_event_filters(org_id: UUID, params: AccessEventRequest):
    filters = [AccessEvent.org_id == org_id]

    if params.site_id and params.site_id != "all":
        filters.append(AccessEvent.site_id == params.site_id)

    if params.direction and params.direction != "all":
        filters.append(AccessEvent.direction == params.direction)

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(AccessEvent.vehicle_no.ilike(search_term),
                           AccessEvent.gate.ilike(search_term),
                           AccessEvent.card_id.ilike(search_term)))

    return filters


def get_access_event_query(db: Session, org_id: UUID, params: AccessEventRequest):
    filters = build_access_event_filters(org_id, params)
    return db.query(AccessEvent).filter(*filters)


def get_access_event_overview(db: Session, org_id: UUID):
    today = datetime.now().date()
    event_fields = db.query(
        func.sum(
            case((func.lower(AccessEvent.direction) == "in", 1), else_=0)
        ).label("total_entries"),
        func.sum(
            case((func.lower(AccessEvent.direction) == "out", 1), else_=0)
        ).label("total_exits"),
    ).filter(AccessEvent.org_id == org_id).one()

    todays_event = db.query(func.count()).filter(
        AccessEvent.org_id == org_id,
        cast(AccessEvent.ts, Date) == today
    ).scalar()

    total_unique_ids = db.query(
        func.count(
            func.distinct(
                func.concat(
                    func.coalesce(AccessEvent.vehicle_no, ''),
                    '-',
                    func.coalesce(AccessEvent.card_id, '')
                )
            )
        )
    ).filter(AccessEvent.org_id == org_id).scalar() or 0

    return {
        "todayEvents": int(todays_event or 0),
        "totalEntries": int(event_fields.total_entries or 0),
        "totalExits": int(event_fields.total_exits or 0),
        "totalUniqueIDs": int(total_unique_ids or 0),
    }


def get_access_events(db: Session, org_id: UUID, params: AccessEventRequest) -> AccessEventsResponse:
    base_query = get_access_event_query(db, org_id, params)
    total = base_query.with_entities(func.count(AccessEvent.id)).scalar()

    results = (
        base_query
        .order_by(AccessEvent.ts.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    events = []
    for event in results:
        site_name = (
            db.query(Site.name)
            .filter(Site.id == event.site_id)
            .scalar()
        )
        events.append(AccessEventOut.model_validate({
            **event.__dict__,
            "site_name": site_name
        }))

    return {"events": events, "total": total}
