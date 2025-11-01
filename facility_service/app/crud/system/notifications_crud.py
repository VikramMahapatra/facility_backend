from operator import or_
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional

from ...schemas.system.notifications_schemas import NotificationOut
from ...models.system.notifications import Notification
from shared.schemas import CommonQueryParams, Lookup

from ...schemas.access_control.role_management_schemas import (
    RoleCreate, RoleOut, RoleRequest, RoleUpdate
)


def get_all_notifications(db: Session, user_id: str, params: CommonQueryParams):
    notification_query = db.query(Notification).filter(
        Notification.user_id == user_id
    )

    if params.search:
        search_term = f"%{params.search}%"
        notification_query = notification_query.filter(
            Notification.title.ilike(search_term))

    total = notification_query.with_entities(
        func.count(Notification.id.distinct())).scalar()
    roles = notification_query.offset(params.skip).limit(params.limit).all()

    result = [NotificationOut.model_validate(role) for role in roles]
    return {"notifications": result, "total": total}
