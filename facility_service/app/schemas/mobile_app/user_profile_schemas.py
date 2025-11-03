from pydantic import BaseModel, UUID4
from typing import List, Optional, Dict, Any


class UserProfileResponse(BaseModel):
    # Personal Info (from auth DB - users table)
    first_name: str
    last_name: str
    picture_url: Optional[str] = None  # from picture_url
    phone: Optional[str] = None
    email: Optional[str] = None

    # Spaces array (replaces 'units')
    spaces: List[Dict[str, Any]]

    # Family members, vehicle details (from facility DB - tenant table JSON)
    family_members: List[Dict[str, Any]]
    vehicle_details: List[Dict[str, Any]]

    # Pet details and documents (added from leases.document)
    pet_details: List[Dict[str, Any]] = []
    documents: List[Dict[str, Any]] = []

    class Config:
        from_attributes = True
