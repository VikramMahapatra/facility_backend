import json
from operator import or_
from ...models.common.comments import Comment
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, cast, and_, distinct, case
from sqlalchemy.dialects.postgresql import UUID
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from facility_service.app.models.space_sites.spaces import Space

from ...schemas.mobile_app.help_desk_schemas import ComplaintCreateResponse, ComplaintDetailsResponse, ComplaintResponse, ComplaintCreate
from ...models.maintenance_assets.service_request import ServiceRequest
from shared.schemas import UserToken
from sqlalchemy.orm import joinedload


def get_complaints(db: Session, space_id: UUID):
    complaints = db.query(ServiceRequest).filter(
        ServiceRequest.space_id == space_id).all()

    results = []
    for complaint in complaints:
        comments_count = complaint.comments.count()
        results.append(
            ComplaintResponse.model_validate({
                **complaint.__dict__,
                "comments": comments_count or 0
            })
        )

    return results


def raise_complaint(db: Session, complaint_data: ComplaintCreate, current_user: UserToken = None):
    """
    Raise a complaint for a specific space with optimized joins
    """
    space = (
        db.query(Space)
        .options(
            joinedload(Space.site),
            joinedload(Space.building)
        )
        .filter(Space.id == complaint_data.space_id)
        .first()
    )

    if not space:
        return None

    complaint = ServiceRequest(
        org_id=space.org_id,
        site_id=space.site_id,
        space_id=complaint_data.space_id,
        requester_kind="resident",
        requester_id=current_user.user_id,
        category=complaint_data.category,
        request_type=complaint_data.request_type,
        description=complaint_data.description,
        my_preferred_time=complaint_data.my_preferred_time,
        channel="phone"
    )

    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    return ComplaintCreateResponse.model_validate(complaint)


def get_complaint_details(db: Session, service_request_id: str) -> ComplaintDetailsResponse:
    """
    Fetch full Service Request details along with all related comments
    """
    # Step 1: Fetch service request
    service_req = (
        db.query(ServiceRequest)
        .filter(ServiceRequest.id == service_request_id, ServiceRequest.is_deleted == False)
        .first()
    )

    if not service_req:
        raise HTTPException(status_code=404, detail="Service request not found")

    # Step 2: Fetch all comments for that service request (latest first)
    comments = (
        db.query(Comment)
        .filter(
            Comment.entity_id == service_request_id,
            Comment.module_name == "service_request",
            Comment.is_deleted == False
        )
        .order_by(Comment.created_at.desc())  # ✅ latest first
        .all()
    )

    # Step 3: Return as schema
    return ComplaintDetailsResponse(
        id=service_req.id,
        sr_no=service_req.sr_no,
        category=service_req.category,
        priority=service_req.priority,
        status=service_req.status,
        description=service_req.description,
        created_at=service_req.created_at,
        updated_at=service_req.updated_at,
        requester_kind=service_req.requester_kind,
        requester_id=service_req.requester_id,
        space_id=service_req.space_id,
        site_id=service_req.site_id,
        comments=comments
    )
