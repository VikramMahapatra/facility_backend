from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Boolean, Column, String, Date, DateTime, func, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from ...models.hospitality.rate_plans import RatePlan
import uuid
from sqlalchemy import JSON
from shared.core.database import Base


class Site(Base):
    __tablename__ = "sites"
    __table_args__ = (
        # 🔥 Best index for your main list API:
        # WHERE org_id = ? AND is_deleted = false ORDER BY created_at DESC
        Index(
            "ix_site_org_active_created_desc",
            "org_id",
            "is_deleted",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
            postgresql_using="btree"
        ),

        # 🔥 Fuzzy search on name (ILIKE %text%)
        Index(
            "ix_site_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"}
        ),

        # 🔥 Fuzzy search on code (ILIKE %text%)
        Index(
            "ix_site_code_trgm",
            "code",
            postgresql_using="gin",
            postgresql_ops={"code": "gin_trgm_ops"}
        ),

        # 🔥 Filtering on kind
        Index("ix_site_kind", "kind"),

        {'extend_existing': True}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey(
        "orgs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    code = Column(String(32))
    kind = Column(String(24), nullable=False)
    address = Column(JSONB)
    geo = Column(JSONB)
    opened_on = Column(Date)
    status = Column(String(16), default="active")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),
                        server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, default=False, nullable=False)

    # Relationships
    org = relationship("Org", back_populates="sites", cascade="all, delete")
    assets = relationship("Asset", back_populates="site")
    buildings = relationship(
        "Building", back_populates="site", cascade="all, delete-orphan")
    spaces = relationship("Space", back_populates="site",
                          cascade="all, delete-orphan")
    space_filters = relationship(
        "SpaceFilter", back_populates="site", cascade="all, delete-orphan")
    tenant_links = relationship(
        "TenantSpace",
        back_populates="site",
        cascade="all, delete-orphan"
    )
    work_orders = relationship("WorkOrder", back_populates="site")
    leases = relationship("Lease", back_populates="site")

    # FIXED: Use string references for hospitality models
    rate_plans = relationship("RatePlan", back_populates="site")
    guests = relationship("Guest", back_populates="site")
    bookings = relationship("Booking", back_populates="site")
    housekeeping_tasks = relationship(
        "HousekeepingTask", back_populates="site")
    meters = relationship("Meter", back_populates="site",
                          cascade="all, delete-orphan")

    contracts = relationship("Contract", back_populates="site")
    tickets = relationship("Ticket", back_populates="site")

    staff_sites = relationship(
        "StaffSite", back_populates="site", cascade="all, delete-orphan")
    # Back-reference to ticket categories
    ticket_categories = relationship("TicketCategory", back_populates="site")
    sla_policies = relationship("SlaPolicy", back_populates="site")
    parking_passes = relationship("ParkingPass", back_populates="site")
