from enum import Enum

class ParkingPassStatus(str, Enum):
    active = "active"
    expired = "expired"
    blocked = "blocked"