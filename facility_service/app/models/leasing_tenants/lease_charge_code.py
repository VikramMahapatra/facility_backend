import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Boolean, Column, ForeignKey, String
from shared.core.database import Base


class LeaseChargeCode(Base):
    __tablename__ = "lease_charge_codes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(32), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    
    
    org = relationship("Org", back_populates="lease_charge_codes")