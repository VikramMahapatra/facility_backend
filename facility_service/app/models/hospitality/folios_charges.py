# folio_charges.py
import uuid
from sqlalchemy import Column, String, Text, Date, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID , JSONB
from sqlalchemy.orm import relationship
from shared.database import Base

class FolioCharge(Base):
    __tablename__ = "folio_charges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folio_id = Column(UUID(as_uuid=True), ForeignKey("folios.id"))
    code = Column(String(32))
    description = Column(Text)
    date = Column(Date)
    amount = Column(Numeric(12,2), nullable=False)
    tax_pct = Column(Numeric(5,2), default=0)
    metadata_json = Column(JSONB)   # renamed

    folio = relationship("Folio", back_populates="charges")
