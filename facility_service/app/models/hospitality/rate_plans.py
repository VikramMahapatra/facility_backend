import uuid
from sqlalchemy import Column, DateTime, String, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from shared.database import Base

class RatePlan(Base):
    __tablename__ = "rate_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False)
    name = Column(String(128), nullable=False)
    meal_plan = Column(String(16))
    policies = Column(JSONB)
    taxes = Column(JSONB)
    status = Column(String(16), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 

    # FIXED: Use string reference
    site = relationship("Site", back_populates="rate_plans")
    
    # Other relationships
    rates = relationship("Rate", back_populates="rate_plan")
    booking_rooms = relationship("BookingRoom", back_populates="rate_plan")