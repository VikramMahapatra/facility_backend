# app/models/maintenance_assets/pm_template.py

import uuid
from sqlalchemy import Column, String, ForeignKey, JSON, Numeric, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.database import Base

class PMTemplate(Base):
    __tablename__ = "pm_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("asset_categories.id", ondelete="SET NULL"), nullable=True)
    checklist = Column(JSON, nullable=True)  
    frequency = Column(String(32), nullable=True)  
    meter_metric = Column(String(32), nullable=True)  
    threshold = Column(Numeric, nullable=True)
    sla = Column(JSON, nullable=True)  

    # New Columns
    next_due = Column(Date, nullable=True)  # stores next PM due date
    status = Column(String(32), nullable=False, default='active')  # active/inactive/etc.

    # Relationships
    organization = relationship("Org", back_populates="pm_templates")
    category = relationship("AssetCategory", back_populates="pm_templates")
    
