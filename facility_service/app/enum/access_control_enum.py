from enum import Enum


class UserStatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class UserRoleEnum(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    ACCOUNTANT = "accountant"
    FRONTDESK = "frontdesk"


class UserTypeEnum(str, Enum):
    Organization = "organization"
    STAFF = "staff"
    TENANT = "tenant"
    VENDOR = "vendor"

class ApproverRoleEnum(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    ACCOUNTANT = "accountant"
    FRONTDESK = "frontdesk"


class CanApproveRoleEnum(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    ACCOUNTANT = "accountant"
    FRONTDESK = "frontdesk"
    DEFAULT = "default"
