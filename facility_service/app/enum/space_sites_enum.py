from enum import Enum

class OwnershipType(str, Enum):
    PRIMARY = "primary"
    JOINT = "joint"
    INVESTOR = "investor"