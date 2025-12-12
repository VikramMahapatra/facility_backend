# app/models/maintenance_assets/pm_template.py

from datetime import date, timedelta 
from dateutil.relativedelta import relativedelta
import uuid
from sqlalchemy import Boolean, Column, DateTime, String, ForeignKey, JSON, Numeric, Date, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.core.database import Base


class PMTemplate(Base):
    __tablename__ = "pm_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey(
        "orgs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey(
        "asset_categories.id", ondelete="SET NULL"), nullable=True)
    checklist = Column(JSON, nullable=True)
    frequency = Column(String(32), nullable=True)
    meter_metric = Column(String(32), nullable=True)
    threshold = Column(Numeric, nullable=True)
    sla = Column(JSON, nullable=True)
    pm_no: str = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),
                        server_default=func.now(), onupdate=func.now())

    # New Columns
    next_due = Column(Date, nullable=True)  # stores next PM due date
    # active/inactive/etc.
    status = Column(String(32), nullable=False, default='active')

    # ✅ Add soft delete columns
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("Org", back_populates="pm_templates")
    category = relationship("AssetCategory", back_populates="pm_templates")

#THIS IS FOR DUE_DATE CALCULATION
    _temp_start_date = None
  
    def set_temp_start_date(self, start_date_value: date):
        self._temp_start_date = start_date_value
    
    @property
    def next_due_calculated(self):
        if not self._temp_start_date or not self.frequency:
            return None
        
        frequency_lower = self.frequency.lower()
        
        if frequency_lower == 'weekly':
            return self._temp_start_date + timedelta(days=7)
            
        elif frequency_lower == 'monthly':
            return self._temp_start_date + relativedelta(months=1)
            
        elif frequency_lower == 'quarterly':
            return self._temp_start_date + relativedelta(months=3)
            
        elif frequency_lower == 'annually':
            return self._temp_start_date + relativedelta(years=1)
            
        else:
            return None
    
    def save_calculated_next_due_to_db(self):
        calculated = self.next_due_calculated
        if calculated:
            self.next_due = calculated