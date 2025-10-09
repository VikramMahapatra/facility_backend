import uuid
from sqlalchemy import Column, String, Date, DateTime, Integer, Boolean, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.database import Base

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False)
    guest_id = Column(UUID(as_uuid=True), ForeignKey("guests.id"))
    channel = Column(String(24), default="direct")
    status = Column(String(24), default="reserved")
    check_in = Column(Date, nullable=False)
    check_out = Column(Date, nullable=False)
    adults = Column(Integer, default=1)
    children = Column(Integer, default=0)
    notes = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    original_check_in = Column(Date)
    original_check_out = Column(Date)
    original_rate_plan_id = Column(UUID(as_uuid=True), ForeignKey("rate_plans.id"))
    is_modified = Column(Boolean, default=False)
    modified_at = Column(DateTime(timezone=True))

    # FIXED: Use string references
    site = relationship("Site", back_populates="bookings")
    guest = relationship("Guest", back_populates="bookings")
    rooms = relationship("BookingRoom", back_populates="booking")
    folios = relationship("Folio", back_populates="booking")
    changes = relationship("BookingChange", back_populates="booking", cascade="all, delete")
    cancellations = relationship("BookingCancellation", back_populates="booking", cascade="all, delete")
