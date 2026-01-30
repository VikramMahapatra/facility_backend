from enum import Enum


class UserAccountType(str, Enum):
    ORGANIZATION = "organization"
    TENANT = "tenant"
    STAFF = "staff"
    FLAT_OWNER = "owner"


class OwnershipStatus(Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    revoked = "revoked"
    leased = "leased"
    ended = "ended"
