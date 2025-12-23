from sqlalchemy import (Column,String,Boolean,Integer,DateTime)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from shared.core.database import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # ---------- General ----------
    system_name = Column(String(100), nullable=False)
    time_zone = Column(String(50), nullable=False)
    date_format = Column(String(20), nullable=False, default="MM/DD/YYYY")
    currency = Column(String(10), nullable=False)

    auto_backup = Column(Boolean, default=True)
    maintenance_mode = Column(Boolean, default=False)

    # ---------- Security ----------
    password_expiry_days = Column(Integer, default=90)
    session_timeout_minutes = Column(Integer, default=30)
    api_rate_limit_per_hour = Column(Integer, default=1000)

    two_factor_auth_enabled = Column(Boolean, default=False)
    audit_logging_enabled = Column(Boolean, default=True)
    data_encryption_enabled = Column(Boolean, default=True)

    # ---------- Meta ----------
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
