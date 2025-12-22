# schemas/system/system_settings_schema.py
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class SystemGeneralSettings(BaseModel):
    system_name: str
    time_zone: str
    date_format: str
    currency: str
    auto_backup: bool
    maintenance_mode: bool


class SystemSecuritySettings(BaseModel):
    password_expiry_days: int
    session_timeout_minutes: int
    api_rate_limit_per_hour: int
    two_factor_auth_enabled: bool
    audit_logging_enabled: bool
    data_encryption_enabled: bool


class SystemSettingsOut(BaseModel):
    id: UUID
    general: SystemGeneralSettings
    security: SystemSecuritySettings
    
    model_config = {"from_attributes": True}


class SystemGeneralSettingsUpdate(BaseModel):
    system_name: Optional[str] = None
    time_zone: Optional[str] = None
    date_format: Optional[str] = None
    currency: Optional[str] = None
    auto_backup: Optional[bool] = None
    maintenance_mode: Optional[bool] = None


class SystemSecuritySettingsUpdate(BaseModel):
    password_expiry_days: Optional[int] = None
    session_timeout_minutes: Optional[int] = None
    api_rate_limit_per_hour: Optional[int] = None
    two_factor_auth_enabled: Optional[bool] = None
    audit_logging_enabled: Optional[bool] = None
    data_encryption_enabled: Optional[bool] = None


class SystemSettingsUpdate(BaseModel):
    general: Optional[SystemGeneralSettingsUpdate] = None
    security: Optional[SystemSecuritySettingsUpdate] = None
    
    model_config = {"from_attributes": True}
