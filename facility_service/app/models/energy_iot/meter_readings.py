import uuid
from sqlalchemy import Column, String, Numeric, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from shared.database import Base


class MeterReading(Base):
    __tablename__ = "meter_readings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meter_id = Column(UUID(as_uuid=True), ForeignKey(
        "meters.id", ondelete="CASCADE"))
    ts = Column(DateTime(timezone=True), nullable=False)
    reading = Column(Numeric(18, 6), nullable=False)
    delta = Column(Numeric(18, 6))
    source = Column(String(16), default="manual")  # manual | iot
    metadata_json = Column("metadata", JSONB)

    __table_args__ = (
        UniqueConstraint("meter_id", "ts", name="uq_meter_readings_meter_ts"),
    )

    # ✅ Relationship to Meter
    meter = relationship("Meter", back_populates="readings")
