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


SPACE_KINDS = [
    "apartment",
    "shop",
    "office",
    "warehouse",
    "meeting_room",
    "hall",
    "common_area",
    "parking",
    "villa",
    "row_house",
    "bungalow",
    "duplex",
    "penthouse",
    "farm_house",
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
    "common_area": "commercial",
    "parking": "commercial",
}


APARTMENT_SUB_KINDS = {
    "studio",
    "1bhk",
    "2bhk",
    "3bhk",
    "4bhk",
    "5bhk",
}
