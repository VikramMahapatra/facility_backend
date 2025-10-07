from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import Text, and_, func, cast, Float, literal, or_

from facility_service.app.models.crm.contacts import Contact
from shared.schemas import Lookup, UserToken
from ...models.maintenance_assets.service_request import ServiceRequest
from uuid import UUID
from ...schemas.maintenance_assets.service_requests_schemas import (
    ServiceRequestCreate, ServiceRequestListResponse, ServiceRequestOut, ServiceRequestRequest, ServiceRequestUpdate)
from ...enum.maintenance_assets_enum import ServiceRequestStatus, ServiceRequestCategory, ServiceRequestRequesterKind, ServiceRequestPriority, ServiceRequestchannel


def get_service_request_overview(db: Session, org_id: UUID):
    # Total Requests
    total_requests = db.query(func.count(ServiceRequest.id)) \
        .filter(ServiceRequest.org_id == org_id).scalar()

    # Open Requests
    open_requests = db.query(func.count(ServiceRequest.id)) \
        .filter(ServiceRequest.org_id == org_id, ServiceRequest.status == "open").scalar()

    # In Progress Requests
    in_progress_requests = db.query(func.count(ServiceRequest.id)) \
        .filter(ServiceRequest.org_id == org_id, ServiceRequest.status == "in progress").scalar()

    # Avg Resolution (extract number from JSON duration)
    avg_resolution = db.query(
        func.avg(
            cast(
                func.regexp_replace(
                    # cast JSON -> text
                    cast(ServiceRequest.sla["duration"], Text),
                    '[^0-9]',
                    '',
                    'g'
                ),
                Float
            )
        )
    ).filter(ServiceRequest.org_id == org_id).scalar()

    return {
        "total_requests": total_requests or 0,
        "open_requests": open_requests or 0,
        "in_progress_requests": in_progress_requests or 0,
        "avg_resolution_hours": float(avg_resolution) if avg_resolution else None
    }

# ----------------- Build Filters -----------------


def build_service_request_filters(org_id: UUID, params: ServiceRequestRequest):
    filters = [ServiceRequest.org_id == org_id]

    if params.category and params.category.lower() != "all":
        filters.append(func.lower(ServiceRequest.category)
                       == params.category.lower())

    if params.status and params.status.lower() != "all":
        filters.append(func.lower(ServiceRequest.status)
                       == params.status.lower())

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(
            or_(
                ServiceRequest.title.ilike(search_term),
                ServiceRequest.description.ilike(search_term),
                func.cast(ServiceRequest.id, func.Text).ilike(search_term),
            )
        )
    return filters


def get_service_request_query(db: Session, org_id: UUID, params: ServiceRequestRequest):
    filters = build_service_request_filters(org_id, params)
    return db.query(ServiceRequest).filter(*filters)

# ----------------- Get All Service Requests -----------------


def get_service_requests(db: Session, org_id: UUID, params: ServiceRequestRequest) -> ServiceRequestListResponse:
    base_query = get_service_request_query(db, org_id, params)
    total = base_query.with_entities(func.count(ServiceRequest.id)).scalar()

    requests = (
        base_query
        .order_by(ServiceRequest.created_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    results = []
    for r in requests:
        results.append(ServiceRequestOut.model_validate(r.__dict__))

    return {"requests": results, "total": total}

# ----------- Status Lookup -----------


def service_request_filter_status_lookup(db: Session, org_id: str) -> List[Dict]:
    # Query distinct service request statuses for the org
    query = (
        db.query(
            ServiceRequest.status.label("id"),
            ServiceRequest.status.label("name")
        )
        .filter(ServiceRequest.org_id == org_id)
        .distinct()
        .order_by(ServiceRequest.status)
    )
    rows = query.all()
    return [{"id": r.id, "name": r.name} for r in rows]

# --------------------ServiceRequestStatus filter by Enum -----------


def service_request_status_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=status.value, name=status.name.capitalize())
        for status in ServiceRequestStatus
    ]

# ----------- Category Lookup -----------


def service_request_filter_category_lookup(db: Session, org_id: str) -> List[Dict]:
    # Query distinct service request categories for the org
    query = (
        db.query(
            ServiceRequest.category.label("id"),
            ServiceRequest.category.label("name")
        )
        .filter(ServiceRequest.org_id == org_id)
        .distinct()
        .order_by(ServiceRequest.category)
    )
    rows = query.all()
    return [{"id": r.id, "name": r.name} for r in rows]

# --------------------ServiceRequestCategory filter by Enum -----------


def service_request_category_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=category.value, name=category.name.capitalize())
        for category in ServiceRequestCategory
    ]

# --------------------ServiceRequest_requester_kind filter by Enum -----------


def service_request_requester_kind_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=requester_kind.value, name=requester_kind.name.capitalize())
        for requester_kind in ServiceRequestRequesterKind
    ]

# --------------------ServiceRequest_priority filter by Enum -----------


def service_request_priority_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=priority.value, name=priority.name.capitalize())
        for priority in ServiceRequestPriority
    ]
# --------------------ServiceRequest_channle filter by Enum -----------


def service_request_channel_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=channel.value, name=channel.name.capitalize())
        for channel in ServiceRequestchannel
    ]

# --------------------------crud operation enpoints-----------------------------
# update create change by using userid

# ----------------- Create Service Request -----------------


def create_service_request(db: Session, org_id: UUID, user_id: UUID, request: ServiceRequestCreate) -> ServiceRequest:
    db_request = ServiceRequest(
        org_id=org_id,
        requester_id=user_id,
        linked_work_order_id=request.linked_work_order_id or None,
        sla=request.sla or {},
        **request.dict(exclude={"org_id", "requester_id", "linked_work_order_id", "sla"})
    )
    db.add(db_request)
    db.commit()
    db.refresh(db_request)
    return db_request


def update_service_request(db: Session, request_update: ServiceRequestUpdate, current_user: UserToken) -> Optional[ServiceRequest]:
    db_request = db.query(ServiceRequest).filter(
        ServiceRequest.id == request_update.id,
        ServiceRequest.org_id == current_user.org_id,
        or_(ServiceRequest.requester_id == current_user.user_id,
            ServiceRequest.requester_id.is_(None))
    ).first()

    if not db_request:
        return None

    # Update only fields provided (handles SLA dict directly from payload)
    [setattr(db_request, k, v)
     for k, v in request_update.dict(exclude_unset=True).items()]

    db.commit()
    db.refresh(db_request)
    return db_request


# ----------------- Delete -----------------
def delete_service_request(db: Session, request_id: UUID) -> bool:
    db_request = db.query(ServiceRequest).filter(
        ServiceRequest.id == request_id).first()
    if not db_request:
        return False
    db.delete(db_request)
    db.commit()
    return True


def service_request_lookup(db: Session, org_id: UUID):
    assets = (
        db.query(
            ServiceRequest.id.label("id"),
            func.concat(
                Contact.full_name,
                literal(" - "),
                ServiceRequest.priority
            ).label("name")
        )
        .join(Contact, and_(Contact.id == ServiceRequest.requester_id, Contact.kind == ServiceRequest.requester_kind))
        .filter(ServiceRequest.org_id == org_id)
        .distinct()
        .order_by(Contact.full_name)
        .all()
    )
    return assets
