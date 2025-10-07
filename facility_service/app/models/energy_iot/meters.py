import uuid
from sqlalchemy import Column, String, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.database import Base


class Meter(Base):
    __tablename__ = "meters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id"), nullable=False)
    # electricity|water|gas|btuh|people_counter
    kind = Column(String(24), nullable=False)
    code = Column(String(64), nullable=False)
    asset_id = Column(UUID(as_uuid=True), ForeignKey(
        "assets.id"), nullable=True)
    space_id = Column(UUID(as_uuid=True), ForeignKey(
        "spaces.id"), nullable=True)
    unit = Column(String(16), nullable=False)  # kWh, m3, L, CFM
    multiplier = Column(Numeric(10, 4), default=1)

    __table_args__ = (
        UniqueConstraint("org_id", "site_id", "code",
                         name="uq_meters_org_site_code"),
    )

    # Optional relationships (only if you have these models)
    site = relationship("Site", back_populates="meters")
    space = relationship("Space", back_populates="meters")
    readings = relationship(
        "MeterReading", back_populates="meter", cascade="all, delete-orphan")
