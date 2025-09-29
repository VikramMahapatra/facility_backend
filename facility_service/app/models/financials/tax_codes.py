import uuid
from sqlalchemy import Column, String, Numeric, Integer, ForeignKey, JSON, CHAR, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from shared.database import Base


class TaxCode(Base):
    __tablename__ = "tax_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    # e.g., GST_12, GST_18, CGST_SGST
    code = Column(String(32), nullable=False)
    rate = Column(Numeric(5, 2), nullable=False)
    jurisdiction = Column(String(64), default="IN")
    status: str = Column(String(16), default="active")  # active|inactive
    accounts = Column(JSONB, nullable=True)  # mapping to GL

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),
                        server_default=func.now(), onupdate=func.now())

    # Optional relationship if you have an Org model
    org = relationship("Org", back_populates="tax_codes")


class Currency(Base):
    __tablename__ = "currencies"

    code = Column(CHAR(3), primary_key=True)  # INR, USD
    decimals = Column(Integer, default=2)
