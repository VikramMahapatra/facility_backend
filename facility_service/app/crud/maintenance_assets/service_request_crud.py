from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import Text, and_, func, cast, Float, literal,String, or_ 

from ...models.maintenance_assets.work_order import WorkOrder
from facility_service.app.models.crm.contacts import Contact
from shared.schemas import Lookup, UserToken
from ...models.maintenance_assets.service_request import ServiceRequest
from uuid import UUID
from ...schemas.maintenance_assets.service_requests_schemas import (
    ServiceRequestCreate, ServiceRequestListResponse, ServiceRequestOut, ServiceRequestRequest, ServiceRequestUpdate)
from ...enum.maintenance_assets_enum import ServiceRequestStatus, ServiceRequestCategory, ServiceRequestRequesterKind, ServiceRequestPriority, ServiceRequestchannel



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
                ServiceRequest.description.ilike(search_term),
                func.cast(ServiceRequest.id, String).ilike(search_term),
            )
        )
    return filters


def get_service_request_query(db: Session, org_id: UUID, params: ServiceRequestRequest):
    filters = build_service_request_filters(org_id, params)
    return db.query(ServiceRequest).filter(*filters)



def get_service_request_overview(db: Session, org_id: UUID, params: ServiceRequestRequest):
    # Build filters
    filters = build_service_request_filters(org_id, params)

    # Total Requests
    total_requests = db.query(func.count(ServiceRequest.id)) \
        .filter(*filters).scalar()

    # Open Requests
    open_requests = db.query(func.count(ServiceRequest.id)) \
        .filter(*filters, ServiceRequest.status == "open").scalar()

    # In Progress Requests
    in_progress_requests = db.query(func.count(ServiceRequest.id)) \
        .filter(*filters, ServiceRequest.status == "in progress").scalar()

    # Avg Resolution (extract number from JSON duration)
    avg_resolution = db.query(
        func.avg(
            cast(
                func.regexp_replace(
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
        "avg_resolution_hours": round(avg_resolution,2) if avg_resolution else None
    }

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
        customer_name = (
        db.query(Contact.full_name)
        .filter(Contact.id == r.requester_id)
        .scalar()
            )

        results.append(ServiceRequestOut.model_validate(
            {**r.__dict__, "requester_name": customer_name}
        ))


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
        .order_by("name")
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
        func.lower(ServiceRequest.category ).label("id"),
        func.lower(ServiceRequest.category).label("name")
        )
        .filter(
            ServiceRequest.org_id == org_id,
            ServiceRequest.category.isnot(None),
            ServiceRequest.category != ""
        )
        .distinct()
        .order_by("name")
    )
    rows = query.all()
    return [{"id": r.id, "name": r.name.title()} for r in rows]

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

# ----------------- Create Service Request -----------------
def create_service_request(db: Session, org_id: UUID, request: ServiceRequestCreate) -> ServiceRequest:
    db_request = ServiceRequest(
        org_id=org_id,
        **request.model_dump(exclude={"org_id", "requester_name"})
    )
    db.add(db_request)
    db.commit()
    db.refresh(db_request)

    # 🔗 Link WorkOrder if provided
    if getattr(request, "linked_work_order_id", None):
        db.query(WorkOrder).filter(WorkOrder.id == request.linked_work_order_id).update(
            {"request_id": db_request.id}
        )
        db.commit()

    return db_request


def update_service_request(db: Session, request_update: ServiceRequestUpdate, current_user: UserToken) -> Optional[ServiceRequest]:
    db_request = (
        db.query(ServiceRequest)
        .filter(
            ServiceRequest.id == request_update.id,
            ServiceRequest.org_id == current_user.org_id,
        )
        .first()
    )

    if not db_request:
        return None

    old_work_order_id = getattr(db_request, "linked_work_order_id", None)

    # ✅ Apply updates
    for k, v in request_update.model_dump(exclude_unset=True).items():
        setattr(db_request, k, v)

    db.commit()
    db.refresh(db_request)

    # 🔄 Unlink old WorkOrder if changed
    if old_work_order_id and old_work_order_id != getattr(request_update, "linked_work_order_id", None):
        db.query(WorkOrder).filter(WorkOrder.id == old_work_order_id).update({"request_id": None})

    # 🔗 Link new WorkOrder if provided
    if getattr(request_update, "linked_work_order_id", None):
        db.query(WorkOrder).filter(WorkOrder.id == request_update.linked_work_order_id).update(
            {"request_id": db_request.id}
        )

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
    requests = (
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
        .order_by("name")
        .all()
    )
    return requests


def service_request_filter_workorder_lookup(db: Session, org_id: str) -> List[Dict]:
    query = (
        db.query(
            WorkOrder.id.label("id"),
            WorkOrder.wo_no.label("name")
        )
        .filter(WorkOrder.org_id == org_id)
        .distinct()
        .order_by(WorkOrder.wo_no)
    )

    rows = query.all()
    # Convert UUID to string for JSON serialization
    return [{"id": str(r.id), "name": r.name} for r in rows]
