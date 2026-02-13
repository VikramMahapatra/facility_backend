from enum import Enum


class OwnershipType(str, Enum):
    PRIMARY = "primary"
    JOINT = "joint"
    INVESTOR = "investor"


class OwnerMaintenanceStatus(str, Enum):
    PENDING = "pending"
    INVOICED = "invoiced"
    PAID = "paid"
    WAIVED = "waived"


class SpaceCategory(str, Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
