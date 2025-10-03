from enum import Enum


class LeaseKind(str, Enum):
    commercial = "commercial"
    residential = "residential"


class LeaseStatus(str, Enum):
    active = "active"
    expired = "expired"
    terminated = "terminated"
    draft = "draft"


class LeaseChargeCode(str, Enum):
    RENT = "RENT"
    CAM = "CAM"
    ELEC = "ELEC"
    WATER = "WATER"
    PARK = "PARK"
    PENALTY = "PENALTY"
    MAINTENANCE = "MAINTENANCE"
