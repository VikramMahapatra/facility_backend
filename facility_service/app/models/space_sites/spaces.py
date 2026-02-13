# space.py
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Boolean, Column, String, Integer, Numeric, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from shared.core.database import Base


class Space(Base):
    __tablename__ = "spaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"))
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id", ondelete="CASCADE"), nullable=False)
    building_block_id = Column(UUID(as_uuid=True), ForeignKey(
        "buildings.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(128))
    kind = Column(String(32), nullable=False)
    floor = Column(String(32))
    area_sqft = Column(Numeric(12, 2))
    beds = Column(Integer)
    baths = Column(Integer)
    attributes = Column(JSONB)
    status = Column(String(24), default="available")

    created_at = Column(DateTime(timezone=True),
                        server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(
    ), onupdate=func.now(), nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    # Relationships
    site = relationship("Site", back_populates="spaces")
    building = relationship(
        "Building", back_populates="spaces", foreign_keys=[building_block_id])
    org = relationship("Org", back_populates="spaces")
    assets = relationship("Asset", back_populates="space",
                          cascade="all, delete-orphan")
    filters = relationship(
        "SpaceFilter", back_populates="space", cascade="all, delete-orphan")
    tenant_links = relationship("TenantSpace", back_populates="space")

    leases = relationship("Lease", back_populates="space")
    work_orders = relationship("WorkOrder", back_populates="space")

    # relationships
    booking_rooms = relationship("BookingRoom", backref="space")
    housekeeping_tasks = relationship(
        "HousekeepingTask", back_populates="space", cascade="all, delete-orphan")
    meters = relationship("Meter", back_populates="space",
                          cascade="all, delete-orphan")
    tickets = relationship("Ticket", back_populates="space")
    parking_passes = relationship("ParkingPass", back_populates="space")
    owners = relationship(
        "SpaceOwner",
        back_populates="space",
        cascade="all, delete-orphan"
    )

    __table_args__ = (

        # -------------------------
        # Existing Indexes
        # -------------------------
        Index(
            "ix_space_building_active",
            "building_block_id",
            "is_deleted"
        ),
        Index(
            "ix_space_status",
            "status"
        ),

        # -------------------------
        # New Recommended Indexes
        # -------------------------

        # 1) Composite index for faster overview counts
        Index(
            "idx_spaces_org_status",
            "org_id",
            "status"
        ),

        # 2) Partial indexes for each status (VERY FAST)
        Index(
            "idx_spaces_available",
            "org_id",
            postgresql_where=(status == "available")
        ),
        Index(
            "idx_spaces_occupied",
            "org_id",
            postgresql_where=(status == "occupied")
        ),
        Index(
            "idx_spaces_oos",
            "org_id",
            postgresql_where=(status == "out_of_service")
        ),
    )
