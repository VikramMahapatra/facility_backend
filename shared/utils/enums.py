from enum import Enum


class UserAccountType(str, Enum):
    PENDING = "pending"
    ORGANIZATION = "organization"
    TENANT = "tenant"
    STAFF = "staff"
    FLAT_OWNER = "owner"
    VENDOR = "vendor"
    SUPER_ADMIN = "super_admin"


class OwnershipStatus(Enum):
    # -- COMMON FOR BOTH
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    # - ADDITIONAL FOR OWNER
    revoked = "revoked"
    # - ADDITIONAL FOR TENANT
    leased = "leased"
    ended = "ended"
