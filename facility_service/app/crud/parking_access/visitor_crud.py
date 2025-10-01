import uuid
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import Date, func, cast, or_, case, literal, Numeric, and_
from dateutil.relativedelta import relativedelta
from sqlalchemy.dialects.postgresql import UUID

from ...models.space_sites.buildings import Building
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...models.parking_access.visitors import Visitor
from ...schemas.parking_access.visitor_schemas import VisitorCreate, VisitorOut, VisitorRequest, VisitorUpdate, VisitorsResponse


def build_visitor_filters(org_id: UUID, params: VisitorRequest):
    filters = [Visitor.org_id == org_id]

    if params.site_id and params.site_id != "all":
        filters.append(Visitor.site_id == params.site_id)

    if params.status and params.status != "all":
        filters.append(func.lower(Visitor.status) == params.status.lower())

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(Visitor.name.ilike(search_term),
                       Visitor.phone.ilike(search_term),
                       Space.name.ilike(search_term)))

    return filters


def get_visitor_query(db: Session, org_id: UUID, params: VisitorRequest):
    filters = build_visitor_filters(org_id, params)
    return db.query(Visitor).join(Space, Space.id == Visitor.space_id).filter(*filters)


def get_visitor_overview(db: Session, org_id: UUID):
    today = datetime.now().date()
    visitor_fields = db.query(
        func.count(Visitor.id).label("total_records"),
        func.sum(
            case((Visitor.vehicle_no.isnot(None), 1), else_=0)
        ).label("with_vehicles"),
    ).filter(Visitor.org_id == org_id).one()

    today_fields = (
        db.query(
            func.sum(
                case((Visitor.status == "checked_in", 1), else_=0)
            ).label("checked_in"),
            func.sum(
                case((Visitor.status == "expected", 1), else_=0)
            ).label("expected"),
        ).filter(
            Visitor.org_id == org_id,
            cast(Visitor.entry_time, Date) == today
        ).one()
    )

    return {
        "checkedInToday": int(today_fields.checked_in or 0),
        "expectedToday": int(today_fields.expected or 0),
        "totalVisitors": int(visitor_fields.total_records or 0),
        "totalVisitorsWithVehicle": int(visitor_fields.with_vehicles or 0),
    }


def get_visitors(db: Session, org_id: UUID, params: VisitorRequest) -> VisitorsResponse:
    base_query = get_visitor_query(db, org_id, params)
    total = base_query.with_entities(func.count(Visitor.id)).scalar()

    results = (
        base_query
        .order_by(Visitor.entry_time.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    visitors = []
    for visitor in results:
        visiting = (
            db.query(
                func.concat(
                    func.coalesce(Building.name, ''),
                    '-',
                    func.coalesce(Space.name, '')
                ).label("space_name")
            )
            .select_from(Space)
            .join(Building, Space.building_block_id == Building.id)
            .filter(Space.id == visitor.space_id)
            .scalar()
        )
        visitors.append(VisitorOut.model_validate({
            **visitor.__dict__,
            "visiting": visiting
        }))

    return {"visitors": visitors, "total": total}


def get_visitor_by_id(db: Session, visitor_id: str):
    return db.query(Visitor).filter(Visitor.id == visitor_id).first()


def create_visitor_log(db: Session, data: VisitorCreate):
    db_visitor = Visitor(**data.model_dump())
    db.add(db_visitor)
    db.commit()
    db.refresh(db_visitor)
    return db_visitor


def update_visitor_log(db: Session, data: VisitorUpdate):
    db_visitor = get_visitor_by_id(db, data.id)
    if not db_visitor:
        return None
    for k, v in data.dict(exclude_unset=True).items():
        setattr(db_visitor, k, v)
    db.commit()
    db.refresh(db_visitor)
    return db_visitor


def delete_visitor_log(db: Session, visitor_id: str):
    db_visitor = get_visitor_by_id(db, visitor_id)
    if not db_visitor:
        return None
    db.delete(db_visitor)
    db.commit()
    return True
