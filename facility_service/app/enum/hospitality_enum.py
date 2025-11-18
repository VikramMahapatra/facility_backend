from enum import Enum


class BookingChannel(str, Enum):

    direct = "Direct"
    online_travel_agent = "Online Travel Agent"
    corporate = "Corporate"

class BookingStatus(str,Enum):
    
    reserved = "reserved"
    in_house = "in_house"
    cancelled = "cancelled"
    checked_out = "checked_out"
    no_show = "no_show"

class RatePlanStatus (str , Enum):

    active = "Active"
    inactive = "Inactive"

class RatePlansMealPlan(str ,Enum):

    EP = "EP - European Plan (Room Only)"
    CP = "CP-Continental Plan (Room + Breakfast)"
    MAP = "MAP - Modified American Plan (Room + 2 Meals)"
    AP = "AP - American Plan (Room + 3 Meals)"


class HousekeepingTaskPriority (str , Enum):

    high = "high"
    low = "low"
    medium = "medium"