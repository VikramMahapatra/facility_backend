from operator import or_
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, and_, distinct, case
from sqlalchemy.dialects.postgresql import UUID
from datetime import date, datetime, timedelta
from typing import Dict, Optional

from facility_service.app.models.space_sites.spaces import Space

from ...schemas.mobile_app.help_desk_schemas import ComplaintCreateResponse, ComplaintResponse, ComplaintCreate
from ...models.maintenance_assets.service_request import ServiceRequest
from shared.schemas import UserToken
from sqlalchemy.orm import joinedload


def get_complaints(db: Session, space_id: UUID):
    complaints = db.query(ServiceRequest).filter(
        ServiceRequest.space_id == space_id).all()

    comments_count = complaint.comments.count()
    results = []
    for complaint in complaints:
        results.append(
            ComplaintResponse.model_validate({
                **complaints.__dict__,
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
