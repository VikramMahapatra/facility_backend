
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import TIMESTAMP, Boolean, Column, DateTime, Index, Integer, String, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from shared.core.database import Base  # adjust the import to your Base--


class TicketCategory(Base):
    __tablename__ = "ticket_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_name = Column(String(255), nullable=False)
    auto_assign_role = Column(String(255))
    sla_hours = Column(Integer, default=24)
    is_active = Column(Boolean, default=True)
    sla_id = Column(UUID(as_uuid=True), ForeignKey("sla_policies.id"))
    # New column
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=True)

    # Soft delete fields
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
        # ✅ New timestamps
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    sla_policy = relationship("SlaPolicy", back_populates="categories")
    tickets = relationship("Ticket", back_populates="category")
    # New relationship
    site = relationship("Site", back_populates="ticket_categories")


    __table_args__ = (
        # -------------------------------------------------------
        # 1. Composite index for site + active categories
        # -------------------------------------------------------
        Index(
            "ix_ticket_category_site_active",
            "site_id",
            "is_active",
            "category_name"
        ),

        # -------------------------------------------------------
        # 2. Site + deleted status (for soft delete queries)
        # -------------------------------------------------------
        Index(
            "ix_ticket_category_site_deleted",
            "site_id",
            "is_deleted",
            "created_at",
            postgresql_ops={"created_at": "DESC"}
        ),

        # -------------------------------------------------------
        # 3. SLA policy reference (for SLA-related queries)
        # -------------------------------------------------------
        Index("ix_ticket_category_sla", "sla_id"),

        # -------------------------------------------------------
        # 4. Active categories only (partial index)
        # -------------------------------------------------------
        Index(
            "ix_ticket_category_active",
            "category_name",
            "site_id",
            postgresql_where=(is_deleted == False) & (is_active == True)
        ),

        # -------------------------------------------------------
        # 5. Category name lookup (case-insensitive ready)
        # -------------------------------------------------------
        Index(
            "ix_ticket_category_name",
            "category_name",
            postgresql_using='btree'
        ),

        # -------------------------------------------------------
        # 6. Created_at for recent categories
        # -------------------------------------------------------
        Index(
            "ix_ticket_category_created",
            "created_at",
            postgresql_ops={"created_at": "DESC"}
        ),
    )