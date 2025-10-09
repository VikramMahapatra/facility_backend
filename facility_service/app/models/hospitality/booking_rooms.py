import uuid
from sqlalchemy import Column, String, Numeric, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.orm import relationship
from shared.database import Base


class BookingRoom(Base):
    __tablename__ = "booking_rooms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"))
    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id"))
    rate_plan_id = Column(UUID(as_uuid=True), ForeignKey("rate_plans.id"))
    price_per_night = Column(Numeric(12, 2), nullable=False)
    taxes = Column(JSON)
    status = Column(String(24), default="allocated")

    booking = relationship("Booking", back_populates="rooms")
    rate_plan = relationship("RatePlan", back_populates="booking_rooms")
