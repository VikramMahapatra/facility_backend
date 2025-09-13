# app/models/commercial_partners.py
import uuid
from sqlalchemy import Column, String
from sqlalchemy.dialects.sqlite import JSON
from app.core.databases import Base

class CommercialPartner(Base):
    __tablename__ = "commercial_partners"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = Column(String, nullable=False)
    site_id = Column(String, nullable=False)
    type = Column(String(16), nullable=False)  # merchant|brand|kiosk
    legal_name = Column(String(200), nullable=False)
    contact = Column(JSON)
    status = Column(String(16), default="active")
