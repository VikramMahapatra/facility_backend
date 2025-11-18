from pydantic import BaseModel
from typing import  Optional
from uuid import UUID
from datetime import date

class AnalyticsRequest(BaseModel):
    site_name: Optional[str] = None
    site_open_month: Optional[str] = None
    