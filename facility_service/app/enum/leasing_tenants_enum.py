from enum import Enum


class LeaseFrequency (str ,Enum):
    monthly = "monthly"
    quaterly = "quaterly"
    yearly = "yearly"


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


class TenantSpaceStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    leased = "leased"
    ended = "ended"
