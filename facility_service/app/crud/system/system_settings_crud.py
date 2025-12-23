from uuid import UUID
from sqlalchemy.orm import Session
from ...models.system.system_settings import SystemSetting
from ...schemas.system.system_settings_schema import SystemSettingsUpdate

def get_system_settings(db: Session):
    setting = db.query(SystemSetting).first()

    if not setting:
        return None

    return {
        "id": setting.id,
        "general": {
            "system_name": setting.system_name,
            "time_zone": setting.time_zone,
            "date_format": setting.date_format,
            "currency": setting.currency,
            "auto_backup": setting.auto_backup,
            "maintenance_mode": setting.maintenance_mode,
        },
        "security": {
            "password_expiry_days": setting.password_expiry_days,
            "session_timeout_minutes": setting.session_timeout_minutes,
            "api_rate_limit_per_hour": setting.api_rate_limit_per_hour,
            "two_factor_auth_enabled": setting.two_factor_auth_enabled,
            "audit_logging_enabled": setting.audit_logging_enabled,
            "data_encryption_enabled": setting.data_encryption_enabled,
        },
    }


def update_system_settings(db: Session, setting_id: UUID, update_data: SystemSettingsUpdate):
    setting = db.query(SystemSetting).filter(SystemSetting.id == setting_id).first()
    if not setting:
        return None

    #-------- General --------
    if update_data.general:
        for field, value in update_data.general.model_dump(exclude_unset=True).items():
            setattr(setting, field, value)
            
    #-------- Security --------
    if update_data.security:
        for field, value in update_data.security.model_dump(exclude_unset=True).items():
            setattr(setting, field, value)

    db.commit()
    db.refresh(setting)

    return {
        "id": setting.id,
        "general": {
            "system_name": setting.system_name,
            "time_zone": setting.time_zone,
            "date_format": setting.date_format,
            "currency": setting.currency,
            "auto_backup": setting.auto_backup,
            "maintenance_mode": setting.maintenance_mode,
        },
        "security": {
            "password_expiry_days": setting.password_expiry_days,
            "session_timeout_minutes": setting.session_timeout_minutes,
            "api_rate_limit_per_hour": setting.api_rate_limit_per_hour,
            "two_factor_auth_enabled": setting.two_factor_auth_enabled,
            "audit_logging_enabled": setting.audit_logging_enabled,
            "data_encryption_enabled": setting.data_encryption_enabled,
        },
    }

