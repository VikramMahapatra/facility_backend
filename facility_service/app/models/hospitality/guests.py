import uuid
from sqlalchemy import Column, String, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.core.database import Base


class Guest(Base):
    __tablename__ = "guests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id"), nullable=False)
    full_name = Column(String(200), nullable=False)
    email = Column(String(200))
    phone_e164 = Column(String(20))
    kyc = Column(JSON)
    guest_kind = Column(String(16), default="guest")

    # FIXED: Add reciprocal relationship
    site = relationship("Site", back_populates="guests")

    # Other relationships
    bookings = relationship("Booking", back_populates="guest")
    booking_changes = relationship(
        "BookingChange", back_populates="changed_by_guest")
    cancellations_made = relationship(
        "BookingCancellation", back_populates="cancelled_by_guest")
    folios = relationship("Folio", back_populates="payer")
