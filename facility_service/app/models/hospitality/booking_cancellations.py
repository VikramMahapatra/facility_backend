import uuid
from sqlalchemy import Column, String, Text, ForeignKey, TIMESTAMP, Numeric, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.database import Base

class BookingCancellation(Base):
    __tablename__ = "booking_cancellations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"))
    cancel_reason = Column(Text)
    cancelled_by = Column(UUID(as_uuid=True), ForeignKey("guests.id"))  # points to guests
    cancelled_at = Column(TIMESTAMP(timezone=True), default="now()")
    refund_amount = Column(Numeric(12, 2))
    penalty_amount = Column(Numeric(12, 2))
    policy_applied = Column(JSON)
    refund_processed = Column(Boolean, default=False)

    # relationships
    cancelled_by_guest = relationship("Guest", back_populates="cancellations_made")
    booking = relationship("Booking", back_populates="cancellations")
