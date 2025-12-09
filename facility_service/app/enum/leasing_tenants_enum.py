from enum import Enum


class LeaseKind(str, Enum):
    commercial = "commercial"
    residential = "residential"


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
