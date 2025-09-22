from sqlalchemy import Column, String, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .sites import Site
from .spaces import Space
import uuid
from shared.database import Base

class SpaceFilter(Base):
    __tablename__ = "spaces_filters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"))
    building_block_id = Column(UUID(as_uuid=True), ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True)
    floor = Column(String, nullable=True)
    kind = Column(String, nullable=False)  # apartment, shop, office, etc.
    code = Column(String, nullable=False)
    status = Column(String, default="available")  # available, occupied, out_of_service
    area = Column(Float, nullable=True)

    site = relationship("Site", back_populates="filters")  # <--- must match Site.filters
    building = relationship("Building", back_populates="spaces")