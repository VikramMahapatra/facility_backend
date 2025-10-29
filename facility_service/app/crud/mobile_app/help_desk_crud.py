from operator import or_
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, and_, distinct, case
from sqlalchemy.dialects.postgresql import UUID
from datetime import date, datetime, timedelta
from typing import Dict, Optional

from ...schemas.mobile_app.help_desk_schemas import ComplaintResponse
from ...models.maintenance_assets.service_request import ServiceRequest
from shared.schemas import UserToken


def get_complaints(db: Session, space_id: UUID):
    complaints = db.query(ServiceRequest).filter(
        ServiceRequest.space_id == space_id).all()

    results = []
    for complaint in complaints:
        results.append(ComplaintResponse.model_validate(complaints))

    return results
