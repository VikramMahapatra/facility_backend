from operator import or_
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional

from ...schemas.system.notifications_schemas import NotificationOut
from ...models.system.notifications import Notification
from shared.core.schemas import CommonQueryParams, Lookup

from ...schemas.access_control.role_management_schemas import (
    RoleCreate, RoleOut, RoleRequest, RoleUpdate
)


def get_all_notifications(db: Session, user_id: str, params: CommonQueryParams):
    notification_query = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_deleted == False  # ✅ ADD THIS
    )

    if params.search:
        search_term = f"%{params.search}%"
        notification_query = notification_query.filter(
            Notification.title.ilike(search_term))

    total = notification_query.with_entities(
        func.count(Notification.id.distinct())).scalar()
    notifications = notification_query.offset(
        params.skip).limit(params.limit).all()

    result = [NotificationOut.model_validate(
        notification) for notification in notifications]
    return {"notifications": result, "total": total}


def get_notification_count(db: Session, user_id: str):
    notification_count = db.query(func.count(Notification.id)).filter(
        Notification.user_id == user_id,
        Notification.read == False,
        Notification.is_deleted == False
    ).scalar()

    return notification_count


def mark_notification_as_read(db: Session, notification_id: str):
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.is_deleted == False
    ).first()

    if not notification:
        return None

    notification.read = True
    db.commit()
    return True


def mark_all_notifications_as_read(db: Session, user_id: str):
    db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_deleted == False,
        Notification.read == False
    ).update({"read": True})
    db.commit()
    return True


def delete_notification(db: Session, notification_id: str):
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.is_deleted == False
    ).first()

    if not notification:
        return None

    notification.is_deleted = True
    db.commit()
    return True


def clear_all_notifications(db: Session, user_id: str):
    """Soft delete all notifications for a user"""
    db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_deleted == False
    ).update({"is_deleted": True})
    db.commit()
    return True
