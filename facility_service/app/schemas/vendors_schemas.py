# app/schemas/vendors.py
from pydantic import BaseModel
from typing import Optional, Any

class VendorBase(BaseModel):
    org_id: str
    name: str
    gst_vat_id: Optional[str] = None
    contact: Optional[Any] = None
    categories: Optional[Any] = None
    rating: Optional[float] = None
    status: Optional[str] = "active"

class VendorCreate(VendorBase):
    pass

class VendorUpdate(VendorBase):
    pass

class VendorOut(VendorBase):
    id: str

    model_config = {
    "from_attributes": True
}
