from enum import Enum


class LeaseDefaultPayer(str, Enum):
    owner = "owner"
    occupant = "occupant"
    split = "split"


class LeaseStatus(str, Enum):
    active = "active"
    expired = "expired"
    terminated = "terminated"
    draft = "draft"




class TenantStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"


class TenantType(str, Enum):
    individual = "individual"
    commercial = "commercial"
