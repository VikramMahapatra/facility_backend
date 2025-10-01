import uuid
from datetime import datetime
from sqlalchemy import Boolean, Column, String, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from shared.database import Base


class Visitor(Base):
    __tablename__ = "visitors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id"), nullable=False)
    space_id = Column(UUID(as_uuid=True), ForeignKey(
        "spaces.id"), nullable=False)
    name = Column(String(128), nullable=False)
    phone = Column(String(20), nullable=False)
    purpose = Column(String(256), nullable=False)
    entry_time = Column(DateTime(timezone=True),
                        default=datetime.now, nullable=False)
    exit_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        Enum("checked_in", "checked_out", "expected", name="visitor_status"),
        nullable=False,
        default="expected"
    )
    vehicle_no = Column(String(20), nullable=True)
    is_expected = Column(Boolean, nullable=False, default=True)
