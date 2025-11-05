from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from uuid import UUID
from ...models.system.notification_settings import NotificationSetting
from ...schemas.system.notification_settings_schema import (
    NotificationSettingOut,
    NotificationSettingUpdate
)
from shared.schemas import CommonQueryParams

def create_default_settings_for_user(db: Session, user_id: str):
    """Create default settings when user first opens the settings page"""
    defaults = [
        {"label": "System Alerts", "description": "Critical system failures and issues"},
        {"label": "Maintenance Reminders", "description": "Scheduled and preventive maintenance notifications"},
        {"label": "Lease Updates", "description": "Lease renewals, expirations, and changes"},
        {"label": "Financial Notifications", "description": "Payment confirmations and financial alerts"},
        {"label": "Visitor Management", "description": "VIP visits and security notifications"},
        {"label": "AI Predictions", "description": "AI-generated insights and predictions"},
        {"label": "Daily Email Digest", "description": "Summary of daily activities and alerts"},
        {"label": "Mobile Push Notifications", "description": "Real-time notifications on mobile devices"},
    ]

    for setting in defaults:
        existing = db.query(NotificationSetting).filter(
            NotificationSetting.user_id == user_id,
            NotificationSetting.label == setting["label"]
        ).first()
        if not existing:
            new_setting = NotificationSetting(
                user_id=user_id,
                label=setting["label"],
                description=setting["description"],
                enabled=True
            )
            db.add(new_setting)
    db.commit()

def get_all_settings(db: Session, user_id: str, params: CommonQueryParams):
    settings_query = db.query(NotificationSetting).filter(
        NotificationSetting.user_id == user_id
    )

    if params.search:
        search_term = f"%{params.search}%"
        settings_query = settings_query.filter(
            NotificationSetting.label.ilike(search_term))

    total = settings_query.with_entities(
        func.count(NotificationSetting.id.distinct())).scalar()
    settings = settings_query.offset(params.skip).limit(params.limit).all()

    result = [NotificationSettingOut.model_validate(setting) for setting in settings]
    return {"settings": result, "total": total}

def update_setting(db: Session, setting_id: str, user_id: str, update_data: NotificationSettingUpdate):
    # Convert string IDs to UUID for proper database comparison
    setting_uuid = UUID(setting_id)
    user_uuid = UUID(user_id)
    
    setting = db.query(NotificationSetting).filter(
        NotificationSetting.id == setting_uuid,
        NotificationSetting.user_id == user_uuid
    ).first()
    
    if not setting:
        return None

    setting.enabled = update_data.enabled
    db.commit()
    db.refresh(setting)
    return setting