from enum import Enum


class UserAccountType(str, Enum):
    ORGANIZATION = "organization"
    TENANT = "tenant"
    STAFF = "staff"
    FLAT_OWNER = "owner"
