from sqlalchemy import Column, Index, Integer, String, Numeric, Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, CHAR
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from shared.core.database import Base


class TaxReport(Base):
    __tablename__ = "tax_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)

    # Format: YYYY-MM
    year = Column(Integer, nullable=False)
    month_no = Column(Integer, nullable=False)

    total_sales = Column(Numeric(15, 2), default=0, nullable=False)
    gst18 = Column(Numeric(15, 2), default=0, nullable=False)
    gst12 = Column(Numeric(15, 2), default=0, nullable=False)
    gst5 = Column(Numeric(15, 2), default=0, nullable=False)
    total_tax = Column(Numeric(15, 2), default=0, nullable=False)

    filed = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True),
                        default=datetime.now, onupdate=datetime.now)

    # Relationships
    org = relationship("Org", back_populates="tax_reports")

    __table_args__ = (
        Index("idx_tax_reports_year_month", "year", "month_no"),
    )
