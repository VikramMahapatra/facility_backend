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
    COMMON_AREA = "common_area"


SPACE_KINDS = [
    "apartment",
    "shop",
    "office",
    "warehouse",
    "meeting_room",
    "hall",
    "parking",
    "villa",
    "row_house",
    "bungalow",
    "duplex",
    "penthouse",
    "farm_house",
    "lobby",
    "garden",
    "swimming_pool",
    "gym",
    "clubhouse",
    "corridor",
    "lift",
    "parking",
    "security_gate",
]

KIND_TO_CATEGORY = {
    "apartment": "residential",
    "villa": "residential",
    "row_house": "residential",
    "bungalow": "residential",
    "duplex": "residential",
    "penthouse": "residential",
    "farm_house": "residential",
    "shop": "commercial",
    "office": "commercial",
    "warehouse": "commercial",
    "meeting_room": "commercial",
    "hall": "commercial",
    "lobby": "common_area",
    "garden": "common_area",
    "swimming_pool": "common_area",
    "gym": "common_area",
    "clubhouse": "common_area",
    "corridor": "common_area",
    "lift": "common_area",
    "parking": "common_area",
    "security_gate": "common_area"
}


APARTMENT_SUB_KINDS = {
    "studio",
    "1bhk",
    "2bhk",
    "3bhk",
    "4bhk",
    "5bhk",
}
