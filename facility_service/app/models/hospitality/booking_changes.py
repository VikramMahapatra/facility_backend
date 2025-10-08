import uuid
from sqlalchemy import Column, String, JSON, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.database import Base

class BookingChange(Base):
    __tablename__ = "booking_changes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"))
    change_type = Column(String(32), nullable=False)
    old_value = Column(JSON, nullable=False)
    new_value = Column(JSON, nullable=False)
    changed_at = Column(TIMESTAMP)
    changed_by = Column(UUID(as_uuid=True), ForeignKey("guests.id"))
    remarks = Column(String)

    booking = relationship("Booking", back_populates="changes")
    changed_by_guest = relationship("Guest", back_populates="booking_changes")
    booking = relationship("Booking", back_populates="changes")
