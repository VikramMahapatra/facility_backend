# folio_payments.py
import uuid
from sqlalchemy import Column, String, TIMESTAMP, Numeric,  ForeignKey
from sqlalchemy.dialects.postgresql import UUID , JSONB
from sqlalchemy.orm import relationship
from shared.database import Base

class FolioPayment(Base):
    __tablename__ = "folio_payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folio_id = Column(UUID(as_uuid=True), ForeignKey("folios.id"))
    method = Column(String(24))
    ref_no = Column(String(64))
    amount = Column(Numeric(12,2), nullable=False)
    paid_at = Column(TIMESTAMP)
    metadata_json = Column(JSONB)   

    folio = relationship("Folio", back_populates="payments")
