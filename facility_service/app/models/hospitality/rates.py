import uuid
from sqlalchemy import Column, ForeignKey, Date, Numeric, Integer, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.core.database import Base


class Rate(Base):
    __tablename__ = "rates"
    __table_args__ = (UniqueConstraint(
        'rate_plan_id', 'space_group_id', 'date'),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rate_plan_id = Column(UUID(as_uuid=True), ForeignKey("rate_plans.id"))
    space_group_id = Column(UUID(as_uuid=True), ForeignKey("space_groups.id"))
    date = Column(Date, nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    allotment = Column(Integer)
    min_stay = Column(Integer)
    max_stay = Column(Integer)
    closed_to_arrival = Column(Boolean, default=False)
    closed_to_departure = Column(Boolean, default=False)

    rate_plan = relationship("RatePlan", back_populates="rates")
