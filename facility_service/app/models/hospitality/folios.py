import uuid
from sqlalchemy import Column, String, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.core.database import Base


class Folio(Base):
    __tablename__ = "folios"
    __table_args__ = (UniqueConstraint('booking_id', 'folio_no'),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"))
    folio_no = Column(String(64), nullable=False)
    status = Column(String(16), default="open")
    payer_kind = Column(String(16), default="guest")
    payer_id = Column(UUID(as_uuid=True), ForeignKey("guests.id"))
    created_at = Column(TIMESTAMP)

    payer = relationship("Guest", back_populates="folios")
    # ✅ Relationships
    booking = relationship("Booking", back_populates="folios")
    charges = relationship(
        "FolioCharge", back_populates="folio", cascade="all, delete")
    payments = relationship(
        "FolioPayment", back_populates="folio", cascade="all, delete")
