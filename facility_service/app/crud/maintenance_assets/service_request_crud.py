from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import Text, func, cast, Float ,or_
from ...models.maintenance_assets.service_request import ServiceRequest
from uuid import UUID
from ...schemas.maintenance_assets.service_request import ServiceRequestCreate, ServiceRequestUpdate



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
                    cast(ServiceRequest.sla["duration"], Text),  # cast JSON -> text
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
def _normalize_sla_value(sla):
    if sla is None:
        return {}
    if isinstance(sla, str):
        # Wrap string into dict
        return {"duration": sla}
    if isinstance(sla, dict):
        return sla
    return {}

def _convert_sla_to_string(requests: List[ServiceRequest]) -> List[ServiceRequest]:
    for r in requests:
        r.sla = _normalize_sla_value(r.sla)
    return requests

def search_service_requests(db: Session, org_id: UUID, query: Optional[str] = None) -> List[ServiceRequest]:
    query_base = db.query(ServiceRequest).filter(ServiceRequest.org_id == org_id)
    if query:
        lower_query = query.lower()
        query_base = query_base.filter(
            or_(
                func.lower(ServiceRequest.description).like(f"%{lower_query}%"),
                func.lower(ServiceRequest.requester_kind).like(f"%{lower_query}%")
            )
        )
    results = query_base.all()
    return _convert_sla_to_string(results)

def filter_service_requests_by_status(db: Session, org_id: UUID, status: Optional[str] = None) -> List[ServiceRequest]:
    query = db.query(ServiceRequest).filter(ServiceRequest.org_id == org_id)
    if status:
        query = query.filter(func.lower(ServiceRequest.status) == status.lower())
    results = query.all()
    return _convert_sla_to_string(results)

def filter_service_requests_by_category(db: Session, org_id: UUID, category: Optional[str] = None) -> List[ServiceRequest]:
    query = db.query(ServiceRequest).filter(ServiceRequest.org_id == org_id)
    if category:
        query = query.filter(func.lower(ServiceRequest.category) == category.lower())
    results = query.all()
    return _convert_sla_to_string(results)


#--------------------------crud operation enpointss-----------------------------
#update create change by using userid 

def create_service_request(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    request: ServiceRequestCreate
) -> ServiceRequest:
    db_request = ServiceRequest(
        org_id=org_id,
        requester_id=user_id,  #  always taken from token
        linked_work_order_id=request.linked_work_order_id or None,
        sla=request.sla or {},
        **request.dict(exclude={"requester_id", "linked_work_order_id", "sla"})
    )
    db.add(db_request)
    db.commit()
    db.refresh(db_request)
    return db_request



def get_service_request(db: Session, org_id: UUID, request_id: UUID) -> Optional[ServiceRequest]:
    return db.query(ServiceRequest).filter(
        ServiceRequest.org_id == org_id,
        ServiceRequest.id == request_id
    ).first()


def get_all_service_requests(db: Session, org_id: UUID) -> List[ServiceRequest]:
    return db.query(ServiceRequest).filter(ServiceRequest.org_id == org_id).all()


def update_service_request(
    db: Session,
    org_id: UUID,
    user_id: UUID,   #  new param
    request_id: UUID,
    update_data: ServiceRequestUpdate
) -> Optional[ServiceRequest]:
    db_request = db.query(ServiceRequest).filter(
        ServiceRequest.org_id == org_id,
        ServiceRequest.id == request_id,
        ServiceRequest.requester_id == user_id   #  enforce requester_id match
    ).first()

    if not db_request:
        return None

    update_dict = update_data.dict(exclude_unset=True)
    if "sla" in update_dict:
        update_dict["sla"] = update_dict["sla"] or {}

    for key, value in update_dict.items():
        setattr(db_request, key, value)

    db.commit()
    db.refresh(db_request)
    return db_request



def delete_service_request(db: Session, org_id: UUID, request_id: UUID) -> bool:
    db_request = db.query(ServiceRequest).filter(
        ServiceRequest.org_id == org_id,
        ServiceRequest.id == request_id
    ).first()
    if not db_request:
        return False
    db.delete(db_request)
    db.commit()
    return True
 